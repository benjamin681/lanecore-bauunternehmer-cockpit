"""Tests fuer B+4.6 — Gap-Resolve-Workflow.

POST /api/v1/lvs/{lv_id}/gaps/resolve

Abgedeckte Szenarien:
1. manual_price legt einen TenantPriceOverride an und markiert das Gap
   als reviewed; der Audit-Trail in LVGapResolution hat die FK zum
   Override. Erneuter Call aktualisiert den bestehenden Override + Audit
   (Upsert), kein Duplikat.
2. skip entfernt das Gap aus dem Report (GET /gaps zeigt es nicht mehr).
3. Validation: manual_price ohne price_net -> 422, Tenant-Isolation ->
   404 bei fremdem LV.
4. unique_missing_materials im Report enthaelt die Dedup-Liste mit
   betroffene_positionen, und skipped Entries fehlen.
"""
from __future__ import annotations

from typing import Any

from app.models.lv import LV, LVGapResolution
from app.models.position import Position
from app.models.pricing import TenantPriceOverride


# --------------------------------------------------------------------------- #
# Helpers (lokal, kompakt; analog zu test_lvs_gaps.py)
# --------------------------------------------------------------------------- #
def _register(c, email: str) -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": "GapBetrieb",
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


def _mat(dna: str, *, menge: float = 1.0, einheit: str = "lfm") -> dict[str, Any]:
    return {
        "dna": dna,
        "menge": menge,
        "einheit": einheit,
        "preis_einheit": 0.0,
        "gp": 0.0,
        "price_source": "not_found",
        "source_description": "Kein Match",
        "applied_discount_percent": None,
        "needs_review": True,
        "match_confidence": None,
    }


def _seed_lv_with_missing_material(
    db, tenant_id: str, dna: str, num_positions: int = 2
) -> str:
    """Erstellt ein LV mit num_positions Positionen, die alle dasselbe
    fehlende Material referenzieren."""
    lv = LV(tenant_id=tenant_id, original_dateiname="resolve.pdf", status="calculated")
    db.add(lv)
    db.flush()
    for i in range(num_positions):
        p = Position(
            lv_id=lv.id,
            reihenfolge=i,
            oz=f"1.{i + 1}",
            kurztext=f"Pos {i + 1}",
            menge=10.0 + i,
            einheit="m",
            erkanntes_system="",
            feuerwiderstand="F0",
            plattentyp="GKB",
            materialien=[_mat(dna, menge=5.0 + i, einheit="lfm")],
            needs_price_review=True,
        )
        db.add(p)
    db.commit()
    return lv.id


