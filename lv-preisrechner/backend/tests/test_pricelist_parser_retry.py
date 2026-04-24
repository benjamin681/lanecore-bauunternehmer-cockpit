"""Retry-Resilienz des Pricelist-Parsers (B+4.5).

Getestet wird die Verhaltens-Ebene:
- JSON-Fehler im ersten Claude-Call → Retry mit verschaerftem User-Hint.
- Zweiter Retry-Versuch nach weiterem JSON-Fehler.
- Kompletter Batch-Ausfall nach erschoepften Retries, ohne den Parse
  abzubrechen; andere Batches laufen weiter; parse_error_details haelt
  den Fehler strukturiert fest.
- Nicht-JSON-Fehler (APIStatusError, z.B. 429) werden NICHT in den
  JSON-Retry-Pfad gefuehrt — sie brechen den Batch sofort ab und der
  Parse laeuft weiter (die Rate-Limit-Retries macht der Claude-Client
  selbst).
- Status-Aggregation: >=80 % Batches ok → PARTIAL_PARSE, darunter →
  ERROR.
"""
from __future__ import annotations

import io
import uuid

import fitz  # PyMuPDF
import pytest

from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
)
from app.services.pricelist_parser import PricelistParser


# --------------------------------------------------------------------------- #
# Helpers (identisch zum Hauptfile, nur isoliert)
# --------------------------------------------------------------------------- #
def _make_multipage_pdf(num_pages: int = 6) -> bytes:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Seite {i + 1} — Kemmler Ausbau 2026")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _register_and_login(c, email: str) -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": "TestBetrieb",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _upload_multipage(c, token: str) -> str:
    pdf = _make_multipage_pdf(num_pages=6)
    resp = c.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                f"retry-{uuid.uuid4().hex[:6]}.pdf",
                io.BytesIO(pdf),
                "application/pdf",
            ),
        },
        data={
            "supplier_name": "Kemmler",
            "list_name": "Retry-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _valid_response(product_suffix: str) -> dict:
    """Kanonische gueltige Antwort eines Claude-Vision-Batches."""
    return {
        "page": 1,
        "entries": [
            {
                "article_number": f"ART-{product_suffix}",
                "manufacturer": "Knauf",
                "product_name": f"GKB {product_suffix} 2000x1250x12,5 mm",
                "category": "Gipskarton",
                "price_net": 3.00,
                "currency": "EUR",
                "unit": "€/m²",
                "attributes": {},
                "parser_confidence": 0.95,
                "needs_review_hint": False,
                "source_row_raw": f"raw-{product_suffix}",
            },
        ],
    }


class _ScriptedClaude:
    """Ruft pro Aufruf eine scripted Reaktion ab.

    Jeder Script-Eintrag ist entweder:
    - ("ok", dict) → liefert dict als parsed response.
    - ("json_error", message) → wirft ValueError(message) (JSON-Fail).
    - ("api_error", exc) → wirft exc (z.B. APIStatusError-Stub).
    """

    def __init__(self, script: list):
        self._script = list(script)
        self.calls: list[dict] = []

    def extract_json(
        self,
        *,
        system=None,
        images=None,
        user_text=None,
        force_fallback=False,
        max_tokens=None,
    ):
        self.calls.append(
            {
                "user_text": user_text,
                "force_fallback": force_fallback,
                "num_images": len(images or []),
            }
        )
        if not self._script:
            raise AssertionError(
                "Scripted-Claude: zu viele Aufrufe — Script erschoepft"
            )
        kind, payload = self._script.pop(0)
        if kind == "ok":
            return payload, "claude-sonnet-4-6"
        if kind == "json_error":
            raise ValueError(f"Claude gab kein gültiges JSON: {payload}")
        if kind == "api_error":
            raise payload
        raise AssertionError(f"Unbekannter Script-Kind: {kind}")


def _sl():
    from app.core import database

    return database.SessionLocal


# --------------------------------------------------------------------------- #
# Test 1 — Retry nach einem JSON-Fehler ist erfolgreich
# --------------------------------------------------------------------------- #
def test_retry_nach_erstem_json_fehler(client):
    token = _register_and_login(client, "retry1@example.com")
    pl_id = _upload_multipage(client, token)

    # 6 Seiten / batch_size=3 → 2 Batches
    # Batch 1: erst JSON-Error, dann OK
    # Batch 2: direkt OK
    mock = _ScriptedClaude(
        [
            ("json_error", "Expecting ',' delimiter: line 3 column 10"),
            ("ok", _valid_response("A")),
            ("ok", _valid_response("B")),
        ]
    )

    with _sl()() as db:
        parser = PricelistParser(db=db, claude_client=mock, batch_size=3)
        result = parser.parse(pl_id)

    # 3 Calls (1 Fehler + 1 Retry auf Batch 1, 1 auf Batch 2)
    assert len(mock.calls) == 3
    # Erster Aufruf ohne Hint, zweiter mit dem Retry-Hint
    assert mock.calls[0]["user_text"] is None
    assert "ungueltiges JSON" in (mock.calls[1]["user_text"] or "")
    # Batch 2 bekommt keinen Hint (eigener Frisch-Start)
    assert mock.calls[2]["user_text"] is None

    assert result.parsed_entries == 2  # 1 pro Batch
    assert len(result.errors) == 0

    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert pl.status == PricelistStatus.PARSED.value
        assert pl.parse_error_details is None
        assert pl.parse_error is None


# --------------------------------------------------------------------------- #
# Test 2 — Zwei JSON-Fehler in Folge, dritter Versuch gewinnt
# --------------------------------------------------------------------------- #
def test_retry_zweiter_versuch_ist_erfolgreich(client):
    token = _register_and_login(client, "retry2@example.com")
    pl_id = _upload_multipage(client, token)

    mock = _ScriptedClaude(
        [
            ("json_error", "Attempt 1 Fail"),
            ("json_error", "Attempt 2 Fail"),
            ("ok", _valid_response("A")),
            ("ok", _valid_response("B")),
        ]
    )

    with _sl()() as db:
        parser = PricelistParser(db=db, claude_client=mock, batch_size=3)
        result = parser.parse(pl_id)

    # 4 Calls: 3 fuer Batch 1 (2 Fehler + 1 Erfolg), 1 fuer Batch 2
    assert len(mock.calls) == 4
    # Beide Retries sollten den Hint bekommen
    assert "ungueltiges JSON" in (mock.calls[1]["user_text"] or "")
    assert "ungueltiges JSON" in (mock.calls[2]["user_text"] or "")

    assert result.parsed_entries == 2
    assert len(result.errors) == 0

    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert pl.status == PricelistStatus.PARSED.value


# --------------------------------------------------------------------------- #
# Test 3 — Kompletter Ausfall nach 2 Retries, anderer Batch laeuft weiter
# --------------------------------------------------------------------------- #
def test_batch_ausfall_nach_max_retries_partial_parse(client):
    token = _register_and_login(client, "retry3@example.com")
    pl_id = _upload_multipage(client, token)

    # 10 Seiten / batch_size=2 → 5 Batches
    # 1 von 5 schlaegt durchgehend fehl (3 JSON-Errors = 1 initial + 2 Retries)
    # Die anderen 4 Batches laufen sauber durch. 4/5 = 80% → PARTIAL_PARSE
    pdf = _make_multipage_pdf(num_pages=10)
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                f"retry3-{uuid.uuid4().hex[:6]}.pdf",
                io.BytesIO(pdf),
                "application/pdf",
            ),
        },
        data={
            "supplier_name": "Kemmler",
            "list_name": "Retry-Test-Partial",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    pl_id = resp.json()["id"]

    mock = _ScriptedClaude(
        [
            ("ok", _valid_response("B1")),       # Batch 1 ok
            ("ok", _valid_response("B2")),       # Batch 2 ok
            # Batch 3: drei Fehler in Folge -> Ausfall
            ("json_error", "ep 1"),
            ("json_error", "ep 2"),
            ("json_error", "ep 3"),
            ("ok", _valid_response("B4")),       # Batch 4 ok
            ("ok", _valid_response("B5")),       # Batch 5 ok
        ]
    )

    with _sl()() as db:
        parser = PricelistParser(db=db, claude_client=mock, batch_size=2)
        result = parser.parse(pl_id)

    # 4 Batches erfolgreich, 1 fehlgeschlagen
    assert result.parsed_entries == 4
    assert len(result.errors) == 1
    assert "Batch 3" in result.errors[0]

    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        # 4/5 = 80% → genau Grenze → PARTIAL_PARSE
        assert pl.status == PricelistStatus.PARTIAL_PARSE.value
        assert pl.parse_error_details is not None
        assert len(pl.parse_error_details) == 1
        fail = pl.parse_error_details[0]
        assert fail["batch_idx"] == 3
        assert fail["page_range"] == "5-6"
        assert fail["attempts"] == 3  # 1 initial + 2 retries
        assert fail["error_class"] == "ValueError"
        assert "ep 3" in fail["error_message"]
        assert "batch_3_attempt_3" in (fail["raw_response_file"] or "")


# --------------------------------------------------------------------------- #
# Test 4 — Nicht-JSON-Fehler (z.B. Rate-Limit) geht NICHT in den Retry-Pfad
# --------------------------------------------------------------------------- #
class _StubAPIError(Exception):
    """Stub fuer APIStatusError — was der Claude-Client bei 429/auth etc. nach 3 Versuchen raised."""

    def __init__(self, message: str = "rate limit"):
        super().__init__(message)


def test_nicht_json_fehler_triggert_keinen_retry(client):
    token = _register_and_login(client, "retry4@example.com")
    pl_id = _upload_multipage(client, token)

    mock = _ScriptedClaude(
        [
            # Batch 1: APIStatusError — sollte sofort aufgegeben werden,
            # KEIN Retry mit verschaerftem Prompt.
            ("api_error", _StubAPIError("429 rate limit")),
            ("ok", _valid_response("B2")),
        ]
    )

    with _sl()() as db:
        parser = PricelistParser(db=db, claude_client=mock, batch_size=3)
        result = parser.parse(pl_id)

    # 2 Calls: Batch 1 (1×, kein Retry) + Batch 2 (1×)
    assert len(mock.calls) == 2
    # Batch 2 bekommt keinen Hint
    assert mock.calls[1]["user_text"] is None

    assert result.parsed_entries == 1  # nur Batch 2 durch
    assert len(result.errors) == 1

    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        # 1/2 = 50% → unter 80% → ERROR
        assert pl.status == PricelistStatus.ERROR.value
        assert pl.parse_error_details is not None
        fail = pl.parse_error_details[0]
        assert fail["batch_idx"] == 1
        # Nur 1 Versuch, kein Retry
        assert fail["attempts"] == 1
        assert fail["error_class"] == "_StubAPIError"
        # Kein Raw-Dump-File bei Non-ValueError
        assert fail["raw_response_file"] is None
