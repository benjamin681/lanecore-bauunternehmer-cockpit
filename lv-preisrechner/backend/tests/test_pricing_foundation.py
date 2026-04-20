"""Foundation-Tests für die Pricing-API (B+1).

Testet:
- Upload-Endpoint (Datei speichern, DB-Entry, SHA256-Duplikate)
- Listing mit Tenant-Isolation (zwei Tenants sehen sich nicht)
- Pricelist-Detail + Soft-Delete + Activate (nur eine aktiv je Supplier)
- TenantPriceOverride CRUD
- TenantDiscountRule CRUD
"""

from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _register_and_login(c, email: str, firma: str = "TestBetrieb") -> str:
    """Registriert einen User und gibt den Bearer-Token zurück."""
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_file(
    c,
    token: str,
    *,
    filename: str = "kemmler-2026-04.pdf",
    content: bytes = b"%PDF-1.4 dummy content",
    supplier_name: str = "Kemmler",
    list_name: str = "Ausbau 2026-04",
    valid_from: str = "2026-04-01",
    supplier_location: str | None = "Neu-Ulm",
    valid_until: str | None = None,
):
    data = {
        "supplier_name": supplier_name,
        "list_name": list_name,
        "valid_from": valid_from,
    }
    if supplier_location is not None:
        data["supplier_location"] = supplier_location
    if valid_until is not None:
        data["valid_until"] = valid_until
    return c.post(
        "/api/v1/pricing/upload",
        headers=_auth(token),
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
        data=data,
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
def test_upload_speichert_datei_und_erstellt_pricelist(client):
    token = _register_and_login(client, "upload1@example.com")
    r = _upload_file(client, token)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PENDING_PARSE"
    assert body["supplier_name"] == "Kemmler"
    assert body["supplier_location"] == "Neu-Ulm"
    assert body["is_active"] is False
    assert len(body["source_file_hash"]) == 64  # SHA256 hex


def test_upload_duplikat_wird_abgewiesen(client):
    token = _register_and_login(client, "upload-dup@example.com")
    r1 = _upload_file(client, token, content=b"exact-same-content-0xdeadbeef")
    assert r1.status_code == 201
    r2 = _upload_file(client, token, content=b"exact-same-content-0xdeadbeef")
    assert r2.status_code == 409
    assert "bereits hochgeladen" in r2.json()["detail"]


def test_upload_abweist_unerlaubte_dateiformate(client):
    token = _register_and_login(client, "upload-ext@example.com")
    r = _upload_file(client, token, filename="virus.exe")
    assert r.status_code == 400


def test_upload_valid_until_vor_valid_from_wird_abgewiesen(client):
    token = _register_and_login(client, "upload-date@example.com")
    r = _upload_file(
        client,
        token,
        valid_from="2026-06-01",
        valid_until="2026-04-01",
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Listing + Tenant-Isolation
# ---------------------------------------------------------------------------
def test_listing_nur_eigene_pricelists_sichtbar(client):
    t1 = _register_and_login(client, "tenant1@example.com", firma="Firma A")
    _upload_file(client, t1, content=b"a-content", supplier_name="Kemmler")
    _upload_file(client, t1, content=b"b-content", supplier_name="Hornbach")

    t2 = _register_and_login(client, "tenant2@example.com", firma="Firma B")
    _upload_file(client, t2, content=b"c-content", supplier_name="Kemmler")

    # Tenant 1 sieht seine 2
    r = client.get("/api/v1/pricing/pricelists", headers=_auth(t1))
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert all(e["supplier_name"] in ("Kemmler", "Hornbach") for e in data)

    # Tenant 2 sieht nur seine 1
    r = client.get("/api/v1/pricing/pricelists", headers=_auth(t2))
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["supplier_name"] == "Kemmler"


def test_listing_filter_supplier_name(client):
    t = _register_and_login(client, "filter1@example.com")
    _upload_file(client, t, content=b"a", supplier_name="Kemmler")
    _upload_file(client, t, content=b"b", supplier_name="Hornbach")
    r = client.get(
        "/api/v1/pricing/pricelists?supplier_name=Kemmler", headers=_auth(t)
    )
    assert r.status_code == 200
    names = [e["supplier_name"] for e in r.json()]
    assert names == ["Kemmler"]


# ---------------------------------------------------------------------------
# Detail + Soft-Delete
# ---------------------------------------------------------------------------
def test_detail_nicht_vorhanden_gibt_404(client):
    t = _register_and_login(client, "detail-404@example.com")
    r = client.get(
        "/api/v1/pricing/pricelists/non-existent-id", headers=_auth(t)
    )
    assert r.status_code == 404


def test_detail_fremder_tenant_gibt_404(client):
    t1 = _register_and_login(client, "tenantX@example.com", firma="X")
    up = _upload_file(client, t1, content=b"x-content")
    pid = up.json()["id"]

    t2 = _register_and_login(client, "tenantY@example.com", firma="Y")
    r = client.get(f"/api/v1/pricing/pricelists/{pid}", headers=_auth(t2))
    assert r.status_code == 404  # Kein Info-Leak


def test_soft_delete_setzt_status_archived(client):
    t = _register_and_login(client, "soft-del@example.com")
    up = _upload_file(client, t, content=b"to-archive")
    pid = up.json()["id"]

    r = client.delete(f"/api/v1/pricing/pricelists/{pid}", headers=_auth(t))
    assert r.status_code == 200
    assert r.json()["status"] == "ARCHIVED"
    assert r.json()["is_active"] is False

    # Datensatz ist noch vorhanden
    r = client.get(f"/api/v1/pricing/pricelists/{pid}", headers=_auth(t))
    assert r.status_code == 200
    assert r.json()["status"] == "ARCHIVED"


# ---------------------------------------------------------------------------
# Activate: nur eine Preisliste pro Lieferant aktiv
# ---------------------------------------------------------------------------
def test_activate_deaktiviert_andere_vom_selben_lieferant(client):
    t = _register_and_login(client, "activate@example.com")
    a = _upload_file(client, t, content=b"kemmler-v1", supplier_name="Kemmler").json()
    b = _upload_file(client, t, content=b"kemmler-v2", supplier_name="Kemmler").json()
    c_ = _upload_file(
        client, t, content=b"hornbach-v1", supplier_name="Hornbach"
    ).json()

    # Aktiviere a — b soll nicht aktiv sein, c_ (anderer Lieferant) unveraendert
    r = client.post(
        f"/api/v1/pricing/pricelists/{a['id']}/activate", headers=_auth(t)
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    # Jetzt b aktivieren — a soll deaktivieren
    r = client.post(
        f"/api/v1/pricing/pricelists/{b['id']}/activate", headers=_auth(t)
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    r = client.get(f"/api/v1/pricing/pricelists/{a['id']}", headers=_auth(t))
    assert r.json()["is_active"] is False

    # c_ (Hornbach) bleibt unveraendert (is_active=False, weil nie aktiviert)
    r = client.get(f"/api/v1/pricing/pricelists/{c_['id']}", headers=_auth(t))
    assert r.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Tenant Price Overrides
# ---------------------------------------------------------------------------
def test_override_create_und_listing(client):
    t = _register_and_login(client, "override1@example.com")
    r = client.post(
        "/api/v1/pricing/overrides",
        headers=_auth(t),
        json={
            "article_number": "3530100012",
            "manufacturer": "Knauf",
            "override_price": 2.85,
            "unit": "m²",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "notes": "Rahmenvertrag 2026",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["override_price"] == 2.85

    r = client.get("/api/v1/pricing/overrides", headers=_auth(t))
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Filter
    r = client.get(
        "/api/v1/pricing/overrides?article_number=3530100012", headers=_auth(t)
    )
    assert len(r.json()) == 1
    r = client.get(
        "/api/v1/pricing/overrides?article_number=nope", headers=_auth(t)
    )
    assert r.json() == []


def test_override_tenant_isolation(client):
    t1 = _register_and_login(client, "ov-t1@example.com", firma="T1")
    t2 = _register_and_login(client, "ov-t2@example.com", firma="T2")
    client.post(
        "/api/v1/pricing/overrides",
        headers=_auth(t1),
        json={
            "article_number": "ABC",
            "override_price": 10.0,
            "unit": "Stk",
            "valid_from": "2026-01-01",
        },
    )
    r = client.get("/api/v1/pricing/overrides", headers=_auth(t2))
    assert r.json() == []


def test_override_delete(client):
    t = _register_and_login(client, "ov-del@example.com")
    r = client.post(
        "/api/v1/pricing/overrides",
        headers=_auth(t),
        json={
            "article_number": "XYZ",
            "override_price": 1.0,
            "unit": "m",
            "valid_from": "2026-01-01",
        },
    )
    oid = r.json()["id"]
    r = client.delete(f"/api/v1/pricing/overrides/{oid}", headers=_auth(t))
    assert r.status_code == 204
    r = client.get("/api/v1/pricing/overrides", headers=_auth(t))
    assert r.json() == []


def test_override_invalid_price_rejected(client):
    t = _register_and_login(client, "ov-inv@example.com")
    r = client.post(
        "/api/v1/pricing/overrides",
        headers=_auth(t),
        json={
            "article_number": "ABC",
            "override_price": -1.0,
            "unit": "Stk",
            "valid_from": "2026-01-01",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Tenant Discount Rules
# ---------------------------------------------------------------------------
def test_discount_rule_create_und_listing(client):
    t = _register_and_login(client, "disc1@example.com")
    r = client.post(
        "/api/v1/pricing/discount-rules",
        headers=_auth(t),
        json={
            "supplier_name": "Kemmler",
            "discount_percent": 12.5,
            "category": "Gipskarton",
            "valid_from": "2026-01-01",
            "valid_until": "2026-12-31",
            "notes": "Rahmenrabatt",
        },
    )
    assert r.status_code == 201, r.text

    r = client.get("/api/v1/pricing/discount-rules", headers=_auth(t))
    assert len(r.json()) == 1
    assert r.json()[0]["discount_percent"] == 12.5


def test_discount_rule_percent_range(client):
    t = _register_and_login(client, "disc-range@example.com")
    for bad_pct in (-5, 150):
        r = client.post(
            "/api/v1/pricing/discount-rules",
            headers=_auth(t),
            json={
                "supplier_name": "Kemmler",
                "discount_percent": bad_pct,
                "valid_from": "2026-01-01",
            },
        )
        assert r.status_code == 422


def test_discount_rule_delete(client):
    t = _register_and_login(client, "disc-del@example.com")
    r = client.post(
        "/api/v1/pricing/discount-rules",
        headers=_auth(t),
        json={
            "supplier_name": "Hornbach",
            "discount_percent": 5.0,
            "valid_from": "2026-01-01",
        },
    )
    rid = r.json()["id"]
    r = client.delete(f"/api/v1/pricing/discount-rules/{rid}", headers=_auth(t))
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# Altes Modell bleibt unberuehrt — Smoke-Test
# ---------------------------------------------------------------------------
def test_altes_price_lists_api_weiter_erreichbar(client):
    t = _register_and_login(client, "legacy@example.com")
    r = client.get("/api/v1/price-lists", headers=_auth(t))
    # Alte API liefert Liste (leer fuer neuen User) — 200, nicht 404
    assert r.status_code == 200
    assert r.json() == []
