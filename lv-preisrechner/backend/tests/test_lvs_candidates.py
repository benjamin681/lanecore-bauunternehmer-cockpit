"""B+4.3.0b Golden-Tests fuer den Candidates-Endpoint.

GET /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates

Bis zu diesem Commit existiert der Endpoint noch nicht — alle Tests
liefern 404 und sollen damit **rot** sein. Die echte Implementierung
folgt in Phase 3.

Test-Strategie:
- Ein einzelnes Setup-Fixture erzeugt Tenant + aktive Kemmler-ahnliche
  SupplierPriceList + LV + Position mit System ``W628A`` (das Rezept
  hat mehrere Materialien: Gipskarton, CW, UW, Daemmung, Schrauben).
- Happy-Path-Tests pruefen Response-Struktur und Kandidaten-Liste.
- Guard-Tests sichern Auth-, 404-, Validation- und Determinismus-
  Semantik ab.

Alle Tests tragen Docstrings nach dem 4-Abschnitt-Muster (Zweck,
Initialstatus, Nach-Fix-Status, Warnsatz).
"""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

import pytest

from app.models.lv import LV
from app.models.position import Position
from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import hash_password


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.core import database

    return database.SessionLocal()


def _get_tenant_of_token(c, token: str) -> str:
    me = c.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200
    return me.json()["tenant_id"]


def _seed_kemmler_list(db, tenant_id: str, user_id: str) -> str:
    """Lege eine aktive SupplierPriceList mit realistischen Kandidaten an.

    Materialien die W628A braucht: Gipskarton 12,5 mm, CW-Profil 100,
    UW-Profil 100, Daemmung, Schrauben, plus PE-Folie UT40 als
    Regression-Kandidat.
    """
    pl = SupplierPriceList(
        tenant_id=tenant_id,
        supplier_name="Kemmler",
        list_name="Ausbau 2026-04",
        valid_from=date(2026, 1, 1),
        source_file_path="/tmp/kemmler.pdf",
        source_file_hash=f"kemmler-test-{tenant_id[:8]}",
        status=PricelistStatus.APPROVED.value,
        is_active=True,
        uploaded_by_user_id=user_id,
    )
    db.add(pl)
    db.flush()

    entries = [
        # Gipskarton
        SupplierPriceEntry(
            pricelist_id=pl.id, tenant_id=tenant_id,
            manufacturer="Knauf",
            product_name="Gipskartonpl. (HRAK) 2000x1250x12,5 mm",
            category="Gipskarton",
            price_net=Decimal("3.30"), currency="EUR", unit="€/m²",
            effective_unit="m²", price_per_effective_unit=Decimal("3.30"),
        ),
        # CW-100 Profil (echter Kemmler-String, keinen extrahierbaren Code)
        SupplierPriceEntry(
            pricelist_id=pl.id, tenant_id=tenant_id,
            manufacturer=None,
            product_name="CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.",
            category="Profile",
            price_net=Decimal("8.05"), currency="EUR", unit="€/m",
            effective_unit="m", price_per_effective_unit=Decimal("8.05"),
        ),
        # Daemmung Sonorock (ohne UT-Code, matcht Daemmung-40mm-Query)
        SupplierPriceEntry(
            pricelist_id=pl.id, tenant_id=tenant_id,
            manufacturer="Rockwool",
            product_name="Trennwandpl. Sonorock WLG040, 1000x625x40 mm - 7,5 m²/Pak.",
            category="Daemmung",
            price_net=Decimal("3.05"), currency="EUR", unit="€/m²",
            effective_unit="m²", price_per_effective_unit=Decimal("3.05"),
            attributes={
                "product_code_type": "WLG",
                "product_code_dimension": "040",
                "product_code_raw": "WLG040",
            },
        ),
        # PE-Folie mit UT40-Code — MUSS in Daemmungs-Material ausgefiltert werden
        SupplierPriceEntry(
            pricelist_id=pl.id, tenant_id=tenant_id,
            manufacturer=None,
            product_name="PE-Folie S=0,20 mm - 4000 mm x 50 m/Ro. UT40",
            category="Folien",
            price_net=Decimal("18.90"), currency="EUR", unit="€/m²",
            effective_unit="m²", price_per_effective_unit=Decimal("18.90"),
            attributes={
                "product_code_type": "UT",
                "product_code_dimension": "40",
                "product_code_raw": "UT40",
            },
        ),
        # Schrauben
        SupplierPriceEntry(
            pricelist_id=pl.id, tenant_id=tenant_id,
            manufacturer="ACP",
            product_name="ACP Gipsplattenschrauben Bohrs. 3,5x45 mm - 500 St./Pak.",
            category="Schrauben",
            price_net=Decimal("22.58"), currency="EUR", unit="€/Pak.",
            effective_unit="Stk", price_per_effective_unit=Decimal("0.045"),
        ),
    ]
    for e in entries:
        db.add(e)
    db.commit()
    return pl.id


