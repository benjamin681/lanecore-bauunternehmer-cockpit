"""Integration-Tests fuer den Preis-Lookup in der Kalkulation (B+4.2).

Deckt ab:
- Flag=OFF: Legacy-Pfad unveraendert
- Flag=ON:  neuer Lookup-Pfad, inklusive Rabatt-Propagation
- Tenant-Isolation
- Variante A-plus: Flag=ON ohne Preisdaten wirft ValueError
- Preis-Quelle und Audit-Trail werden in Position/PositionOut propagiert

Test-Strategie (umgestellt 2026-04-29): Tests verwenden jetzt das Rezept
"WC_Trennwand", das einen einzigen Material-Eintrag enthaelt (`|Bauelemente|
WC-Trennwand||` 1.0 Stk). Damit lassen sich die Lookup-Pfade pro Position
deterministisch testen. Vorher genutzte "Tueraussparung" wurde am 28./29.04.
auf eine Pauschal-Logik (0 Material-Eintraege) kalibriert und ist als
Test-Anker daher nicht mehr geeignet.

  material_ep = 1 Stk * price (WC-Trennwand-Einheitspreis aus dem Lookup)
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


def _seed_legacy_pricelist_with_wc(db, tenant_id):
    """Seed Legacy-PriceList mit einem WC-Trennwand-Eintrag fuer den
    Single-Material-Test-Pfad."""
    pl = PriceList(
        tenant_id=tenant_id,
        haendler="LegacyShop",
        aktiv=True,
        status="ready",
    )
    db.add(pl)
    db.flush()
    db.add(
        PriceEntry(
            price_list_id=pl.id,
            dna="|Bauelemente|WC-Trennwand||",
            hersteller="",
            kategorie="Bauelemente",
            produktname="WC-Trennwand",
            abmessungen="",
            variante="",
            preis=12.00,
            einheit="Stk",
            preis_pro_basis=12.00,
            basis_einheit="Stk",
            konfidenz=1.0,
        )
    )
    db.commit()
    return pl


# Backwards-compat-Alias falls aeltere Test-Nutzungen noch vorkommen.
_seed_legacy_pricelist_with_ua = _seed_legacy_pricelist_with_wc


def _seed_supplier_list_with_wc(
    db, tenant_id, user_id, *, supplier_name="Kemmler", price=10.00
):
    """Seed Supplier-Preisliste mit einem WC-Trennwand-Eintrag.

    Rueckgabe (pl, entry).
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
    entry = SupplierPriceEntry(
        pricelist_id=pl.id,
        tenant_id=tenant_id,
        article_number="WC-TR",
        manufacturer="Knauf",
        product_name="WC-Trennwand",
        category="Bauelemente",
        price_net=price,
        currency="EUR",
        unit="Stk",
        effective_unit="Stk",
        price_per_effective_unit=price,
    )
    db.add(entry)
    db.commit()
    return pl, entry


# Alias fuer Aufruferseite, die noch den alten Namen hat.
_seed_supplier_list_with_ua = _seed_supplier_list_with_wc


def _seed_lv_with_tueraussparung(db, tenant_id, *, menge=1.0):
    """Seed LV mit einer Position System=WC_Trennwand fuer den Single-Material-
    Lookup-Test. Funktionsname historisch — die Implementierung nutzt seit
    2026-04-29 WC_Trennwand statt Tueraussparung."""
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
        kurztext="WC-Trennwand",
        menge=menge,
        einheit="Stk",
        erkanntes_system="WC_Trennwand",
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
    assert pos.material_ep == 12.00  # 1 Stk * 12.00 (legacy)
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
    assert pos.material_ep == 10.00  # 1 Stk * 10.00 (supplier)
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
    assert pos.material_ep == 8.50  # 1 Stk * 10.00 * 0.85 (15%-Rabatt)
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
    assert pos.material_ep == 12.00  # 1 Stk * 12.00 (legacy)
    assert pos.ep > 0
    assert pos.gp == round(pos.ep * 2.0, 2)
    assert "legacy" in (pos.price_source_summary or "")
