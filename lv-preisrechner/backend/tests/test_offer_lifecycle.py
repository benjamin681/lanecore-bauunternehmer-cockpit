"""B+4.11 — Offer-Lifecycle Tests.

Abdeckung:
1. Offer-Erstellung mit korrektem Snapshot (netto/brutto/positions/format).
2. Status-Wechsel mit Audit-Trail-Eintraegen.
3. valid_until = sent_date + tenant.default_offer_validity_days bei SENT.
4. Tenant-Isolation: anderer Tenant bekommt 404.
5. Auto-Numerierung A-yymmdd-NN pro Tenant pro Tag.
6. Ungueltiger Status-Wechsel -> 409.
7. PDF-Generierung in beiden Formaten (eigenes Layout + Original-LV).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.models.lv import LV
from app.models.offer import Offer, OfferStatusChange
from app.models.position import Position


# --------------------------------------------------------------------------- #
# Helpers (analog zu test_customer_project.py)
# --------------------------------------------------------------------------- #
def _register(c, email: str) -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": "OfferBetrieb",
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


def _seed_lv(
    db,
    tenant_id: str,
    *,
    projekt_name: str = "Test-Bau",
    auftraggeber: str = "Wilma GmbH",
    angebotssumme: float = 12345.67,
    positionen: int = 17,
    original_pdf_bytes: bytes | None = None,
    with_positions: bool = False,
) -> str:
    lv = LV(
        tenant_id=tenant_id,
        projekt_name=projekt_name,
        auftraggeber=auftraggeber,
        original_dateiname="test.pdf",
        status="calculated",
        positionen_gesamt=positionen,
        positionen_gematcht=positionen,
        angebotssumme_netto=angebotssumme,
        original_pdf_bytes=original_pdf_bytes,
    )
    db.add(lv)
    db.commit()
    if with_positions:
        db.add(
            Position(
                lv_id=lv.id,
                reihenfolge=0,
                oz="01.01",
                titel="Trockenbauwand W112",
                kurztext="Trennwand 100mm GKB doppelt",
                menge=10.0,
                einheit="m²",
                ep=50.0,
                gp=500.0,
            )
        )
        db.commit()
    return lv.id


def _set_validity(c, token: str, days: int) -> None:
    r = c.patch(
        "/api/v1/tenant/profile",
        headers=_auth(token),
        json={"default_offer_validity_days": days},
    )
    assert r.status_code == 200, r.text


# --------------------------------------------------------------------------- #
# 1. Offer-Erstellung mit Snapshot
# --------------------------------------------------------------------------- #
def test_create_offer_snapshots_lv_sums_and_format(client):
    token = _register(client, "off-1@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid, angebotssumme=10_000.00, positionen=5)

    r = client.post(
        f"/api/v1/lvs/{lv_id}/offers",
        headers=_auth(token),
        json={"pdf_format": "eigenes_layout", "internal_notes": "Erstangebot"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["lv_id"] == lv_id
    assert body["status"] == "draft"
    assert body["betrag_netto"] == 10000.00
    # 19% USt -> 11900.00
    assert body["betrag_brutto"] == 11900.00
    assert body["position_count"] == 5
    assert body["pdf_format"] == "eigenes_layout"
    assert body["internal_notes"] == "Erstangebot"
    assert body["sent_date"] is None
    assert body["valid_until"] is None
    # offer_number-Format
    assert body["offer_number"].startswith("A-")
    assert body["offer_number"].endswith("-01")

    # Initialer Audit-Trail-Eintrag wurde geschrieben
    detail = client.get(
        f"/api/v1/offers/{body['id']}", headers=_auth(token)
    ).json()
    assert detail["status_history"]
    assert detail["status_history"][0]["new_status"] == "draft"
    assert detail["status_history"][0]["old_status"] is None


# --------------------------------------------------------------------------- #
# 2. Status-Wechsel mit Audit-Trail
# --------------------------------------------------------------------------- #
def test_status_transitions_and_audit_trail(client):
    token = _register(client, "off-2@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid)
    create = client.post(
        f"/api/v1/lvs/{lv_id}/offers",
        headers=_auth(token),
        json={},
    ).json()
    oid = create["id"]

    # draft -> sent
    r = client.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "sent", "reason": "per Mail an Bauleitung"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent"
    assert r.json()["sent_date"] is not None

    # sent -> accepted
    r = client.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "accepted"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "accepted"
    assert body["accepted_date"] is not None

    # Audit-History komplett
    history = body["status_history"]
    new_statuses = [h["new_status"] for h in history]
    # Order DESC: accepted, sent, draft
    assert new_statuses == ["accepted", "sent", "draft"]
    assert history[1]["reason"] == "per Mail an Bauleitung"


# --------------------------------------------------------------------------- #
# 3. valid_until aus Tenant-Profil
# --------------------------------------------------------------------------- #
def test_valid_until_derived_from_tenant_validity_days(client):
    token = _register(client, "off-3@example.com")
    _set_validity(client, token, 45)
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid)
    oid = client.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token), json={}
    ).json()["id"]
    today = datetime.now(UTC).date()

    r = client.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "sent", "on_date": today.isoformat()},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sent_date"] == today.isoformat()
    assert body["valid_until"] == (today + timedelta(days=45)).isoformat()


# --------------------------------------------------------------------------- #
# 4. Tenant-Isolation
# --------------------------------------------------------------------------- #
def test_tenant_isolation_other_tenant_404(client):
    a = _register(client, "off-a@example.com")
    b = _register(client, "off-b@example.com")
    tid_a = _tenant_id(client, a)
    with _db() as db:
        lv_id = _seed_lv(db, tid_a, projekt_name="Geheim")
    oid = client.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(a), json={}
    ).json()["id"]

    # Tenant B sieht weder das LV noch die Offer
    assert client.get(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(b)
    ).status_code == 404
    assert client.get(
        f"/api/v1/offers/{oid}", headers=_auth(b)
    ).status_code == 404
    assert client.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(b),
        json={"status": "sent"},
    ).status_code == 404


# --------------------------------------------------------------------------- #
# 5. Auto-Numerierung pro Tenant pro Tag
# --------------------------------------------------------------------------- #
def test_offer_number_sequence_per_tenant_per_day(client):
    a = _register(client, "off-num-a@example.com")
    b = _register(client, "off-num-b@example.com")
    tid_a = _tenant_id(client, a)
    tid_b = _tenant_id(client, b)
    with _db() as db:
        lv_a = _seed_lv(db, tid_a)
        lv_b = _seed_lv(db, tid_b)

    nums_a = []
    for _ in range(3):
        r = client.post(
            f"/api/v1/lvs/{lv_a}/offers", headers=_auth(a), json={}
        )
        assert r.status_code == 201, r.text
        nums_a.append(r.json()["offer_number"])

    # Sequenz steigt pro Tenant: -01, -02, -03
    assert [n[-2:] for n in nums_a] == ["01", "02", "03"]

    # Anderer Tenant beginnt wieder bei -01
    r = client.post(
        f"/api/v1/lvs/{lv_b}/offers", headers=_auth(b), json={}
    )
    assert r.status_code == 201
    assert r.json()["offer_number"].endswith("-01")

    # Format A-yymmdd-NN
    today = datetime.now(UTC).date()
    expected_prefix = f"A-{today.strftime('%y%m%d')}-"
    assert all(n.startswith(expected_prefix) for n in nums_a)


# --------------------------------------------------------------------------- #
# 6. Ungueltiger Status-Wechsel
# --------------------------------------------------------------------------- #
def test_invalid_status_transition_returns_409(client):
    token = _register(client, "off-inv@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid)
    oid = client.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token), json={}
    ).json()["id"]

    # draft -> accepted ist nicht erlaubt (muss erst sent)
    r = client.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "accepted"},
    )
    assert r.status_code == 409, r.text
    assert "draft" in r.json()["detail"]
    assert "accepted" in r.json()["detail"]

    # Erstmal draft -> rejected -> dann waere alles weiter blockiert
    client.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "rejected"},
    )
    r = client.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "sent"},
    )
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# 7. PDF-Generation in beiden Formaten
# --------------------------------------------------------------------------- #
def _minimal_pdf_bytes() -> bytes:
    """Erzeugt ein minimal valides 1-Seiten-PDF via PyMuPDF."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "01.01 Trockenbauwand")
    out = doc.tobytes()
    doc.close()
    return out


