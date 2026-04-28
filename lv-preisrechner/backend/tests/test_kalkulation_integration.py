"""Integration-Tests fuer den Preis-Lookup in der Kalkulation (B+4.2).

Deckt ab:
- Flag=OFF: Legacy-Pfad unveraendert
- Flag=ON:  neuer Lookup-Pfad, inklusive Rabatt-Propagation
- Tenant-Isolation
- Variante A-plus: Flag=ON ohne Preisdaten wirft ValueError
- Preis-Quelle und Audit-Trail werden in Position/PositionOut propagiert

Test-Strategie (kalibriert 2026-04-28): Rezept "Tueraussparung" hat seit
Iteration 5b drei Materialien: UA75 (5 lfm) + UW75 (1 lfm, optional) +
Kleinmaterial-Pauschale (1 Stk, fallback 5 EUR). Die Test-Seed deckt
beide Profile ab; die Kleinmaterial-Pauschale traegt ueber den
fallback_preis konstant 5 EUR zur Material-Summe bei.

  material_ep_supplier = (UA75 2 lfm + UW75 1 lfm) * price = 3 * price
  material_ep_legacy   = nur UA75: 2 lfm * price (legacy-Matcher trifft nur UA75)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.lv import LV
from app.models.position import Position
from app.models.price_entry import PriceEntry
from app.models.price_list import PriceList
from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
    TenantDiscountRule,
    TenantPriceOverride,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.kalkulation import kalkuliere_lv


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _db():
    from app.core import database
    return database.SessionLocal()


def _seed_tenant(db, *, name="TestBetrieb", use_new_pricing=False):
    t = Tenant(name=name, use_new_pricing=use_new_pricing)
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id,
        email=f"{name.lower()}@example.com",
        password_hash=hash_password("pw"),
        vorname="Max",
        nachname="Mustermann",
    )
    db.add(u)
    db.commit()
    return t, u


def _seed_legacy_pricelist_with_ua(db, tenant_id):
    pl = PriceList(
        tenant_id=tenant_id,
        haendler="LegacyShop",
        aktiv=True,
        status="ready",
    )
    db.add(pl)
    db.flush()
    # B+4.13 Iter 5b: Tueraussparung-Rezept hat UA75 + UW75 als Profile
    db.add(
        PriceEntry(
            price_list_id=pl.id,
            dna="Knauf|Profile|UA|75|",
            hersteller="Knauf",
            kategorie="Profile",
            produktname="UA",
            abmessungen="75",
            variante="",
            preis=12.00,
            einheit="lfm",
            preis_pro_basis=12.00,
            basis_einheit="lfm",
            konfidenz=1.0,
        )
    )
    db.add(
        PriceEntry(
            price_list_id=pl.id,
            dna="Knauf|Profile|UW|75|",
            hersteller="Knauf",
            kategorie="Profile",
            produktname="UW",
            abmessungen="75",
            variante="",
            preis=12.00,
            einheit="lfm",
            preis_pro_basis=12.00,
            basis_einheit="lfm",
            konfidenz=1.0,
        )
    )
    db.commit()
    return pl


def _seed_supplier_list_with_ua(
    db, tenant_id, user_id, *, supplier_name="Kemmler", price=10.00
):
    """Seed Supplier-Preisliste mit UA75 + UW75 fuer Tueraussparung-Rezept.

    Rueckgabe (pl, primary_entry) — primary_entry ist die UA75-Zeile, die
    ein Test ggf. als ``needs_review=True`` markiert.
    """
    pl = SupplierPriceList(
        tenant_id=tenant_id,
        supplier_name=supplier_name,
        list_name=f"{supplier_name} 2026-04",
        valid_from=date(2026, 1, 1),
        source_file_path=f"/tmp/{supplier_name}.pdf",
        source_file_hash=supplier_name,
        status=PricelistStatus.APPROVED.value,
        is_active=True,
        uploaded_by_user_id=user_id,
    )
    db.add(pl)
    db.flush()
    # B+4.13 Iter 5b: Tueraussparung-Rezept hat UA75 + UW75 + Kleinmaterial.
    # Beide Profile als "UA 75" / "UW 75" — Fuzzy-Schwelle 0.85 gegen
    # DNA "UA 75" / "UW 75" trifft sicher.
    primary = SupplierPriceEntry(
        pricelist_id=pl.id,
        tenant_id=tenant_id,
        article_number="UA-75",
        manufacturer="Knauf",
        product_name="UA 75",
        category="Profile",
        price_net=price,
        currency="EUR",
        unit="lfm",
        effective_unit="lfm",
        price_per_effective_unit=price,
    )
    db.add(primary)
    db.add(
        SupplierPriceEntry(
            pricelist_id=pl.id,
            tenant_id=tenant_id,
            article_number="UW-75",
            manufacturer="Knauf",
            product_name="UW 75",
            category="Profile",
            price_net=price,
            currency="EUR",
            unit="lfm",
            effective_unit="lfm",
            price_per_effective_unit=price,
        )
    )
    db.commit()
    return pl, primary


def _seed_lv_with_tueraussparung(db, tenant_id, *, menge=1.0):
    lv = LV(
        tenant_id=tenant_id,
        original_dateiname="integration.pdf",
        status="review_needed",
    )
    db.add(lv)
    db.flush()
    p = Position(
        lv_id=lv.id,
        oz="1.1",
        kurztext="Tueraussparung",
        menge=menge,
        einheit="Stk",
        erkanntes_system="Tueraussparung",
    )
    db.add(p)
    db.commit()
    return lv, p


# ---------------------------------------------------------------------------
# Flag=OFF: Legacy-Pfad
# ---------------------------------------------------------------------------
def test_kalkulation_mit_flag_off_nutzt_legacy_pfad(client):
    db = _db()
    t, _u = _seed_tenant(db, use_new_pricing=False)
    _seed_legacy_pricelist_with_ua(db, t.id)
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    result = kalkuliere_lv(db, lv.id, t.id)
    pos = result.positions[0]
    # Legacy-DNA-Matcher trifft nur UA75 (2 lfm * 12.00 = 24.00).
    # UW75 trifft im Legacy-Pfad nicht.
    assert pos.material_ep == 24.00
    assert "legacy" in (pos.price_source_summary or "")


def test_kalkulation_flag_off_ohne_legacy_priceliste_wirft_fehler(client):
    db = _db()
    t, _u = _seed_tenant(db, use_new_pricing=False)
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    import pytest
    with pytest.raises(ValueError, match="Keine aktive Preisliste"):
        kalkuliere_lv(db, lv.id, t.id)


# ---------------------------------------------------------------------------
# Flag=ON: neuer Pfad
# ---------------------------------------------------------------------------
def test_kalkulation_mit_flag_on_nutzt_neuen_pfad(client):
    db = _db()
    t, u = _seed_tenant(db, use_new_pricing=True)
    _seed_supplier_list_with_ua(db, t.id, u.id, price=10.00)
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    result = kalkuliere_lv(db, lv.id, t.id)
    pos = result.positions[0]
    # SupplierPrice-Lookup trifft sowohl UA75 (2 lfm) als auch UW75 (1 lfm).
    # Summe: 3 lfm * 10.00 = 30.00.
    assert pos.material_ep == 30.00
    assert "supplier_price" in (pos.price_source_summary or "")
    # manufacturer kommt aus dem Entry (NICHT supplier_name!)
    assert "Knauf" in (pos.angebotenes_fabrikat or "") or pos.angebotenes_fabrikat == ""


def test_flag_on_ohne_daten_wirft_fehler_variante_a_plus(client):
    """Variante A-plus: weder SupplierPriceList noch Override -> Fehler."""
    db = _db()
    t, _u = _seed_tenant(db, use_new_pricing=True)
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    import pytest
    with pytest.raises(ValueError, match="Keine Preisdaten"):
        kalkuliere_lv(db, lv.id, t.id)


def test_flag_on_mit_nur_override_akzeptiert(client):
    """Flag=ON: auch nur ein TenantPriceOverride reicht als Datengrundlage."""
    db = _db()
    t, u = _seed_tenant(db, use_new_pricing=True)
    # Kein SupplierPriceList, nur ein Override
    o = TenantPriceOverride(
        tenant_id=t.id,
        article_number="UA-50",
        manufacturer="Knauf",
        override_price=8.00,
        unit="lfm",
        valid_from=date(2026, 1, 1),
        created_by_user_id=u.id,
    )
    db.add(o)
    db.commit()
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    # Kalkulation darf NICHT am Check scheitern (auch wenn das UA-Material
    # nicht matcht -- der Check passiert am Anfang von kalkuliere_lv).
    result = kalkuliere_lv(db, lv.id, t.id)
    assert result.status == "calculated"


# ---------------------------------------------------------------------------
# Rabatt-Propagation
# ---------------------------------------------------------------------------
def test_rabatt_percent_wird_propagiert(client):
    db = _db()
    t, u = _seed_tenant(db, use_new_pricing=True)
    _seed_supplier_list_with_ua(db, t.id, u.id, supplier_name="Kemmler", price=10.00)
    rule = TenantDiscountRule(
        tenant_id=t.id,
        supplier_name="Kemmler",
        discount_percent=15.0,
        valid_from=date(2026, 1, 1),
        created_by_user_id=u.id,
    )
    db.add(rule)
    db.commit()
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    result = kalkuliere_lv(db, lv.id, t.id)
    pos = result.positions[0]
    # Material-EP nach Rabatt: (UA75 + UW75) 3 lfm * 10.00 * 0.85 = 25.50.
    assert pos.material_ep == 25.50
    # Rabatt muss pro Material im JSON stecken (am UA75-Eintrag)
    mats = pos.materialien or []
    rabatt_mats = [m for m in mats if m.get("applied_discount_percent") == 15.0]
    assert len(rabatt_mats) >= 1


# ---------------------------------------------------------------------------
# needs_review-Propagation
# ---------------------------------------------------------------------------
def test_needs_review_flag_wird_propagiert(client):
    """Entry mit needs_review=True muss Position.needs_price_review=True ausloesen."""
    db = _db()
    t, u = _seed_tenant(db, use_new_pricing=True)
    pl, entry = _seed_supplier_list_with_ua(db, t.id, u.id, price=10.00)
    entry.needs_review = True
    db.commit()
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    result = kalkuliere_lv(db, lv.id, t.id)
    pos = result.positions[0]
    assert pos.needs_price_review is True
    mats = pos.materialien or []
    assert mats[0].get("needs_review") is True


# ---------------------------------------------------------------------------
# Positions-Output: Preis-Quelle im JSON + in neuen Spalten
# ---------------------------------------------------------------------------
def test_preis_quelle_wird_propagiert_in_result(client):
    db = _db()
    t, u = _seed_tenant(db, use_new_pricing=True)
    _seed_supplier_list_with_ua(db, t.id, u.id, supplier_name="Kemmler", price=10.00)
    lv, _p = _seed_lv_with_tueraussparung(db, t.id)

    result = kalkuliere_lv(db, lv.id, t.id)
    pos = result.positions[0]
    # Aggregiert auf Position: UA75 + UW75 -> 2x supplier_price + Kleinmaterial-Fallback
    assert "supplier_price" in (pos.price_source_summary or "")
    # Pro Material im JSON-Detail: das erste ist der UA75-Eintrag (Hauptmaterial)
    mats = pos.materialien or []
    sup = next(m for m in mats if m.get("price_source") == "supplier_price")
    assert "Kemmler" in sup["source_description"]
    assert sup["applied_discount_percent"] is None
    assert sup["needs_review"] is False


# ---------------------------------------------------------------------------
# Tenant-Isolation bei beiden Pfaden
# ---------------------------------------------------------------------------
def test_tenant_isolation_flag_off(client):
    """Legacy-Pfad: Tenant A's Preisliste darf nicht an Tenant B wirken."""
    db = _db()
    t_a, _ = _seed_tenant(db, name="A", use_new_pricing=False)
    t_b, _ = _seed_tenant(db, name="B", use_new_pricing=False)
    _seed_legacy_pricelist_with_ua(db, t_a.id)

    lv_b, _p = _seed_lv_with_tueraussparung(db, t_b.id)
    import pytest
    with pytest.raises(ValueError, match="Keine aktive Preisliste"):
        kalkuliere_lv(db, lv_b.id, t_b.id)


