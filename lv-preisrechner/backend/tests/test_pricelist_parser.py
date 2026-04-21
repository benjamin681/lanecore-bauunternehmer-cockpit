"""Unit-Tests + Integrations-Test für den Pricelist-Parser (Sub-Block B+2).

Scope:
- Format-Erkennung (_detect_format)
- Einheiten-Normalisierung (_normalize_unit): die 5 Regeln
- ParseResult.success_rate
- Integration: PricelistParser mit Mock-Claude gegen Mini-Fixture-PDF
- Worker: Status-Übergänge + Fehler-Handling
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from app.services.pricelist_parser import (
    ParseResult,
    PricelistParser,
    UnitInfo,
    _detect_format,
    _extract_price_per_effective_unit,
    _normalize_unit,
)


# ---------------------------------------------------------------------------
# Format-Erkennung
# ---------------------------------------------------------------------------

def test_detect_format_kemmler_by_filename():
    assert _detect_format("/tmp/kemmler-preisliste-2026-04.pdf") == "kemmler"
    assert _detect_format("/uploads/Kemmler_Ausbau_2026.pdf") == "kemmler"
    assert _detect_format("/uploads/a-liste-2026.pdf") == "kemmler"
    assert _detect_format("/uploads/a+-liste-2026.pdf") == "kemmler"


def test_detect_format_kemmler_by_supplier_hint():
    # Dateiname ohne Hinweis, aber supplier_hint explizit
    assert _detect_format("/tmp/test.pdf", supplier_hint="Kemmler") == "kemmler"
    assert _detect_format("/tmp/test.pdf", supplier_hint="kemmler Baustoffe") == "kemmler"


def test_detect_format_kemmler_by_first_page_text():
    text = "Preisliste Kemmler Baustoffe & Fliesen Neu-Ulm, Stand 04/2026"
    assert _detect_format("/tmp/generic.pdf", first_page_text=text) == "kemmler"


def test_detect_format_unknown_falls_back_to_kemmler_prompt():
    """B+4.3: unbekannte Haendler fallen auf den Kemmler-Prompt als
    generischen deutschen Preislisten-Prompt. Siehe _detect_format-
    Docstring."""
    from app.services.pricelist_parser import UNSUPPORTED_FORMAT_FALLBACK
    assert UNSUPPORTED_FORMAT_FALLBACK == "kemmler"
    assert _detect_format("/tmp/hornbach-2026.pdf") == UNSUPPORTED_FORMAT_FALLBACK
    assert _detect_format("/tmp/random.pdf", supplier_hint="Obi") == UNSUPPORTED_FORMAT_FALLBACK
    assert _detect_format("/tmp/random.pdf", first_page_text="Bauhaus AG") == UNSUPPORTED_FORMAT_FALLBACK


# ---------------------------------------------------------------------------
# Unit-Normalisierung: Die 5 Regeln
# ---------------------------------------------------------------------------

def test_normalize_unit_sack_kg():
    """R1: 25 kg/Sack + 26,54 €/Sack -> 1,06 €/kg"""
    info = _normalize_unit(
        "€/Sack", product_name="Knauf Uniflott 25 kg/Sack", price=26.54
    )
    assert info.effective_unit == "kg"
    assert info.package_size == 25.0
    assert info.package_unit == "kg"
    assert abs(info.price_per_effective_unit - 1.0616) < 0.001
    assert info.needs_review is False
    assert info.confidence >= 0.9


def test_normalize_unit_eimer_liter():
    """R3: 12,5 l/Eimer + 47,50 €/Eimer -> 3,80 €/l"""
    info = _normalize_unit(
        "€/Eimer", product_name="Dispersion weiß 12,5 l/Eimer", price=47.50
    )
    assert info.effective_unit == "l"
    assert info.package_size == 12.5
    assert info.package_unit == "l"
    assert abs(info.price_per_effective_unit - 3.80) < 0.001
    assert info.needs_review is False


def test_normalize_unit_plate_m2_direct():
    """R4: Plattenware mit direktem €/m² -> 1:1"""
    info = _normalize_unit(
        "€/m²", product_name="Knauf GKB 2000x1250x12,5 mm", price=3.00
    )
    assert info.effective_unit == "m²"
    assert info.price_per_effective_unit == 3.00
    assert info.confidence == 1.0
    assert info.needs_review is False


def test_normalize_unit_bundle_unclear_triggers_review():
    """R2: CW-Profil mit '8 St./Bd.' und BL=2600mm + Preis €/m -> unklar, Review"""
    info = _normalize_unit(
        "€/m",
        product_name="Knauf CW 50x50 BL=2600 mm - 8 St./Bd.",
        price=112.80,
    )
    assert info.needs_review is True
    assert info.pieces_per_package == 8
    assert info.package_size == 2.6  # 2600mm -> 2.6m
    assert info.confidence < 0.7
    assert "Bundpreis" in info.note or "unklar" in info.note.lower()


def test_normalize_unit_fallback_unknown_unit():
    """Unbekannte Einheit -> needs_review=True, confidence<0.5"""
    info = _normalize_unit(
        "€/Ringkartusche", product_name="Exotisches Produkt", price=19.99
    )
    assert info.needs_review is True
    assert info.confidence < 0.5
    assert info.price_per_effective_unit == 19.99  # unveraendert durchgereicht


def test_normalize_unit_stk_direct():
    info = _normalize_unit("€/Stk", product_name="Revisionsklappe 30x30", price=58.50)
    assert info.effective_unit == "Stk"
    assert info.price_per_effective_unit == 58.50
    assert info.confidence == 1.0


def test_extract_price_per_effective_unit_wrapper():
    # Convenience-Wrapper gibt nur den Preis zurueck
    p = _extract_price_per_effective_unit(
        "€/Sack", 26.54, product_name="Uniflott 25 kg/Sack"
    )
    assert abs(p - 1.0616) < 0.001


# ---------------------------------------------------------------------------
# ParseResult
# ---------------------------------------------------------------------------

def test_parse_result_default_werte_sind_null():
    r = ParseResult(pricelist_id="abc")
    assert r.total_entries == 0
    assert r.parsed_entries == 0
    assert r.needs_review_count == 0
    assert r.avg_confidence == 0.0
    assert r.success_rate == 0.0
    assert r.errors == []


def test_parse_result_success_rate():
    r = ParseResult(
        pricelist_id="abc",
        total_entries=10,
        parsed_entries=8,
        skipped_entries=2,
    )
    assert r.success_rate == 0.8


def test_parse_result_success_rate_null_safe():
    r = ParseResult(pricelist_id="abc")
    assert r.success_rate == 0.0


# ---------------------------------------------------------------------------
# Integrations-Test: PricelistParser mit Mock-Claude
# ---------------------------------------------------------------------------


def _make_mini_pdf(content_lines: list[str]) -> bytes:
    """Minimales PDF mit mehreren Text-Zeilen (für pdf_to_page_images)."""
    try:
        import fitz
    except ImportError:
        pytest.skip("pymupdf nicht installiert")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 80.0
    for line in content_lines:
        page.insert_text((50, y), line, fontsize=10)
        y += 20
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class _MockClaude:
    """Emuliert claude_client.claude.extract_json() deterministisch."""

    def __init__(self, canned_response: dict):
        self.canned = canned_response
        self.calls = 0

    def extract_json(
        self,
        *,
        system=None,
        images=None,
        user_text=None,
        force_fallback=False,
        max_tokens=None,
    ):
        self.calls += 1
        return self.canned, "claude-sonnet-4-6"


def _register_and_login(c, email: str, firma: str = "TestBetrieb") -> str:
    resp = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "Test",
            "nachname": "User",
            "firma": firma,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def test_pricelist_parser_integration_mit_mock_claude(client, tmp_path):
    """End-to-End: Upload + Parse mit Mock-Claude + Mini-PDF."""
    # 1. User + Token
    token = _register_and_login(client, "parser-int@example.com")

    # 2. Datei vorbereiten und hochladen (mit auto_parse=False!)
    pdf = _make_mini_pdf(
        [
            "Kemmler Baustoffe - Preisliste Ausbau 2026",
            "3530100012 Knauf GKB 2000x1250x12,5 mm  3,00 EUR/m²",
            "3530100027 Knauf GKF 15mm  4,43 EUR/m²",
        ]
    )
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("kemmler.pdf", io.BytesIO(pdf), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Mini-Fixture",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    assert resp.status_code == 201, resp.text
    pricelist_id = resp.json()["id"]
    assert resp.json()["status"] == "PENDING_PARSE"

    # 3. Parser direkt aufrufen mit Mock-Claude
    from app.core.database import SessionLocal
    from app.models.pricing import SupplierPriceEntry

    mock_claude = _MockClaude(
        canned_response={
            "page": 1,
            "entries": [
                {
                    "article_number": "3530100012",
                    "manufacturer": "Knauf",
                    "product_name": "GKB 2000x1250x12,5 mm",
                    "category": "Gipskarton",
                    "subcategory": "Standard",
                    "price_net": 3.00,
                    "currency": "EUR",
                    "unit": "€/m²",
                    "attributes": {
                        "dimensions": "2000x1250x12,5mm",
                        "thickness": "12,5mm",
                    },
                    "parser_confidence": 1.0,
                    "needs_review_hint": False,
                },
                {
                    "article_number": "3530100027",
                    "manufacturer": "Knauf",
                    "product_name": "GKF 15mm",
                    "category": "Gipskarton",
                    "subcategory": "Feuerschutz",
                    "price_net": 4.43,
                    "currency": "EUR",
                    "unit": "€/m²",
                    "attributes": {"thickness": "15mm"},
                    "parser_confidence": 0.95,
                    "needs_review_hint": False,
                },
                # Ein Uniflott-Sack: sollte durch _normalize_unit umgerechnet werden
                {
                    "article_number": "3400001",
                    "manufacturer": "Knauf",
                    "product_name": "Uniflott 25 kg/Sack",
                    "category": "Spachtel",
                    "price_net": 26.54,
                    "currency": "EUR",
                    "unit": "€/Sack",
                    "attributes": {"packaging": "25 kg/Sack"},
                    "parser_confidence": 0.9,
                    "needs_review_hint": False,
                },
                # Unklare Profil-Zeile: needs_review=True erwartet
                {
                    "article_number": None,
                    "manufacturer": "Knauf",
                    "product_name": "CW 50/50 BL=2600 mm - 8 St./Bd.",
                    "category": "Profile",
                    "price_net": 112.80,
                    "currency": "EUR",
                    "unit": "€/m",
                    "attributes": {"bundle_length": "2600mm", "pieces_per_bundle": 8},
                    "parser_confidence": 0.6,
                    "needs_review_hint": True,
                },
            ],
        }
    )

    with SessionLocal() as db:
        parser = PricelistParser(db=db, claude_client=mock_claude, batch_size=5)
        result = parser.parse(pricelist_id)

    assert mock_claude.calls >= 1
    assert result.parsed_entries == 4
    assert result.skipped_entries == 0
    # Von 4 Einträgen: 1 needs_review (CW-Profil)
    assert result.needs_review_count == 1
    # Durchschnittliche Confidence sollte > 0.7 sein (3 gute + 1 mittelmaessig)
    assert result.avg_confidence > 0.7

    # 4. Datenbank-Check: Entries tatsaechlich gespeichert
    with SessionLocal() as db:
        entries = (
            db.query(SupplierPriceEntry)
            .filter(SupplierPriceEntry.pricelist_id == pricelist_id)
            .all()
        )
        assert len(entries) == 4

        # Plattenware: effective_unit=m², price direkt
        gkb = next(e for e in entries if e.product_name.startswith("GKB"))
        assert gkb.effective_unit == "m²"
        assert gkb.price_per_effective_unit == 3.00
        assert gkb.needs_review is False

        # Sack-Einheit: effective_unit=kg, price = 26.54/25
        uniflott = next(
            e for e in entries if "Uniflott" in e.product_name
        )
        assert uniflott.effective_unit == "kg"
        assert uniflott.package_size == 25.0
        assert uniflott.package_unit == "kg"
        assert abs(uniflott.price_per_effective_unit - 1.0616) < 0.001

        # Bundpreis-Profil: needs_review
        cw = next(e for e in entries if "CW 50" in e.product_name)
        assert cw.needs_review is True
        assert cw.pieces_per_package == 8

        # source_page: im single-page-wrapper {"page":1, ...} kommt page=1 durch
        for e in entries:
            assert e.source_page == 1, (
                f"{e.product_name}: source_page sollte 1 sein (kam aus "
                f"single-page-wrapper), ist aber {e.source_page}"
            )


def test_source_page_aus_pages_wrapper_durchgereicht(client):
    """pages[]-Wrapper liefert pro Seite page-Nr; jeder Entry bekommt diese."""
    from app.core.database import SessionLocal
    from app.models.pricing import SupplierPriceEntry

    token = _register_and_login(client, "source-page@example.com")
    pdf = _make_mini_pdf(["Kemmler Multi-Page"])
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("multi.pdf", io.BytesIO(pdf), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Multi-Page-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    pricelist_id = resp.json()["id"]

    mock = _MockClaude(
        canned_response={
            "pages": [
                {
                    "page": 3,
                    "entries": [
                        {
                            "product_name": "Artikel-Page3-A",
                            "price_net": 10.0,
                            "unit": "€/Stk",
                            "parser_confidence": 1.0,
                        },
                        {
                            "product_name": "Artikel-Page3-B",
                            "price_net": 20.0,
                            "unit": "€/Stk",
                            "parser_confidence": 1.0,
                        },
                    ],
                },
                {
                    "page": 5,
                    "entries": [
                        {
                            "product_name": "Artikel-Page5",
                            "price_net": 30.0,
                            "unit": "€/Stk",
                            "parser_confidence": 1.0,
                        },
                    ],
                },
            ]
        }
    )
    with SessionLocal() as db:
        parser = PricelistParser(db=db, claude_client=mock)
        result = parser.parse(pricelist_id)

    assert result.parsed_entries == 3

    with SessionLocal() as db:
        entries = {
            e.product_name: e
            for e in db.query(SupplierPriceEntry).filter(
                SupplierPriceEntry.pricelist_id == pricelist_id
            )
        }
    assert entries["Artikel-Page3-A"].source_page == 3
    assert entries["Artikel-Page3-B"].source_page == 3
    assert entries["Artikel-Page5"].source_page == 5


def test_source_page_entry_eigene_page_ueberschreibt_wrapper_nicht(client):
    """Wenn Entry bereits source_page hat, wird die NICHT ueberschrieben.

    Hintergrund: Claude koennte intern eine feinere Nummer liefern (z.B.
    Doppelseite unterteilen). Wrapper-page ist nur Fallback.
    """
    from app.core.database import SessionLocal
    from app.models.pricing import SupplierPriceEntry

    token = _register_and_login(client, "source-page-override@example.com")
    pdf = _make_mini_pdf(["Kemmler"])
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("ov.pdf", io.BytesIO(pdf), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Override-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    pricelist_id = resp.json()["id"]

    mock = _MockClaude(
        canned_response={
            "pages": [
                {
                    "page": 10,
                    "entries": [
                        {
                            "product_name": "Mit-Eigener-Page",
                            "price_net": 1.0,
                            "unit": "€/Stk",
                            "parser_confidence": 1.0,
                            "source_page": 99,  # explizit anders
                        },
                    ],
                }
            ]
        }
    )
    with SessionLocal() as db:
        parser = PricelistParser(db=db, claude_client=mock)
        parser.parse(pricelist_id)

    with SessionLocal() as db:
        e = (
            db.query(SupplierPriceEntry)
            .filter(SupplierPriceEntry.pricelist_id == pricelist_id)
            .first()
        )
    assert e.source_page == 99, "Entry-eigenes source_page soll Wrapper-page gewinnen"


def test_pricelist_parser_fehlendes_pflichtfeld_wird_geskipped(client):
    """Wenn Claude einen Entry ohne price_net liefert -> skipped, nicht parsed."""
    from app.core.database import SessionLocal
    from app.models.pricing import SupplierPriceEntry

    token = _register_and_login(client, "parser-skip@example.com")
    pdf = _make_mini_pdf(["Kemmler Mini"])
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("kemmler-skip.pdf", io.BytesIO(pdf), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Skip-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    pricelist_id = resp.json()["id"]

    mock = _MockClaude(
        canned_response={
            "entries": [
                {
                    "product_name": "Validiert",
                    "price_net": 10.0,
                    "unit": "€/Stk",
                    "parser_confidence": 1.0,
                },
                # Fehlender product_name -> skip
                {"price_net": 5.0, "unit": "€/Stk"},
                # Preis 0 -> skip
                {"product_name": "Nullpreis", "price_net": 0, "unit": "€/Stk"},
                # Fehlende Einheit -> skip
                {"product_name": "ohne Einheit", "price_net": 3.0, "unit": ""},
            ],
        }
    )
    with SessionLocal() as db:
        parser = PricelistParser(db=db, claude_client=mock)
        result = parser.parse(pricelist_id)

    assert result.parsed_entries == 1
    assert result.skipped_entries == 3


# ---------------------------------------------------------------------------
# Worker: Status-Transitions
# ---------------------------------------------------------------------------

def test_worker_setzt_error_bei_nicht_vorhandener_datei(client):
    """Der Worker sollte bei fehlender Datei ERROR setzen, nicht crashen."""
    token = _register_and_login(client, "worker-err@example.com")
    # Upload durchführen
    pdf = _make_mini_pdf(["irrelevant"])
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("kemmler-err.pdf", io.BytesIO(pdf), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Err-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    pricelist_id = resp.json()["id"]

    # Datei manuell loeschen, damit Parser fehlschlaegt
    from app.core.database import SessionLocal
    from app.models.pricing import SupplierPriceList

    with SessionLocal() as db:
        pl = db.get(SupplierPriceList, pricelist_id)
        Path(pl.source_file_path).unlink(missing_ok=True)

    # Worker laufen lassen
    from app.workers.pricelist_parse_worker import run_pricelist_parse

    run_pricelist_parse(pricelist_id)

    # Status sollte jetzt ERROR sein, parse_error gefuellt
    with SessionLocal() as db:
        pl = db.get(SupplierPriceList, pricelist_id)
        assert pl.status == "ERROR"
        assert pl.parse_error is not None
        assert "fehlt" in pl.parse_error.lower() or "not found" in pl.parse_error.lower()


def test_trigger_parse_endpoint_nur_aus_pending_oder_error(client):
    """Der POST /parse-Trigger soll aus PARSED nicht akzeptiert werden."""
    token = _register_and_login(client, "trigger@example.com")
    pdf = _make_mini_pdf(["x"])
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("t.pdf", io.BytesIO(pdf), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Trigger-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    pid = resp.json()["id"]

    # Status direkt in DB auf PARSED setzen, dann Trigger testen
    from app.core.database import SessionLocal
    from app.models.pricing import PricelistStatus, SupplierPriceList

    with SessionLocal() as db:
        pl = db.get(SupplierPriceList, pid)
        pl.status = PricelistStatus.PARSED.value
        db.commit()

    resp = client.post(
        f"/api/v1/pricing/pricelists/{pid}/parse",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


def test_review_needed_endpoint_sortiert_nach_confidence(client):
    """GET /review-needed sollte niedrigste Confidence zuerst liefern."""
    token = _register_and_login(client, "review@example.com")
    pdf = _make_mini_pdf(["x"])
    resp = client.post(
        "/api/v1/pricing/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("review.pdf", io.BytesIO(pdf), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Review-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    pid = resp.json()["id"]

    # Manuelle Entries einfuegen
    from app.core.database import SessionLocal
    from app.models.pricing import SupplierPriceEntry

    with SessionLocal() as db:
        for i, conf in enumerate([0.3, 0.9, 0.5, 0.95]):
            e = SupplierPriceEntry(
                pricelist_id=pid,
                tenant_id=resp.json()["tenant_id"],
                product_name=f"Entry {i}",
                price_net=10.0 + i,
                unit="€/Stk",
                effective_unit="Stk",
                price_per_effective_unit=10.0 + i,
                parser_confidence=conf,
                needs_review=(conf < 0.7),
            )
            db.add(e)
        db.commit()

    r = client.get(
        f"/api/v1/pricing/pricelists/{pid}/review-needed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    entries = r.json()
    # Nur 2 mit needs_review=True (conf 0.3 und 0.5)
    assert len(entries) == 2
    # Sortiert ASC by confidence -> 0.3 zuerst
    assert entries[0]["parser_confidence"] == 0.3
    assert entries[1]["parser_confidence"] == 0.5