def test_pdf_generation_eigenes_layout(client):
    token = _register(client, "off-pdf-1@example.com")
    # Briefkopf setzen, sonst kann Angebots-PDF leer sein
    client.patch(
        "/api/v1/tenant/profile",
        headers=_auth(token),
        json={
            "company_name": "Trockenbau Test GmbH",
            "company_address_street": "Teststr 1",
            "company_address_zip": "12345",
            "company_address_city": "Teststadt",
        },
    )
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid, with_positions=True)
    oid = client.post(
        f"/api/v1/lvs/{lv_id}/offers",
        headers=_auth(token),
        json={"pdf_format": "eigenes_layout"},
    ).json()["id"]

    r = client.get(f"/api/v1/offers/{oid}/pdf", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    # Filename = Offer-Nummer
    assert "A-" in r.headers["content-disposition"]


def test_pdf_generation_original_lv_filled_format(client):
    token = _register(client, "off-pdf-2@example.com")
    tid = _tenant_id(client, token)
    pdf = _minimal_pdf_bytes()
    with _db() as db:
        lv_id = _seed_lv(db, tid, original_pdf_bytes=pdf)
    oid = client.post(
        f"/api/v1/lvs/{lv_id}/offers",
        headers=_auth(token),
        json={"pdf_format": "original_lv_filled"},
    ).json()["id"]

    r = client.get(f"/api/v1/offers/{oid}/pdf", headers=_auth(token))
    # Original-Filling erfordert Punkt-Linien-Spalten — minimales PDF hat
    # keine. Service raised dann LVOriginalFilledError mit klarer Message,
    # was wir als 422 sehen. Wichtig: NICHT 500.
    assert r.status_code in (200, 422), r.text
    if r.status_code == 200:
        assert r.content[:4] == b"%PDF"


# --------------------------------------------------------------------------- #
# 8. lv-summary fuer LV-Liste
# --------------------------------------------------------------------------- #
def test_lv_summary_aggregates_per_lv(client):
    token = _register(client, "off-sum@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_a = _seed_lv(db, tid, projekt_name="A")
        lv_b = _seed_lv(db, tid, projekt_name="B")
        # LV C: keine Offers — kommt nicht in der Summary vor
        _seed_lv(db, tid, projekt_name="C")
    # 2 Offers fuer A, 1 fuer B
    client.post(f"/api/v1/lvs/{lv_a}/offers", headers=_auth(token), json={})
    client.post(f"/api/v1/lvs/{lv_a}/offers", headers=_auth(token), json={})
    client.post(f"/api/v1/lvs/{lv_b}/offers", headers=_auth(token), json={})

    r = client.get("/api/v1/offers/lv-summary", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body[lv_a]["offer_count"] == 2
    assert body[lv_b]["offer_count"] == 1
    assert body[lv_a]["latest_status"] == "draft"
    assert body[lv_a]["latest_offer_number"].startswith("A-")


# --------------------------------------------------------------------------- #
# Bonus: Liste-Endpoint
# --------------------------------------------------------------------------- #
def test_list_offers_for_lv_orders_by_created_desc(client):
    token = _register(client, "off-list@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv(db, tid)
    n1 = client.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token), json={}
    ).json()["offer_number"]
    n2 = client.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token), json={}
    ).json()["offer_number"]

    r = client.get(f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    # neueste zuerst
    assert body[0]["offer_number"] == n2
    assert body[1]["offer_number"] == n1
