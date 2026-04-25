"""B+4.9 — Customer/Project CRUD + Auto-Anlage-Hook + Tenant-Profil.

Abdeckung:
- Tenant-Profil GET/PATCH inkl. Whitespace-Strip + IBAN-Uppercase.
- Customer-CRUD: Liste, Create, Get, Patch, Delete (mit haengenden
  Projekten -> 409).
- Project-CRUD analog mit Customer-Tenant-Validierung.
- Auto-Anlage-Hook: 4 Faelle (existing/new × customer/project,
  fehlende Header-Daten).
"""
from __future__ import annotations

from app.models.customer import Customer, Project
from app.models.lv import LV
from app.models.tenant import Tenant
from app.services.customer_project_autocreate import autocreate_for_lv


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _register(c, email: str) -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": "B49Betrieb",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.core import database
    return database.SessionLocal()


def _tenant_id(c, token: str) -> str:
    return c.get("/api/v1/auth/me", headers=_auth(token)).json()["tenant_id"]


# --------------------------------------------------------------------------- #
# Tenant-Profile
# --------------------------------------------------------------------------- #
def test_tenant_profile_get_and_patch_strips_iban_whitespace(client):
    token = _register(client, "tp-1@example.com")

    # GET — Defaults
    r = client.get("/api/v1/tenant/profile", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_address_country"] == "DE"
    assert body["default_payment_terms_days"] == 14
    assert body["default_offer_validity_days"] == 30
    assert body["company_name"] is None

    # PATCH
    r = client.patch(
        "/api/v1/tenant/profile",
        headers=_auth(token),
        json={
            "company_name": "Trockenbau Mustermann GmbH",
            "company_address_street": " Beispielweg 12 ",
            "company_address_zip": "89073",
            "company_address_city": "Ulm",
            "bank_iban": "de12 3456 7890 1234 5678 90",
            "bank_bic": "MUSTDE12",
            "vat_id": "DE123456789",
            "default_payment_terms_days": 21,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["company_name"] == "Trockenbau Mustermann GmbH"
    assert body["company_address_street"] == "Beispielweg 12"
    # IBAN: Whitespace + lowercase werden normalisiert
    assert body["bank_iban"] == "DE123456789012345678 90".replace(" ", "")
    assert body["bank_bic"] == "MUSTDE12"
    assert body["default_payment_terms_days"] == 21


def test_tenant_profile_invalid_country_code_422(client):
    token = _register(client, "tp-cc@example.com")
    r = client.patch(
        "/api/v1/tenant/profile",
        headers=_auth(token),
        json={"company_address_country": "DEU"},  # 3 Zeichen → invalid
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Customer-CRUD
# --------------------------------------------------------------------------- #
def test_customer_crud_full_cycle(client):
    token = _register(client, "cust-1@example.com")

    # Liste leer
    assert client.get("/api/v1/customers", headers=_auth(token)).json() == []

    # Create
    r = client.post(
        "/api/v1/customers",
        headers=_auth(token),
        json={
            "name": "Wilma Wohnen Süd BW GmbH",
            "address_city": "Stuttgart",
            "email": "kontakt@wilma-wohnen.de",
        },
    )
    assert r.status_code == 201, r.text
    cust_id = r.json()["id"]
    assert r.json()["address_country"] == "DE"  # default

    # Get
    r = client.get(f"/api/v1/customers/{cust_id}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["name"] == "Wilma Wohnen Süd BW GmbH"

    # Patch
    r = client.patch(
        f"/api/v1/customers/{cust_id}",
        headers=_auth(token),
        json={"contact_person": "Max Müller"},
    )
    assert r.status_code == 200
    assert r.json()["contact_person"] == "Max Müller"

    # Search
    r = client.get(
        "/api/v1/customers?search=wilma",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Delete
    r = client.delete(f"/api/v1/customers/{cust_id}", headers=_auth(token))
    assert r.status_code == 204
    assert client.get(f"/api/v1/customers/{cust_id}", headers=_auth(token)).status_code == 404


def test_customer_delete_blocked_when_projects_exist(client):
    token = _register(client, "cust-block@example.com")
    cust = client.post(
        "/api/v1/customers", headers=_auth(token),
        json={"name": "X-GmbH"},
    ).json()
    proj = client.post(
        "/api/v1/projects", headers=_auth(token),
        json={"customer_id": cust["id"], "name": "Bauvorhaben Ulm"},
    ).json()
    assert proj["status"] == "draft"

    r = client.delete(f"/api/v1/customers/{cust['id']}", headers=_auth(token))
    assert r.status_code == 409


def test_customer_tenant_isolation(client):
    owner = _register(client, "cust-owner@example.com")
    cust = client.post(
        "/api/v1/customers", headers=_auth(owner),
        json={"name": "Privater Kunde"},
    ).json()

    stranger = _register(client, "cust-stranger@example.com")
    r = client.get(f"/api/v1/customers/{cust['id']}", headers=_auth(stranger))
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# Project-CRUD
# --------------------------------------------------------------------------- #
def test_project_create_validiert_customer_tenant(client):
    owner = _register(client, "proj-owner@example.com")
    stranger = _register(client, "proj-stranger@example.com")
    cust_owner = client.post(
        "/api/v1/customers", headers=_auth(owner),
        json={"name": "Owner-Customer"},
    ).json()

    # Stranger versucht ein Projekt mit fremdem Customer anzulegen
    r = client.post(
        "/api/v1/projects", headers=_auth(stranger),
        json={"customer_id": cust_owner["id"], "name": "X"},
    )
    assert r.status_code == 422


def test_project_list_filter_und_lvs_endpoint(client):
    token = _register(client, "proj-filter@example.com")
    cust = client.post(
        "/api/v1/customers", headers=_auth(token),
        json={"name": "Kunde A"},
    ).json()
    p1 = client.post(
        "/api/v1/projects", headers=_auth(token),
        json={"customer_id": cust["id"], "name": "P1", "status": "active"},
    ).json()
    client.post(
        "/api/v1/projects", headers=_auth(token),
        json={"customer_id": cust["id"], "name": "P2", "status": "draft"},
    )

    r = client.get(
        f"/api/v1/projects?customer_id={cust['id']}&status=active",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "P1"

    # /lvs leer fuer ein Projekt ohne LVs
    r = client.get(f"/api/v1/projects/{p1['id']}/lvs", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []


# --------------------------------------------------------------------------- #
# Auto-Anlage-Hook
# --------------------------------------------------------------------------- #
def _seed_lv(db, tenant_id: str, *, projekt_name: str, auftraggeber: str) -> str:
    lv = LV(
        tenant_id=tenant_id,
        projekt_name=projekt_name,
        auftraggeber=auftraggeber,
        original_dateiname="auto.pdf",
        status="review_needed",
    )
    db.add(lv)
    db.commit()
    return lv.id


def test_autocreate_neuer_customer_neues_project(client):
    token = _register(client, "auto-1@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid, projekt_name="Bauvorhaben Salach",
                         auftraggeber="Wilma Wohnen Süd BW GmbH")
        lv = db.get(LV, lv_id)
        cust, proj = autocreate_for_lv(db, lv)
        db.commit()
        db.refresh(lv)
        assert cust is not None and proj is not None
        assert cust.name == "Wilma Wohnen Süd BW GmbH"
        assert proj.name == "Bauvorhaben Salach"
        assert proj.customer_id == cust.id
        assert lv.project_id == proj.id


def test_autocreate_existierender_customer_neues_project(client):
    token = _register(client, "auto-2@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        existing = Customer(tenant_id=tid, name="Wilma Wohnen Süd BW GmbH")
        db.add(existing)
        db.commit()
        existing_id = existing.id

        lv_id = _seed_lv(db, tid, projekt_name="Anderes Bauvorhaben",
                         auftraggeber="wilma wohnen süd bw gmbh")  # case-different
        lv = db.get(LV, lv_id)
        cust, proj = autocreate_for_lv(db, lv)
        db.commit()
        assert cust.id == existing_id
        assert proj.name == "Anderes Bauvorhaben"


def test_autocreate_existierender_customer_existierendes_project(client):
    token = _register(client, "auto-3@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        existing_c = Customer(tenant_id=tid, name="Repeat-Kunde")
        db.add(existing_c)
        db.flush()
        existing_p = Project(
            tenant_id=tid, customer_id=existing_c.id, name="Repeat-Projekt"
        )
        db.add(existing_p)
        db.commit()
        existing_p_id = existing_p.id

        lv_id = _seed_lv(db, tid, projekt_name="Repeat-Projekt",
                         auftraggeber="Repeat-Kunde")
        lv = db.get(LV, lv_id)
        cust, proj = autocreate_for_lv(db, lv)
        db.commit()
        assert proj.id == existing_p_id


def test_autocreate_skip_when_no_auftraggeber(client):
    token = _register(client, "auto-4@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid, projekt_name="Foo", auftraggeber="")
        lv = db.get(LV, lv_id)
        cust, proj = autocreate_for_lv(db, lv)
        assert cust is None and proj is None
        assert lv.project_id is None
