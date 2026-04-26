"""B+4.12 — Aufmaß-Lifecycle Tests.

Abdeckung:
1. Aufmaß-Erstellung aus accepted Offer mit Snapshot.
2. Mengen-Edit mit GP-Recalc.
3. Edits nach finalize blockiert (409).
4. Differenz-Aggregat korrekt (gesamt + by_group).
5. Tenant-Isolation.
6. Aufmaß aus draft-Offer wird abgelehnt (409).
7. Final-Offer-Erstellung verknuepft mit dem Aufmaß.
8. Final-Offer-PDF nutzt die gemessenen Mengen.
"""
from __future__ import annotations

from app.models.aufmass import Aufmass, AufmassPosition
from app.models.lv import LV
from app.models.offer import Offer
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
            "firma": "AufmassBetrieb",
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


def _seed_lv_with_positions(
    db,
    tenant_id: str,
    *,
    angebotssumme: float = 5_500.0,
    items: list[tuple[str, str, float, float, str]] = None,  # (oz, kurztext, menge, ep, einheit)
) -> str:
    """Seed eines LV mit kalkuliert-Status und Positionen."""
    items = items or [
        ("01.01", "Trennwand W112", 100.0, 50.0, "m²"),  # gp 5000
        ("01.02", "UA-Profil 75mm", 250.0, 2.0, "m"),  # gp 500
    ]
    lv = LV(
        tenant_id=tenant_id,
        projekt_name="Aufmaß-Test",
        auftraggeber="Test GmbH",
        original_dateiname="test.pdf",
        status="calculated",
        positionen_gesamt=len(items),
        positionen_gematcht=len(items),
        angebotssumme_netto=angebotssumme,
    )
    db.add(lv)
    db.flush()
    for i, (oz, k, m, ep, e) in enumerate(items):
        db.add(
            Position(
                lv_id=lv.id,
                reihenfolge=i,
                oz=oz,
                kurztext=k,
                menge=m,
                einheit=e,
                ep=ep,
                gp=m * ep,
            )
        )
    db.commit()
    return lv.id


def _create_offer_and_accept(c, token: str, lv_id: str) -> str:
    """Erzeugt Offer und marked it accepted via 2 Status-Wechsel."""
    oid = c.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token), json={}
    ).json()["id"]
    c.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "sent"},
    )
    c.patch(
        f"/api/v1/offers/{oid}/status",
        headers=_auth(token),
        json={"status": "accepted"},
    )
    return oid