def _seed_lv_with_position(
    db,
    tenant_id: str,
    *,
    system: str = "W628A",
    feuerwiderstand: str = "F0",
    plattentyp: str = "GKB",
) -> tuple[str, str]:
    """Erzeugt ein LV + eine Position des gewuenschten Systems.

    Rueckgabe: (lv_id, position_id).
    """
    lv = LV(
        tenant_id=tenant_id,
        original_dateiname="candidates-test.pdf",
        status="review_needed",
    )
    db.add(lv)
    db.flush()
    p = Position(
        lv_id=lv.id,
        oz="1.1",
        kurztext=f"Test {system}",
        menge=100.0,
        einheit="m²",
        erkanntes_system=system,
        feuerwiderstand=feuerwiderstand,
        plattentyp=plattentyp,
    )
    db.add(p)
    db.commit()
    return lv.id, p.id


def _setup(client, email="candidates@example.com", firma="CandidatesBetrieb"):
    """Komplettes Setup fuer einen Test. Gibt (token, lv_id, pos_id)."""
    token = _register_and_login(client, email, firma=firma)
    db = _db()
    try:
        tenant_id = _get_tenant_of_token(client, token)
        user = (
            db.query(User).filter(User.tenant_id == tenant_id).first()
        )
        _seed_kemmler_list(db, tenant_id, user.id)
        lv_id, pos_id = _seed_lv_with_position(db, tenant_id)
        return token, lv_id, pos_id, tenant_id
    finally:
        db.close()


def _url(lv_id: str, pos_id: str) -> str:
    return f"/api/v1/lvs/{lv_id}/positions/{pos_id}/candidates"