# --------------------------------------------------------------------------- #
# Test 1 — manual_price legt Override + Audit an; unique_missing weg
# --------------------------------------------------------------------------- #
def test_manual_price_legt_override_an_und_loest_gap(client, monkeypatch):
    # kalkuliere_lv stubben, damit wir ohne vollen Material-Pipeline-Setup
    # testen koennen: die Migration + Persistenz + Audit-Trail sind der
    # kritische Pfad.
    monkeypatch.setattr(
        "app.services.kalkulation.kalkuliere_lv",
        lambda db, lv_id, tenant_id: None,
    )

    token = _register(client, "resolve-manual@example.com")
    tid = _tenant_id(client, token)
    dna = "Protektor|Profile|Eckschutzschiene|2500mm|"

    with _db() as db:
        lv_id = _seed_lv_with_missing_material(db, tid, dna, num_positions=2)

    # Baseline: unique_missing enthaelt das DNA-Material.
    r0 = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
    assert r0.status_code == 200
    assert r0.json()["missing_count"] == 2
    uniq = r0.json()["unique_missing_materials"]
    assert len(uniq) == 1
    assert uniq[0]["material_dna"] == dna
    assert sorted(uniq[0]["betroffene_positionen"]) == ["1.1", "1.2"]
    assert uniq[0]["total_required_amount"] == 5.0 + 6.0

    # Resolve
    r = client.post(
        f"/api/v1/lvs/{lv_id}/gaps/resolve",
        headers=_auth(token),
        json={
            "material_dna": dna,
            "resolution_type": "manual_price",
            "value": {"price_net": 2.87, "unit": "lfm"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resolution"]["resolution_type"] == "manual_price"
    assert body["resolution"]["resolved_value"] == {"price_net": 2.87, "unit": "lfm"}
    override_id = body["resolution"]["tenant_price_override_id"]
    assert override_id is not None

    # Override wirklich in DB?
    with _db() as db:
        ov = db.get(TenantPriceOverride, override_id)
        assert ov is not None
        assert ov.override_price == 2.87
        assert ov.unit == "lfm"
        assert ov.article_number == f"DNA:{dna}"
        audit = db.query(LVGapResolution).filter_by(lv_id=lv_id).all()
        assert len(audit) == 1


# --------------------------------------------------------------------------- #
# Test 2 — Upsert: zweiter manual_price-Call aktualisiert, kein Duplikat
# --------------------------------------------------------------------------- #
def test_manual_price_upsert_kein_duplikat(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.kalkulation.kalkuliere_lv",
        lambda db, lv_id, tenant_id: None,
    )
    token = _register(client, "resolve-upsert@example.com")
    tid = _tenant_id(client, token)
    dna = "|Profile|Eckschiene|2500|"
    with _db() as db:
        lv_id = _seed_lv_with_missing_material(db, tid, dna)

    def _post(price: float) -> dict:
        return client.post(
            f"/api/v1/lvs/{lv_id}/gaps/resolve",
            headers=_auth(token),
            json={
                "material_dna": dna,
                "resolution_type": "manual_price",
                "value": {"price_net": price, "unit": "lfm"},
            },
        ).json()

    r1 = _post(2.87)
    r2 = _post(3.10)

    # Gleiche Audit-ID, gleicher Override — aber aktualisierte Werte
    assert r1["resolution"]["id"] == r2["resolution"]["id"]
    assert r1["resolution"]["tenant_price_override_id"] == (
        r2["resolution"]["tenant_price_override_id"]
    )

    with _db() as db:
        ov = db.get(
            TenantPriceOverride, r2["resolution"]["tenant_price_override_id"]
        )
        assert ov.override_price == 3.10
        assert db.query(LVGapResolution).filter_by(lv_id=lv_id).count() == 1
        assert (
            db.query(TenantPriceOverride)
            .filter_by(tenant_id=tid, article_number=f"DNA:{dna}")
            .count()
            == 1
        )


# --------------------------------------------------------------------------- #
# Test 3 — skip entfernt das Gap aus dem Report
# --------------------------------------------------------------------------- #
def test_skip_entfernt_gap_aus_report(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.kalkulation.kalkuliere_lv",
        lambda db, lv_id, tenant_id: None,
    )
    token = _register(client, "resolve-skip@example.com")
    tid = _tenant_id(client, token)
    dna = "|Profile|Eckschiene|2500|"
    with _db() as db:
        lv_id = _seed_lv_with_missing_material(db, tid, dna)

    # Vorher: 1 unique missing
    assert (
        client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token))
        .json()["missing_count"]
        == 2
    )

    r = client.post(
        f"/api/v1/lvs/{lv_id}/gaps/resolve",
        headers=_auth(token),
        json={
            "material_dna": dna,
            "resolution_type": "skip",
            "value": {},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["resolution"]["resolution_type"] == "skip"
    assert r.json()["resolution"]["tenant_price_override_id"] is None

    # Nachher: Gap ist weg aus Counter UND unique-Liste
    after = client.get(f"/api/v1/lvs/{lv_id}/gaps", headers=_auth(token)).json()
    assert after["missing_count"] == 0
    assert after["unique_missing_materials"] == []


# --------------------------------------------------------------------------- #
# Test 4 — Validation + Tenant-Isolation
# --------------------------------------------------------------------------- #
def test_manual_price_ohne_price_net_gibt_422(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.kalkulation.kalkuliere_lv",
        lambda db, lv_id, tenant_id: None,
    )
    token = _register(client, "resolve-inv@example.com")
    tid = _tenant_id(client, token)
    with _db() as db:
        lv_id = _seed_lv_with_missing_material(db, tid, "|Profile|Eckschiene|2500|")

    r = client.post(
        f"/api/v1/lvs/{lv_id}/gaps/resolve",
        headers=_auth(token),
        json={
            "material_dna": "|Profile|Eckschiene|2500|",
            "resolution_type": "manual_price",
            "value": {"unit": "lfm"},  # price_net fehlt
        },
    )
    assert r.status_code == 422


def test_fremder_tenant_bekommt_404(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.kalkulation.kalkuliere_lv",
        lambda db, lv_id, tenant_id: None,
    )
    owner = _register(client, "resolve-owner@example.com")
    stranger = _register(client, "resolve-stranger@example.com")
    tid_owner = _tenant_id(client, owner)
    with _db() as db:
        lv_id = _seed_lv_with_missing_material(
            db, tid_owner, "|Profile|Eckschiene|2500|"
        )

    r = client.post(
        f"/api/v1/lvs/{lv_id}/gaps/resolve",
        headers=_auth(stranger),
        json={
            "material_dna": "|Profile|Eckschiene|2500|",
            "resolution_type": "skip",
            "value": {},
        },
    )
    assert r.status_code == 404