# --------------------------------------------------------------------------- #
# 1. Aufmaß-Erstellung aus accepted Offer mit Snapshot
# --------------------------------------------------------------------------- #
def test_create_aufmass_from_accepted_offer_snapshots_positions(client):
    token = _register(client, "auf-1@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_offer_and_accept(client, token, lv_id)

    r = client.post(
        f"/api/v1/offers/{oid}/aufmass",
        headers=_auth(token),
        json={"internal_notes": "Erstes Aufmaß"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["aufmass_number"].startswith("M-")
    assert body["status"] == "in_progress"
    assert body["source_offer_id"] == oid
    assert body["internal_notes"] == "Erstes Aufmaß"
    assert len(body["positions"]) == 2

    p1 = next(p for p in body["positions"] if p["oz"] == "01.01")
    assert p1["lv_menge"] == 100.0
    assert p1["gemessene_menge"] == 100.0  # initial gleich lv_menge
    assert p1["ep"] == 50.0
    assert p1["gp_lv_snapshot"] == 5000.0
    assert p1["gp_aufmass"] == 5000.0
    assert p1["einheit"] == "m²"


# --------------------------------------------------------------------------- #
# 2. Mengen-Edit + GP-Recalc
# --------------------------------------------------------------------------- #
def test_position_edit_recalculates_gp_aufmass(client):
    token = _register(client, "auf-2@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_offer_and_accept(client, token, lv_id)
    aufmass = client.post(
        f"/api/v1/offers/{oid}/aufmass", headers=_auth(token), json={}
    ).json()
    aid = aufmass["id"]
    pos1 = next(p for p in aufmass["positions"] if p["oz"] == "01.01")
    pid = pos1["id"]

    # 100 -> 120
    r = client.patch(
        f"/api/v1/aufmasse/{aid}/positions/{pid}",
        headers=_auth(token),
        json={"gemessene_menge": 120.0, "notes": "Nachverputzte Wandflaeche"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gemessene_menge"] == 120.0
    assert body["gp_aufmass"] == 6000.0  # 120 * 50
    assert body["gp_lv_snapshot"] == 5000.0  # unveraendert
    assert body["notes"] == "Nachverputzte Wandflaeche"


# --------------------------------------------------------------------------- #
# 3. Finalize blockiert weitere Edits
# --------------------------------------------------------------------------- #
def test_finalize_blocks_further_edits(client):
    token = _register(client, "auf-3@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_offer_and_accept(client, token, lv_id)
    aufmass = client.post(
        f"/api/v1/offers/{oid}/aufmass", headers=_auth(token), json={}
    ).json()
    aid = aufmass["id"]
    pid = aufmass["positions"][0]["id"]

    # Finalize
    r = client.post(f"/api/v1/aufmasse/{aid}/finalize", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "finalized"
    assert r.json()["finalized_at"] is not None

    # Weitere Edits -> 409
    r = client.patch(
        f"/api/v1/aufmasse/{aid}/positions/{pid}",
        headers=_auth(token),
        json={"gemessene_menge": 999.0},
    )
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# 4. Differenz-Aggregat
# --------------------------------------------------------------------------- #
def test_summary_aggregates_diff_total_and_per_group(client):
    token = _register(client, "auf-4@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        # 3 Positions in 2 Hauptgruppen
        lv_id = _seed_lv_with_positions(
            db, tid,
            items=[
                ("59.10.0010", "Wand A", 100.0, 50.0, "m²"),  # group 59, gp 5000
                ("59.20.0001", "Wand B", 50.0, 50.0, "m²"),   # group 59, gp 2500
                ("60.10.0001", "Decke",  20.0, 100.0, "m²"),  # group 60, gp 2000
            ],
        )
    oid = _create_offer_and_accept(client, token, lv_id)
    aufmass = client.post(
        f"/api/v1/offers/{oid}/aufmass", headers=_auth(token), json={}
    ).json()
    aid = aufmass["id"]

    # Edits: A: 100->110 (+500); B: 50->40 (-500); Decke: 20->25 (+500). Net +500
    edits = {"59.10.0010": 110.0, "59.20.0001": 40.0, "60.10.0001": 25.0}
    for p in aufmass["positions"]:
        client.patch(
            f"/api/v1/aufmasse/{aid}/positions/{p['id']}",
            headers=_auth(token),
            json={"gemessene_menge": edits[p["oz"]]},
        )

    r = client.get(f"/api/v1/aufmasse/{aid}/summary", headers=_auth(token))
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["lv_total_netto"] == 9500.0    # 5000+2500+2000
    assert s["aufmass_total_netto"] == 10000.0  # 5500+2000+2500
    assert s["diff_netto"] == 500.0
    assert s["position_count"] == 3
    # Decimal vs float Praezision — approx
    assert abs(s["diff_pct"] - 500.0 / 9500.0 * 100) < 1e-9

    by_group = {g["group"]: g for g in s["by_group"]}
    # Gruppe 59: lv 7500, aufmass 7500 (Wand A +500, Wand B -500), diff 0
    assert by_group["59"]["lv_netto"] == 7500.0
    assert by_group["59"]["aufmass_netto"] == 7500.0
    assert by_group["59"]["diff_netto"] == 0.0
    # Gruppe 60: lv 2000, aufmass 2500
    assert by_group["60"]["diff_netto"] == 500.0


# --------------------------------------------------------------------------- #
# 5. Tenant-Isolation
# --------------------------------------------------------------------------- #
def test_tenant_isolation_aufmass_other_tenant_404(client):
    a = _register(client, "auf-iso-a@example.com")
    b = _register(client, "auf-iso-b@example.com")
    tid_a = _tenant_id(client, a)
    with _db() as db:
        lv_a = _seed_lv_with_positions(db, tid_a)
    oid = _create_offer_and_accept(client, a, lv_a)
    aufmass = client.post(
        f"/api/v1/offers/{oid}/aufmass", headers=_auth(a), json={}
    ).json()
    aid = aufmass["id"]
    pid = aufmass["positions"][0]["id"]

    # Tenant b sieht weder Aufmaß noch dessen Positionen
    assert client.get(f"/api/v1/aufmasse/{aid}", headers=_auth(b)).status_code == 404
    assert client.get(f"/api/v1/aufmasse/{aid}/summary", headers=_auth(b)).status_code == 404
    assert client.post(f"/api/v1/aufmasse/{aid}/finalize", headers=_auth(b)).status_code == 404
    assert client.patch(
        f"/api/v1/aufmasse/{aid}/positions/{pid}",
        headers=_auth(b),
        json={"gemessene_menge": 50},
    ).status_code == 404


# --------------------------------------------------------------------------- #
# 6. Aufmaß aus draft Offer wird abgelehnt
# --------------------------------------------------------------------------- #
def test_aufmass_from_draft_offer_rejected_409(client):
    token = _register(client, "auf-draft@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = client.post(
        f"/api/v1/lvs/{lv_id}/offers", headers=_auth(token), json={}
    ).json()["id"]

    r = client.post(
        f"/api/v1/offers/{oid}/aufmass", headers=_auth(token), json={}
    )
    assert r.status_code == 409
    assert "accepted" in r.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# 7. Final-Offer-Erstellung verknuepft mit dem Aufmaß
# --------------------------------------------------------------------------- #
def test_create_final_offer_links_to_aufmass_with_diff_in_notes(client):
    token = _register(client, "auf-fo@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)  # 5500 netto
    oid = _create_offer_and_accept(client, token, lv_id)
    aufmass = client.post(
        f"/api/v1/offers/{oid}/aufmass", headers=_auth(token), json={}
    ).json()
    aid = aufmass["id"]

    # Mengen leicht erhoehen: +200 EUR
    pid = next(p["id"] for p in aufmass["positions"] if p["oz"] == "01.01")
    client.patch(
        f"/api/v1/aufmasse/{aid}/positions/{pid}",
        headers=_auth(token),
        json={"gemessene_menge": 104.0},  # 100 -> 104, +4 m² = +200 EUR
    )
    # Finalize first
    client.post(f"/api/v1/aufmasse/{aid}/finalize", headers=_auth(token))

    # Final-Offer erstellen
    r = client.post(
        f"/api/v1/aufmasse/{aid}/create-final-offer",
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["pdf_format"] == "aufmass_basiert"
    assert body["status"] == "draft"
    # 5700 = 5500 LV + 200 Diff
    assert body["betrag_netto"] == 5700.0
    # Hinweis auf Aufmaß in den Notes
    assert "Aufmaß" in body["internal_notes"]
    assert aufmass["aufmass_number"] in body["internal_notes"]

    # DB-Check: aufmass_id ist gesetzt
    detail = client.get(f"/api/v1/offers/{body['id']}", headers=_auth(token)).json()
    # OfferDetail enthaelt aufmass_id nicht direkt — DB-Check
    with _db() as db:
        offer_db = db.get(Offer, body["id"])
        assert offer_db.aufmass_id == aid


# --------------------------------------------------------------------------- #
# 8. Final-Offer-PDF nutzt die gemessenen Mengen
# --------------------------------------------------------------------------- #
def test_final_offer_pdf_uses_aufmass_quantities(client):
    token = _register(client, "auf-pdf@example.com")
    # Briefkopf damit PDF ueberhaupt generiert
    client.patch(
        "/api/v1/tenant/profile",
        headers=_auth(token),
        json={
            "company_name": "Trockenbau AG",
            "company_address_street": "Str 1",
            "company_address_zip": "12345",
            "company_address_city": "Stadt",
        },
    )
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_offer_and_accept(client, token, lv_id)
    aufmass = client.post(
        f"/api/v1/offers/{oid}/aufmass", headers=_auth(token), json={}
    ).json()
    aid = aufmass["id"]
    # Edit
    pid = next(p["id"] for p in aufmass["positions"] if p["oz"] == "01.01")
    client.patch(
        f"/api/v1/aufmasse/{aid}/positions/{pid}",
        headers=_auth(token),
        json={"gemessene_menge": 110.0},
    )
    client.post(f"/api/v1/aufmasse/{aid}/finalize", headers=_auth(token))

    final = client.post(
        f"/api/v1/aufmasse/{aid}/create-final-offer", headers=_auth(token)
    ).json()

    r = client.get(f"/api/v1/offers/{final['id']}/pdf", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 1000  # nicht-leer

    # Aufmass-PDF-Endpoint funktioniert ebenfalls
    r2 = client.get(f"/api/v1/aufmasse/{aid}/pdf", headers=_auth(token))
    assert r2.status_code == 200
    assert r2.content[:4] == b"%PDF"
    # Filename enthaelt Aufmass-Nummer
    assert aufmass["aufmass_number"] in r2.headers["content-disposition"]


# --------------------------------------------------------------------------- #
# Bonus: list pro LV
# --------------------------------------------------------------------------- #
def test_list_aufmasse_for_lv(client):
    token = _register(client, "auf-list@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_positions(db, tid)
    oid = _create_offer_and_accept(client, token, lv_id)
    client.post(f"/api/v1/offers/{oid}/aufmass", headers=_auth(token), json={})

    r = client.get(f"/api/v1/lvs/{lv_id}/aufmasse", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["status"] == "in_progress"