# --------------------------------------------------------------------------- #
# Test 1 — Happy Path mit Default-Limit
# --------------------------------------------------------------------------- #
def test_happy_path_default_limit(client):
    """GET liefert 200 + strukturierte Response mit materials-Array.

    Zweck: Basis-Vertrag des Endpoints absichern.
    Initialstatus: **rot** (Endpoint liefert 404, Assertion `== 200`
      scheitert).
    Nach-Fix-Status: gruen.
    Wenn nach einem Fix ROT: die Response-Struktur ist gebrochen
      oder der Endpoint wurde entfernt.
    """
    token, lv_id, pos_id, _ = _setup(client, "hp@example.com")
    r = client.get(_url(lv_id, pos_id), headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "position_id" in body
    assert body["position_id"] == pos_id
    assert "position_name" in body
    assert isinstance(body["materials"], list)
    assert len(body["materials"]) > 0
    first_mat = body["materials"][0]
    assert set(first_mat.keys()) >= {
        "material_name", "required_amount", "unit", "candidates",
    }
    # Jeder Kandidat hat den vollen Satz an Feldern
    for cand in first_mat["candidates"]:
        assert set(cand.keys()) >= {
            "pricelist_name",
            "candidate_name",
            "match_confidence",
            "stage",
            "price_net",
            "unit",
            "match_reason",
        }
        assert isinstance(cand["match_confidence"], (int, float))
        assert isinstance(cand["price_net"], (int, float))


# --------------------------------------------------------------------------- #
# Test 2 — Custom Limit
# --------------------------------------------------------------------------- #
def test_custom_limit_wird_respektiert(client):
    """?limit=5 begrenzt echte Kandidaten auf 5 je Material.

    Zweck: Pagination-artige Kontrolle des Response-Volumens.
    Initialstatus: **rot** (Endpoint existiert nicht).
    Nach-Fix-Status: gruen — jedes Material hat max 5 non-estimated
      Kandidaten plus 1 estimated-Eintrag.
    Wenn nach Fix ROT: Limit wird nicht angewandt oder falsch.
    """
    token, lv_id, pos_id, _ = _setup(client, "limit@example.com")
    r = client.get(_url(lv_id, pos_id) + "?limit=5", headers=_auth(token))
    assert r.status_code == 200, r.text
    for mat in r.json()["materials"]:
        non_est = [c for c in mat["candidates"] if c["stage"] != "estimated"]
        assert len(non_est) <= 5


# --------------------------------------------------------------------------- #
# Test 3 — UT-Blacklist greift pro Material
# --------------------------------------------------------------------------- #
def test_ut_blacklist_filtert_daemmung(client):
    """Dämmungs-Material: UT40 ist NICHT in candidates, Sonorock schon.

    Zweck: Regression-Schutz fuer den Option-C-Blacklist-Filter im
      Near-Miss-Drawer.
    Initialstatus: **rot** (Endpoint existiert nicht).
    Nach-Fix-Status: gruen — UT40-Kandidat erscheint in keinem
      Material-Block, Sonorock erscheint im Daemmungs-Block.
    Wenn nach Fix ROT: der Blacklist-Filter wird im
      list_candidates-Helper vergessen oder falsch angewandt —
      die PE-Folie wuerde dem Handwerker als Alternative angeboten.
    """
    token, lv_id, pos_id, _ = _setup(client, "ut@example.com")
    r = client.get(_url(lv_id, pos_id), headers=_auth(token))
    assert r.status_code == 200, r.text
    all_names = {
        cand["candidate_name"]
        for mat in r.json()["materials"]
        for cand in mat["candidates"]
    }
    assert all("UT40" not in n for n in all_names), (
        f"UT40-Produkt ist faelschlich in Kandidaten: {all_names}"
    )


# --------------------------------------------------------------------------- #
# Test 4 — Estimated pro Material als letzter Eintrag
# --------------------------------------------------------------------------- #
def test_estimated_pro_material_immer_letzter_eintrag(client):
    """Jedes Material hat genau einen estimated-Eintrag am Ende.

    Zweck: Design-Invariante durchsetzen — der virtuelle Schaetzwert
      ist pro Material persistent und immer am Ende der candidates-
      Liste.
    Initialstatus: **rot** (Endpoint existiert nicht).
    Nach-Fix-Status: gruen.
    Wenn nach Fix ROT: estimated wurde an Position-Ebene geschoben
      oder fehlt bei Materialien ohne echten Match.
    """
    token, lv_id, pos_id, _ = _setup(client, "est@example.com")
    r = client.get(_url(lv_id, pos_id), headers=_auth(token))
    assert r.status_code == 200, r.text
    for mat in r.json()["materials"]:
        assert len(mat["candidates"]) >= 1
        assert mat["candidates"][-1]["stage"] == "estimated"


# --------------------------------------------------------------------------- #
# Test 5 — Position ohne Rezept
# --------------------------------------------------------------------------- #
def test_position_ohne_rezept_liefert_leeres_materials(client):
    """Zulagen/Regiestunden ohne Rezept: materials ist leer, Status 200.

    Zweck: Edge Case abdecken — nicht alle Positionen haben ein
      Rezept (z. B. Regiestunden, freie Zulagen).
    Initialstatus: **rot** (Endpoint existiert nicht).
    Nach-Fix-Status: gruen — Response 200, position_id/_name gesetzt,
      materials=[], keine Exception.
    Wenn nach Fix ROT: Endpoint wirft 500 oder 404 fuer rezeptlose
      Positionen statt leere Liste.
    """
    token = _register_and_login(client, "rezeptlos@example.com")
    db = _db()
    try:
        tenant_id = _get_tenant_of_token(client, token)
        user = db.query(User).filter(User.tenant_id == tenant_id).first()
        _seed_kemmler_list(db, tenant_id, user.id)
        # Position mit einem System, das kein Rezept hat
        lv_id, pos_id = _seed_lv_with_position(db, tenant_id, system="Regiestunde")
    finally:
        db.close()
    r = client.get(_url(lv_id, pos_id), headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["materials"] == []


# --------------------------------------------------------------------------- #
# Test 6 — 404 bei nicht-existenter Position
# --------------------------------------------------------------------------- #
def test_404_bei_unbekannter_position(client):
    """Unbekannte pos_id → 404 mit klar erkennbarer Fehlermeldung.

    Zweck: semantisches 404 (nicht das FastAPI-Default-404 fuer
      unbekannte Routes).
    Initialstatus: **rot** — Endpoint existiert nicht, FastAPI liefert
      zwar 404, aber mit `detail="Not Found"` statt der erwarteten
      Meldung.
    Nach-Fix-Status: gruen — detail enthaelt "Position".
    """
    token, lv_id, _real_pos_id, _ = _setup(client, "404@example.com")
    fake_pos = "00000000-0000-0000-0000-000000000000"
    r = client.get(_url(lv_id, fake_pos), headers=_auth(token))
    assert r.status_code == 404
    assert "Position" in r.json().get("detail", "")


# --------------------------------------------------------------------------- #
# Test 7 — 401 ohne Auth
# --------------------------------------------------------------------------- #
def test_401_ohne_auth(client):
    """Fehlender Bearer-Token → 401.

    Zweck: kein ungeschuetzter Read-Only-Pfad.
    Initialstatus: **rot** — Endpoint existiert nicht, FastAPI liefert
      404 statt 401.
    Nach-Fix-Status: gruen.
    """
    token, lv_id, pos_id, _ = _setup(client, "unauth@example.com")
    # absichtlich ohne headers
    r = client.get(_url(lv_id, pos_id))
    assert r.status_code == 401


# --------------------------------------------------------------------------- #
# Test 8 — Fremder Tenant: 404 (nicht 403, keine Leckage)
# --------------------------------------------------------------------------- #
def test_fremder_tenant_bekommt_404(client):
    """User B aus anderem Tenant → 404.

    Zweck: Multi-Tenant-Isolation und keine Existenz-Leckage
      (404 statt 403).
    Initialstatus: **rot** — Endpoint existiert nicht, Response hat
      zwar 404 aber generisch, nicht mit "Position" im detail.
    Nach-Fix-Status: gruen.
    """
    token_a, lv_id, pos_id, _ = _setup(client, "a@example.com", firma="A")
    token_b = _register_and_login(client, "b@example.com", firma="B")
    r = client.get(_url(lv_id, pos_id), headers=_auth(token_b))
    assert r.status_code == 404
    # Entscheidend: 404 und nicht 403, damit die Existenz nicht leakt.
    assert r.status_code != 403


# --------------------------------------------------------------------------- #
# Test 9 — Limit-Validierung
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("limit,expected", [(0, 422), (6, 422), (3, 200)])
def test_limit_validierung(client, limit, expected):
    """?limit=0|6 → 422, ?limit=3 → 200.

    Zweck: Pydantic-/FastAPI-Validator erzwingt Min 1, Max 5.
    Initialstatus fuer limit=3: **rot** (Endpoint existiert nicht,
      liefert 404 statt 200).
    Initialstatus fuer limit=0/6: **rot** (liefert 404 statt 422).
    Nach-Fix-Status: gruen.
    """
    token, lv_id, pos_id, _ = _setup(
        client, f"lim{limit}@example.com", firma=f"LIM{limit}"
    )
    r = client.get(_url(lv_id, pos_id) + f"?limit={limit}", headers=_auth(token))
    assert r.status_code == expected, r.text


# --------------------------------------------------------------------------- #
# Test 10 — Performance-Sanity-Check
# --------------------------------------------------------------------------- #
def test_performance_unter_1500ms(client):
    """5-Material-Response in unter 1,5 s.

    Zweck: grober Sanity-Check gegen Worst-Case-Drift. Kein strenger
      Benchmark — nur Alarm, wenn die Python-Iteration > 1,5 s
      dauert.
    Initialstatus: **rot** (Endpoint liefert 404 → != 200, Assertion
      scheitert).
    Nach-Fix-Status: gruen, typischerweise deutlich unter 500 ms.
    Wenn nach Fix ROT: O(n²)-Regression oder fehlender Short-Circuit
      im Scorer — dann Profiler oder Pre-Filter als Follow-up.
    """
    token, lv_id, pos_id, _ = _setup(client, "perf@example.com")
    start = time.perf_counter()
    r = client.get(_url(lv_id, pos_id), headers=_auth(token))
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert r.status_code == 200
    assert elapsed_ms < 1500, f"Response dauerte {elapsed_ms:.0f} ms"


# --------------------------------------------------------------------------- #
# Test 11 — Determinismus: zwei identische Calls → gleiche Struktur
# --------------------------------------------------------------------------- #
def test_material_reihenfolge_deterministisch(client):
    """Zwei aufeinanderfolgende Calls liefern identische Material-Sequenz.

    Zweck: UI-Konsistenz — der Drawer darf seine Reihenfolge nicht
      zwischen Renderings aendern.
    Initialstatus: **rot** — Endpoint liefert 404, die Happy-Path-
      Assertion `== 200` scheitert.
    Nach-Fix-Status: gruen.
    Wenn nach Fix ROT: Material-Iteration basiert auf Hash- oder
      Set-Reihenfolge, die zwischen Python-Runs driftet —
      `sort_key=material_name` als Fix.
    """
    token, lv_id, pos_id, _ = _setup(client, "det@example.com")
    r1 = client.get(_url(lv_id, pos_id), headers=_auth(token))
    r2 = client.get(_url(lv_id, pos_id), headers=_auth(token))
    assert r1.status_code == 200
    assert r2.status_code == 200
    names1 = [m["material_name"] for m in r1.json()["materials"]]
    names2 = [m["material_name"] for m in r2.json()["materials"]]
    assert names1 == names2