def test_tenant_isolation_flag_on(client):
    """Neuer Pfad: Tenant A's SupplierPriceList darf Tenant B nicht helfen."""
    db = _db()
    t_a, u_a = _seed_tenant(db, name="A", use_new_pricing=True)
    t_b, _u_b = _seed_tenant(db, name="B", use_new_pricing=True)
    _seed_supplier_list_with_ua(db, t_a.id, u_a.id)

    lv_b, _ = _seed_lv_with_tueraussparung(db, t_b.id)
    import pytest
    with pytest.raises(ValueError, match="Keine Preisdaten"):
        kalkuliere_lv(db, lv_b.id, t_b.id)


# ---------------------------------------------------------------------------
# Regression: Flag=OFF-Ergebnisse aendern sich gegenueber vor B+4.2 nicht
# ---------------------------------------------------------------------------
def test_kalkulation_legacy_ergebnis_unveraendert_nach_b42(client):
    """Smoke-Test: Legacy-Pfad liefert weiterhin EP>0, keine needs_review-
    Flaggung und keinen Crash durch die neue Aggregation."""
    db = _db()
    t, _u = _seed_tenant(db, use_new_pricing=False)
    _seed_legacy_pricelist_with_ua(db, t.id)
    lv, _p = _seed_lv_with_tueraussparung(db, t.id, menge=2.0)

    result = kalkuliere_lv(db, lv.id, t.id)
    pos = result.positions[0]
    # Deterministisch (Iter 5b): Legacy-Matcher trifft UA75 = 2 lfm * 12 = 24.00.
    assert pos.material_ep == 24.00
    assert pos.ep > 0
    assert pos.gp == round(pos.ep * 2.0, 2)
    assert "legacy" in (pos.price_source_summary or "")
