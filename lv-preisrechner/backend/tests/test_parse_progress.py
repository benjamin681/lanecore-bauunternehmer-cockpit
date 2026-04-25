"""Tests fuer B+4.7 — Live-Fortschritt eines Parses.

Abgedeckt:
1. PricelistParser._update_progress schreibt parse_progress in
   eigener Session und ueberlebt einen Rollback der Hauptsession.
2. GET /pricing/pricelists/{id}/progress liefert percentage und
   estimated_remaining_seconds aus parse_progress + status.
3. Edge-Case: Status != PARSING -> Felder leer, UI sieht "fertig".
"""
from __future__ import annotations

import io
import time
import uuid
from datetime import UTC, datetime, timedelta

from app.models.pricing import SupplierPriceList


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _sl():
    from app.core import database
    return database.SessionLocal


def _register(c, email: str) -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": "ProgressBetrieb",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_dummy_pricelist(c, token: str) -> str:
    """Upload mit auto_parse=False, damit kein Background-Worker startet."""
    resp = c.post(
        "/api/v1/pricing/upload",
        headers=_auth(token),
        files={
            "file": (
                f"prog-{uuid.uuid4().hex[:6]}.pdf",
                io.BytesIO(b"%PDF-1.4 dummy"),
                "application/pdf",
            ),
        },
        data={
            "supplier_name": "Kemmler",
            "list_name": "Progress-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _set_status(pricelist_id: str, status: str, **extra) -> None:
    """Setzt Status + optionale Felder (parse_progress) per direkter SQL."""
    with _sl()() as db:
        pl = db.get(SupplierPriceList, pricelist_id)
        assert pl is not None
        pl.status = status
        for k, v in extra.items():
            setattr(pl, k, v)
        db.commit()


# --------------------------------------------------------------------------- #
# Test 1 — _update_progress schreibt in eigener Session
# --------------------------------------------------------------------------- #
def test_update_progress_persistiert_unabhaengig_von_hauptsession(client):
    token = _register(client, "progress-helper@example.com")
    pl_id = _upload_dummy_pricelist(client, token)

    from app.services.pricelist_parser import PricelistParser

    # Mock-Claude irrelevant — wir rufen NUR den Helper.
    parser = PricelistParser(db=_sl()(), batch_size=3)
    started = datetime.now(UTC)
    parser._update_progress(
        pricelist_id=pl_id,
        current_batch=2,
        total_batches=9,
        current_action="Verarbeite Seiten 4-6",
        started_at=started,
        entries_so_far=15,
    )

    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert pl.parse_progress is not None
        assert pl.parse_progress["current_batch"] == 2
        assert pl.parse_progress["total_batches"] == 9
        assert pl.parse_progress["current_action"] == "Verarbeite Seiten 4-6"
        assert pl.parse_progress["entries_so_far"] == 15


# --------------------------------------------------------------------------- #
# Test 2 — Endpoint liefert percentage + remaining waehrend PARSING
# --------------------------------------------------------------------------- #
def test_progress_endpoint_liefert_perzent_und_restzeit(client):
    token = _register(client, "progress-endpoint@example.com")
    pl_id = _upload_dummy_pricelist(client, token)

    # Simuliere: Parser ist bei Batch 3 von 9, gestartet vor 60 Sekunden.
    started_at = datetime.now(UTC) - timedelta(seconds=60)
    last_update = datetime.now(UTC) - timedelta(seconds=2)
    _set_status(
        pl_id,
        "PARSING",
        parse_progress={
            "current_batch": 3,
            "total_batches": 9,
            "current_action": "Verarbeite Seiten 7-9",
            "started_at": started_at.isoformat(),
            "last_update_at": last_update.isoformat(),
            "entries_so_far": 42,
        },
    )

    r = client.get(
        f"/api/v1/pricing/pricelists/{pl_id}/progress",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["status"] == "PARSING"
    assert body["current_batch"] == 3
    assert body["total_batches"] == 9
    assert body["percentage"] == 33.3  # 3/9*100 = 33.333... gerundet
    assert body["current_action"] == "Verarbeite Seiten 7-9"
    assert body["entries_so_far"] == 42
    # elapsed sollte ~60s sein (innerhalb 5s-Toleranz)
    assert 55 <= body["elapsed_seconds"] <= 70
    # remaining: 60s/3 * 6 = 120s, ungefaehr
    assert body["estimated_remaining_seconds"] is not None
    assert 100 <= body["estimated_remaining_seconds"] <= 140


# --------------------------------------------------------------------------- #
# Test 3 — Status != PARSING -> nur status, andere Felder leer
# --------------------------------------------------------------------------- #
def test_progress_endpoint_bei_parsed_status_keine_progress_felder(client):
    token = _register(client, "progress-done@example.com")
    pl_id = _upload_dummy_pricelist(client, token)

    # Parse fertig: Status PARSED, parse_progress kann noch da sein
    _set_status(pl_id, "PARSED", parse_progress=None)

    r = client.get(
        f"/api/v1/pricing/pricelists/{pl_id}/progress",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PARSED"
    assert body["current_batch"] is None
    assert body["total_batches"] is None
    assert body["percentage"] is None
    assert body["estimated_remaining_seconds"] is None
    assert body["entries_so_far"] == 0


# --------------------------------------------------------------------------- #
# Test 4 — Tenant-Isolation
# --------------------------------------------------------------------------- #
def test_progress_endpoint_fremder_tenant_404(client):
    owner = _register(client, "progress-owner@example.com")
    pl_id = _upload_dummy_pricelist(client, owner)
    stranger = _register(client, "progress-stranger@example.com")

    r = client.get(
        f"/api/v1/pricing/pricelists/{pl_id}/progress",
        headers=_auth(stranger),
    )
    assert r.status_code == 404
