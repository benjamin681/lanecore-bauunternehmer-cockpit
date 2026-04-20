"""Tests fuer PATCH /pricing/pricelists/{id}/entries/{entry_id} (B+3.3).

Fokus: Correction-Tracking + Reviewed-Counter + Tenant-Isolation.
"""

from __future__ import annotations

import io

from app.models.pricing import SupplierPriceEntry, SupplierPriceList


def _sl():
    """Dynamischer Zugriff auf die (vom Test-Fixture evtl. gepatchte)
    SessionLocal-Factory — verhindert stale Module-Level-Binding."""
    from app.core import database

    return database.SessionLocal


def _register_and_login(c, email: str, firma: str = "T") -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": firma,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_and_seed(c, token: str, *, needs_review: bool = True) -> tuple[str, str]:
    """Upload + seedet einen Entry direkt in die DB. Gibt (pricelist_id, entry_id)."""
    import uuid

    filename = f"seed-{uuid.uuid4().hex[:8]}.pdf"
    resp = c.post(
        "/api/v1/pricing/upload",
        headers=_auth(token),
        files={"file": (filename, io.BytesIO(b"%PDF-1.4 seed"), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Review-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    assert resp.status_code == 201, resp.text
    pl_id = resp.json()["id"]

    # Einen Entry direkt seeden (bypass Parser).
    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert pl is not None
        e = SupplierPriceEntry(
            pricelist_id=pl_id,
            tenant_id=pl.tenant_id,
            article_number="3530100012",
            manufacturer="Knauf",
            product_name="GKB 2000x1250x12,5 mm",
            category="Gipskarton",
            price_net=3.00,
            currency="EUR",
            unit="€/m²",
            package_size=None,
            package_unit=None,
            pieces_per_package=None,
            effective_unit="m²",
            price_per_effective_unit=3.00,
            attributes={"thickness": "12,5mm"},
            source_page=1,
            parser_confidence=0.6,
            needs_review=needs_review,
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        entry_id = e.id
    return pl_id, entry_id


# ---------------------------------------------------------------------------
# Happy-Path
# ---------------------------------------------------------------------------

def test_entry_update_setzt_correction_applied(client):
    token = _register_and_login(client, "correction@example.com")
    pl_id, e_id = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"price_net": 3.50},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["price_net"] == 3.50
    assert body["correction_applied"] is True
    assert body["reviewed_by_user_id"] is not None
    assert body["reviewed_at"] is not None


def test_entry_update_ohne_change_setzt_kein_correction(client):
    """Wenn der Payload identische Werte schickt, bleibt correction_applied=False."""
    token = _register_and_login(client, "nochange@example.com")
    pl_id, e_id = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"price_net": 3.00},  # identisch zum Seed
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["correction_applied"] is False
    assert body["reviewed_by_user_id"] is None


def test_entry_update_empty_body_is_noop(client):
    token = _register_and_login(client, "empty@example.com")
    pl_id, e_id = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={},
    )
    assert resp.status_code == 200
    assert resp.json()["correction_applied"] is False


# ---------------------------------------------------------------------------
# Reviewed-Counter auf Parent-Pricelist
# ---------------------------------------------------------------------------

def test_entry_update_reviewed_counter_steigt_bei_needs_review_false(client):
    token = _register_and_login(client, "counter-up@example.com")
    pl_id, e_id = _upload_and_seed(client, token, needs_review=True)
    # Start-Counter pruefen
    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert (pl.entries_reviewed or 0) == 0

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"needs_review": False},
    )
    assert resp.status_code == 200

    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert pl.entries_reviewed == 1


def test_entry_update_reviewed_counter_faellt_bei_needs_review_true(client):
    """Wenn Reviewer einen Eintrag 're-opened', sinkt der Counter wieder."""
    token = _register_and_login(client, "counter-down@example.com")
    pl_id, e_id = _upload_and_seed(client, token, needs_review=False)

    # Pre-Setup: Counter auf 1 bringen, damit wir dekrementieren koennen.
    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        pl.entries_reviewed = 1
        db.commit()

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"needs_review": True},
    )
    assert resp.status_code == 200
    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert pl.entries_reviewed == 0


