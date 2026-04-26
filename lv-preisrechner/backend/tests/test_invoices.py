"""B+4.13 — Invoice + Dunning + Finance Tests.

Abdeckung:
1. Invoice aus accepted Offer mit korrektem Snapshot.
2. Status-Wechsel mit Audit-Trail + sent_date + due_date.
3. Auto-Numerierung R-yyyy-NN pro Tenant pro Jahr (UNIQUE).
4. Teilzahlung -> partially_paid.
5. Restzahlung -> paid.
6. check_overdue setzt sent auf overdue.
7. Dunning Stufe 1 + 2 + 3, korrekte Fristen + Gebuehren.
8. Tenant-Isolation.
9. Finance overview Aggregate.
10. PDF-Generation (Invoice + Dunning).
11. Email-Compose Bonus.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.models.invoice import Dunning, Invoice, InvoiceStatus, InvoiceStatusChange
from app.models.lv import LV
from app.models.position import Position


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
            "firma": "InvoiceBetrieb",
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


def _seed_lv_with_positions(db, tenant_id: str, *, sum_netto: float = 1_000.0) -> str:
    lv = LV(
        tenant_id=tenant_id,
        projekt_name="Invoice-Test-Bau",
        auftraggeber="Wilma GmbH",
        original_dateiname="t.pdf",
        status="calculated",
        positionen_gesamt=2,
        positionen_gematcht=2,
        angebotssumme_netto=sum_netto,
    )
    db.add(lv)
    db.flush()
    db.add(
        Position(
            lv_id=lv.id, reihenfolge=0, oz="01.01",
            kurztext="W112 Wand", menge=10.0, einheit="m²", ep=80.0, gp=800.0,
        )
    )
    db.add(
        Position(
            lv_id=lv.id, reihenfolge=1, oz="01.02",
            kurztext="UA-Profil", menge=20.0, einheit="m", ep=10.0, gp=200.0,
        )
    )
    db.commit()
    return lv.id


def _create_accepted_offer(c, token: str, lv_id: str) -> str:
    oid = c.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token), json={}
    ).json()["id"]
    c.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token), json={"status": "sent"},
    )
    c.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token), json={"status": "accepted"},
    )
    return oid


def _set_payment_terms(c, token: str, days: int) -> None:
    c.patch(
        "/api/v1/tenant/profile",
        headers=_auth(token),
        json={"default_payment_terms_days": days},
    )


# --------------------------------------------------------------------------- #
# 1. Invoice aus accepted Offer mit Snapshot
# --------------------------------------------------------------------------- #
def test_create_invoice_from_accepted_offer_snapshots_amounts(client):
    token = _register(client, "inv-1@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid, sum_netto=1000.0)
    oid = _create_accepted_offer(client, token, lv_id)

    r = client.post(
        f"/api/v1/offers/{oid}/invoice",
        headers=_auth(token),
        json={"internal_notes": "Schlussrechnung Testbau"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["invoice_number"].startswith("R-")
    assert body["invoice_number"].endswith("-01")
    assert body["status"] == "draft"
    assert body["invoice_type"] == "schlussrechnung"
    assert body["betrag_netto"] == 1000.0
    assert body["betrag_ust"] == 190.0  # 19%
    assert body["betrag_brutto"] == 1190.0
    assert body["position_count"] == 2
    assert body["source_offer_id"] == oid
    assert len(body["status_history"]) == 1
    assert body["status_history"][0]["new_status"] == "draft"
    assert body["status_history"][0]["old_status"] is None


# --------------------------------------------------------------------------- #
# 2. Status-Wechsel mit sent_date + due_date
# --------------------------------------------------------------------------- #
def test_status_to_sent_sets_due_date_from_payment_terms(client):
    token = _register(client, "inv-2@example.com")
    _set_payment_terms(client, token, 21)
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_accepted_offer(client, token, lv_id)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}
    ).json()["id"]
    today = datetime.now(UTC).date()

    r = client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        headers=_auth(token),
        json={"status": "sent", "on_date": today.isoformat()},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "sent"
    assert body["sent_date"] == today.isoformat()
    assert body["due_date"] == (today + timedelta(days=21)).isoformat()
    # Audit
    statuses = [h["new_status"] for h in body["status_history"]]
    assert statuses == ["sent", "draft"]


# --------------------------------------------------------------------------- #
# 3. Auto-Numerierung pro Tenant pro Jahr UNIQUE
# --------------------------------------------------------------------------- #
def test_invoice_number_sequence_per_tenant_per_year(client):
    a = _register(client, "inv-num-a@example.com")
    b = _register(client, "inv-num-b@example.com")
    tid_a = _tenant_id(client, a)
    tid_b = _tenant_id(client, b)
    with _db() as db:
        lv_a = _seed_lv_with_positions(db, tid_a)
        lv_b = _seed_lv_with_positions(db, tid_b)
    oa = _create_accepted_offer(client, a, lv_a)
    ob = _create_accepted_offer(client, b, lv_b)

    nums_a = []
    for _ in range(3):
        nums_a.append(
            client.post(
                f"/api/v1/offers/{oa}/invoice", headers=_auth(a), json={}
            ).json()["invoice_number"]
        )
    assert [n[-2:] for n in nums_a] == ["01", "02", "03"]

    # Tenant b beginnt wieder bei 01
    n_b = client.post(
        f"/api/v1/offers/{ob}/invoice", headers=_auth(b), json={}
    ).json()["invoice_number"]
    assert n_b.endswith("-01")

    year = datetime.now(UTC).year
    expected = f"R-{year}-"
    assert all(n.startswith(expected) for n in nums_a)
    assert n_b.startswith(expected)


# --------------------------------------------------------------------------- #
# 4. Teilzahlung -> partially_paid
# --------------------------------------------------------------------------- #
def test_partial_payment_sets_partially_paid(client):
    token = _register(client, "inv-pay@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_accepted_offer(client, token, lv_id)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}
    ).json()["id"]
    client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        headers=_auth(token), json={"status": "sent"},
    )

    # 500 von 1190 brutto
    r = client.post(
        f"/api/v1/invoices/{inv_id}/payments",
        headers=_auth(token),
        json={"amount": 500.0, "note": "Anzahlung"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "partially_paid"
    assert body["paid_amount"] == 500.0
    assert body["paid_date"] is None  # nur bei Vollzahlung


# --------------------------------------------------------------------------- #
# 5. Restzahlung -> paid
# --------------------------------------------------------------------------- #
def test_full_payment_sets_paid_and_paid_date(client):
    token = _register(client, "inv-full@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_accepted_offer(client, token, lv_id)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}
    ).json()["id"]
    client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        headers=_auth(token), json={"status": "sent"},
    )
    # Anzahlung
    client.post(
        f"/api/v1/invoices/{inv_id}/payments",
        headers=_auth(token), json={"amount": 500.0},
    )
    today = datetime.now(UTC).date()
    # Rest
    r = client.post(
        f"/api/v1/invoices/{inv_id}/payments",
        headers=_auth(token),
        json={"amount": 690.0, "payment_date": today.isoformat()},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "paid"
    assert body["paid_amount"] == 1190.0
    assert body["paid_date"] == today.isoformat()


# --------------------------------------------------------------------------- #
# 6. check_overdue setzt sent auf overdue
# --------------------------------------------------------------------------- #
def test_check_overdue_marks_sent_invoices_with_past_due_date(client):
    token = _register(client, "inv-od@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_accepted_offer(client, token, lv_id)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}
    ).json()["id"]
    client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        headers=_auth(token), json={"status": "sent"},
    )

    # Faelligkeit kuenstlich in Vergangenheit setzen (DB-Manipulation)
    with _db() as db:
        inv = db.get(Invoice, inv_id)
        inv.due_date = date(2025, 1, 1)
        db.commit()

    r = client.post("/api/v1/finance/check-overdue", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["updated"] == 1

    detail = client.get(f"/api/v1/invoices/{inv_id}", headers=_auth(token)).json()
    assert detail["status"] == "overdue"


# --------------------------------------------------------------------------- #
# 7. Dunning-Stufen 1 + 2 + 3 mit Fristen + Gebuehren
# --------------------------------------------------------------------------- #
def test_dunning_levels_1_2_3_with_correct_fees_and_due(client):
    token = _register(client, "inv-dun@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_accepted_offer(client, token, lv_id)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}
    ).json()["id"]
    client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        headers=_auth(token), json={"status": "sent"},
    )
    # In overdue versetzen
    with _db() as db:
        inv = db.get(Invoice, inv_id)
        inv.due_date = date(2025, 1, 1)
        db.commit()
    client.post("/api/v1/finance/check-overdue", headers=_auth(token))

    # Stufe 1
    r = client.post(
        f"/api/v1/invoices/{inv_id}/dunnings", headers=_auth(token), json={}
    )
    assert r.status_code == 201
    d1 = r.json()
    assert d1["dunning_level"] == 1
    assert d1["mahngebuehr_betrag"] == 0.0
    today = datetime.now(UTC).date()
    assert d1["due_date"] == (today + timedelta(days=7)).isoformat()

    # Stufe 2
    r = client.post(
        f"/api/v1/invoices/{inv_id}/dunnings", headers=_auth(token), json={}
    )
    assert r.status_code == 201
    d2 = r.json()
    assert d2["dunning_level"] == 2
    assert d2["mahngebuehr_betrag"] == 5.0
    assert d2["due_date"] == (today + timedelta(days=14)).isoformat()

    # Stufe 3
    r = client.post(
        f"/api/v1/invoices/{inv_id}/dunnings", headers=_auth(token), json={}
    )
    assert r.status_code == 201
    d3 = r.json()
    assert d3["dunning_level"] == 3
    assert d3["mahngebuehr_betrag"] == 15.0
    assert d3["due_date"] == (today + timedelta(days=21)).isoformat()

    # Stufe 4 -> 409
    r = client.post(
        f"/api/v1/invoices/{inv_id}/dunnings", headers=_auth(token), json={}
    )
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# 8. Tenant-Isolation
# --------------------------------------------------------------------------- #
def test_tenant_isolation_invoice_other_tenant_404(client):
    a = _register(client, "inv-iso-a@example.com")
    b = _register(client, "inv-iso-b@example.com")
    tid_a = _tenant_id(client, a)
    with _db() as db:
        lv_a = _seed_lv_with_positions(db, tid_a)
    oid = _create_accepted_offer(client, a, lv_a)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(a), json={}
    ).json()["id"]

    # Tenant b sieht weder Invoice noch dessen Endpoints
    assert client.get(f"/api/v1/invoices/{inv_id}", headers=_auth(b)).status_code == 404
    assert client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        headers=_auth(b),
        json={"status": "sent"},
    ).status_code == 404
    assert client.post(
        f"/api/v1/invoices/{inv_id}/payments",
        headers=_auth(b),
        json={"amount": 100.0},
    ).status_code == 404


# --------------------------------------------------------------------------- #
# 9. Finance overview
# --------------------------------------------------------------------------- #
def test_finance_overview_aggregates_open_overdue_paid(client):
    token = _register(client, "inv-fin@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    # 3 Rechnungen
    oid = _create_accepted_offer(client, token, lv_id)
    inv1 = client.post(f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}).json()["id"]
    inv2 = client.post(f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}).json()["id"]
    inv3 = client.post(f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}).json()["id"]
    # inv1 -> paid (sent then payment)
    client.patch(f"/api/v1/invoices/{inv1}/status", headers=_auth(token), json={"status": "sent"})
    client.post(f"/api/v1/invoices/{inv1}/payments", headers=_auth(token), json={"amount": 1190.0})
    # inv2 -> sent (offen)
    client.patch(f"/api/v1/invoices/{inv2}/status", headers=_auth(token), json={"status": "sent"})
    # inv3 -> overdue
    client.patch(f"/api/v1/invoices/{inv3}/status", headers=_auth(token), json={"status": "sent"})
    with _db() as db:
        inv = db.get(Invoice, inv3)
        inv.due_date = date(2025, 1, 1)
        db.commit()
    client.post("/api/v1/finance/check-overdue", headers=_auth(token))

    r = client.get("/api/v1/finance/overview", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    # offen = sent (inv2) + overdue (inv3) = 2 Rechnungen
    assert body["offene_rechnungen_count"] == 2
    assert body["offene_summe_brutto"] == 2 * 1190.0
    assert body["ueberfaellige_count"] == 1
    assert body["ueberfaellige_summe_brutto"] == 1190.0
    assert body["gezahlte_summe_jahr_aktuell"] == 1190.0


# --------------------------------------------------------------------------- #
# 10. PDF-Generation
# --------------------------------------------------------------------------- #
def test_invoice_and_dunning_pdfs_are_valid(client):
    token = _register(client, "inv-pdf@example.com")
    client.patch(
        "/api/v1/tenant/profile",
        headers=_auth(token),
        json={
            "company_name": "Trockenbau X",
            "company_address_street": "Str 1",
            "company_address_zip": "12345",
            "company_address_city": "Stadt",
            "bank_iban": "DE12345678901234567890",
            "bank_bic": "MUSTDE12",
        },
    )
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_accepted_offer(client, token, lv_id)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}
    ).json()["id"]

    r = client.get(f"/api/v1/invoices/{inv_id}/pdf", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 1000

    # Dunning PDF
    client.patch(f"/api/v1/invoices/{inv_id}/status", headers=_auth(token), json={"status": "sent"})
    with _db() as db:
        inv = db.get(Invoice, inv_id)
        inv.due_date = date(2025, 1, 1)
        db.commit()
    client.post("/api/v1/finance/check-overdue", headers=_auth(token))
    d_id = client.post(
        f"/api/v1/invoices/{inv_id}/dunnings", headers=_auth(token), json={}
    ).json()["id"]

    r = client.get(
        f"/api/v1/invoices/{inv_id}/dunnings/{d_id}/pdf",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


# --------------------------------------------------------------------------- #
# 11. Email-Compose-Bonus
# --------------------------------------------------------------------------- #
def test_email_draft_returns_mailto_with_subject_and_body(client):
    token = _register(client, "inv-email@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_accepted_offer(client, token, lv_id)
    inv_id = client.post(
        f"/api/v1/offers/{oid}/invoice", headers=_auth(token), json={}
    ).json()["id"]

    r = client.post(f"/api/v1/invoices/{inv_id}/email", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mailto"].startswith("mailto:")
    assert "Rechnung" in body["subject"]
    assert "Rechnung" in body["body"]