def test_entry_update_counter_nicht_negativ(client):
    """Wenn Counter bereits 0 ist und needs_review von True->True (kein Change),
    bleibt Counter 0. Safety: dekrement geht nicht unter 0."""
    token = _register_and_login(client, "nonneg@example.com")
    pl_id, e_id = _upload_and_seed(client, token, needs_review=False)

    # Counter auf 0 lassen. needs_review von False->True setzt Dekrement.
    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"needs_review": True},
    )
    assert resp.status_code == 200
    with _sl()() as db:
        pl = db.get(SupplierPriceList, pl_id)
        assert (pl.entries_reviewed or 0) == 0


# ---------------------------------------------------------------------------
# Tenant-Isolation
# ---------------------------------------------------------------------------

def test_entry_update_fremde_pricelist_404(client):
    """User A kann Entry von User B nicht patchen — weder via eigener noch
    fremder pricelist_id."""
    token_a = _register_and_login(client, "tenant-a@example.com", firma="A")
    _, entry_id_a = _upload_and_seed(client, token_a)

    token_b = _register_and_login(client, "tenant-b@example.com", firma="B")
    pl_id_b, _ = _upload_and_seed(client, token_b)

    # A versucht Entry von A zu patchen, aber mit Pricelist von B -> 404
    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id_b}/entries/{entry_id_a}",
        headers=_auth(token_a),
        json={"price_net": 99.0},
    )
    assert resp.status_code == 404


def test_entry_update_fremder_tenant_kann_nichts_aendern(client):
    """User B patcht Entry von User A unter A's pricelist_id -> 404."""
    token_a = _register_and_login(client, "owner-a@example.com", firma="A")
    pl_id_a, entry_id_a = _upload_and_seed(client, token_a)

    token_b = _register_and_login(client, "intruder-b@example.com", firma="B")

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id_a}/entries/{entry_id_a}",
        headers=_auth(token_b),
        json={"price_net": 99.0},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------

def test_entry_update_unbekanntes_feld_422(client):
    """extra='forbid' im Schema: unbekanntes Feld -> 422."""
    token = _register_and_login(client, "forbid@example.com")
    pl_id, e_id = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"something_invalid": 1},
    )
    assert resp.status_code == 422


def test_entry_update_price_negativ_422(client):
    token = _register_and_login(client, "negprice@example.com")
    pl_id, e_id = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"price_net": -1},
    )
    assert resp.status_code == 422


def test_entry_update_attributes_merge_ersetzt(client):
    """attributes wird KOMPLETT ersetzt, nicht gemergt (dict-Felder)."""
    token = _register_and_login(client, "attrs@example.com")
    pl_id, e_id = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/{e_id}",
        headers=_auth(token),
        json={"attributes": {"weight": "25 kg"}},
    )
    assert resp.status_code == 200
    assert resp.json()["attributes"] == {"weight": "25 kg"}
    # "thickness" aus Seed ist verschwunden
    assert "thickness" not in resp.json()["attributes"]


# ---------------------------------------------------------------------------
# Nicht-existierende IDs
# ---------------------------------------------------------------------------

def test_entry_update_nonexistent_entry_404(client):
    token = _register_and_login(client, "noentry@example.com")
    pl_id, _ = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/{pl_id}/entries/does-not-exist",
        headers=_auth(token),
        json={"price_net": 5.0},
    )
    assert resp.status_code == 404


def test_entry_update_nonexistent_pricelist_404(client):
    token = _register_and_login(client, "nopl@example.com")
    _, e_id = _upload_and_seed(client, token)

    resp = client.patch(
        f"/api/v1/pricing/pricelists/does-not-exist/entries/{e_id}",
        headers=_auth(token),
        json={"price_net": 5.0},
    )
    assert resp.status_code == 404
