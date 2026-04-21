"""Tests für price_lookup.py — die 5-stufige Lookup-Kaskade.

Aufbau:
- Jede Test-Funktion baut sich ihre Fixture-Daten über die DB-Session
  direkt (kein HTTP-Layer nötig, da der Service isoliert ist).
- Ein Helper `_seed_tenant()` legt Tenant + User an; weitere Helpers
  füllen Overrides, Supplier-Preislisten, Rabatt-Regeln, Legacy-Einträge.
"""

from __future__ import annotations

import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

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
from app.services.price_lookup import (
    FUZZY_MATCH_THRESHOLD,
    PriceLookupResult,
    lookup_price,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _db(client) -> Session:
    # Late binding: conftest.py ueberschreibt database.SessionLocal pro Test;
    # wir duerfen daher nicht die Top-Level-Referenz cachen.
    from app.core import database
    return database.SessionLocal()


def _seed_tenant(db: Session, name: str = "Tenant A") -> tuple[str, str]:
    t = Tenant(name=name)
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id,
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        vorname="Max",
        nachname="Mustermann",
    )
    db.add(u)
    db.commit()
    return t.id, u.id


def _seed_supplier_list(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    supplier_name: str = "Kemmler",
    is_active: bool = True,
    status: str = PricelistStatus.APPROVED.value,
    valid_from: date | None = None,
) -> SupplierPriceList:
    pl = SupplierPriceList(
        tenant_id=tenant_id,
        supplier_name=supplier_name,
        list_name=f"{supplier_name} 2026-04",
        valid_from=valid_from or date(2026, 1, 1),
        source_file_path=f"/tmp/{uuid.uuid4().hex}.pdf",
        source_file_hash=uuid.uuid4().hex,
        status=status,
        is_active=is_active,
        uploaded_by_user_id=user_id,
    )
    db.add(pl)
    db.commit()
    return pl


def _seed_entry(
    db: Session,
    *,
    pricelist: SupplierPriceList,
    product_name: str,
    unit: str = "m²",
    effective_unit: str | None = None,
    price: float = 12.50,
    article_number: str | None = None,
    manufacturer: str | None = "Knauf",
    category: str | None = "Gipskarton",
    needs_review: bool = False,
) -> SupplierPriceEntry:
    e = SupplierPriceEntry(
        pricelist_id=pricelist.id,
        tenant_id=pricelist.tenant_id,
        article_number=article_number,
        manufacturer=manufacturer,
        product_name=product_name,
        category=category,
        price_net=price,
        currency="EUR",
        unit=unit,
        effective_unit=effective_unit or unit,
        price_per_effective_unit=price,
        needs_review=needs_review,
    )
    db.add(e)
    db.commit()
    return e


def _seed_override(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    article_number: str,
    price: float,
    unit: str = "m²",
    manufacturer: str | None = "Knauf",
    valid_from: date | None = None,
    valid_until: date | None = None,
) -> TenantPriceOverride:
    o = TenantPriceOverride(
        tenant_id=tenant_id,
        article_number=article_number,
        manufacturer=manufacturer,
        override_price=price,
        unit=unit,
        valid_from=valid_from or date(2026, 1, 1),
        valid_until=valid_until,
        created_by_user_id=user_id,
    )
    db.add(o)
    db.commit()
    return o


def _seed_discount(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    supplier_name: str,
    discount_percent: float = 10.0,
    category: str | None = None,
    valid_from: date | None = None,
    valid_until: date | None = None,
) -> TenantDiscountRule:
    r = TenantDiscountRule(
        tenant_id=tenant_id,
        supplier_name=supplier_name,
        discount_percent=discount_percent,
        category=category,
        valid_from=valid_from or date(2026, 1, 1),
        valid_until=valid_until,
        created_by_user_id=user_id,
    )
    db.add(r)
    db.commit()
    return r


def _seed_legacy(
    db: Session,
    *,
    tenant_id: str,
    produktname: str,
    preis: float,
    einheit: str = "m²",
    hersteller: str = "Knauf",
    aktiv: bool = True,
) -> PriceEntry:
    pl = PriceList(
        tenant_id=tenant_id,
        haendler="LegacyShop",
        aktiv=aktiv,
    )
    db.add(pl)
    db.flush()
    e = PriceEntry(
        price_list_id=pl.id,
        dna=f"{hersteller}|Gipskarton|{produktname}||",
        hersteller=hersteller,
        produktname=produktname,
        preis=preis,
        einheit=einheit,
        preis_pro_basis=preis,
        basis_einheit=einheit,
        kategorie="Gipskarton",
    )
    db.add(e)
    db.commit()
    return e


# ---------------------------------------------------------------------------
# Stufe 1 — Override
# ---------------------------------------------------------------------------
def test_lookup_stufe1_tenant_override_matcht_auf_article_number(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    _seed_override(db, tenant_id=tid, user_id=uid, article_number="A-123", price=9.99)

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="irgendwas",
        unit="m²",
        article_number="A-123",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "override"
    assert result.price == Decimal("9.99")
    assert result.match_confidence == 1.0
    assert result.needs_review is False
    assert any(d["stage"] == "override" and d["matched"] for d in result.lookup_details)


def test_lookup_stufe1_override_wird_nicht_rabattiert(client):
    """Kritisch: Override + vorhandene Rabatt-Regel -> Override gewinnt, 0 % Rabatt."""
    db = _db(client)
    tid, uid = _seed_tenant(db)
    _seed_override(db, tenant_id=tid, user_id=uid, article_number="A-999", price=20.00)
    _seed_discount(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler", discount_percent=50.0)

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Egal",
        unit="m²",
        article_number="A-999",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "override"
    assert result.price == Decimal("20.00")
    assert result.applied_discount_percent is None
    assert result.original_price == Decimal("20.00")


def test_lookup_override_ausserhalb_gueltigkeit_wird_ignoriert(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    _seed_override(
        db,
        tenant_id=tid,
        user_id=uid,
        article_number="A-OLD",
        price=5.00,
        valid_from=date(2020, 1, 1),
        valid_until=date(2020, 12, 31),
    )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="X",
        unit="m²",
        article_number="A-OLD",
        today=date(2026, 4, 21),
    )
    # Kein Treffer in keiner Stufe -> not_found
    assert result.price_source == "not_found"
    assert result.price is None
    assert result.needs_review is True


# ---------------------------------------------------------------------------
# Stufe 2 — Supplier-Price
# ---------------------------------------------------------------------------
def test_lookup_stufe2_supplier_price_mit_rabatt(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler")
    _seed_entry(db, pricelist=pl, product_name="Knauf GKB 12,5", article_number="KNF-GKB-125", price=10.00)
    _seed_discount(
        db, tenant_id=tid, user_id=uid, supplier_name="Kemmler", discount_percent=10.0
    )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Knauf GKB 12,5",
        unit="m²",
        article_number="KNF-GKB-125",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "supplier_price"
    assert result.original_price == Decimal("10.00")
    assert result.applied_discount_percent == Decimal("10.0")
    assert result.price == Decimal("9.0000")
    assert "Rabatt" in result.source_description


def test_lookup_stufe2_supplier_price_ohne_rabatt_wenn_regel_fehlt(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid, supplier_name="Baumit")
    _seed_entry(db, pricelist=pl, product_name="Baumit Putz", article_number="BAU-1", price=5.00)
    # Rabatt existiert nur für Kemmler, nicht Baumit
    _seed_discount(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler", discount_percent=25.0)

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Baumit Putz",
        unit="m²",
        article_number="BAU-1",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "supplier_price"
    assert result.applied_discount_percent is None
    assert result.price == Decimal("5.0000")


def test_lookup_stufe2_kategoriespezifischer_rabatt(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler")
    _seed_entry(
        db,
        pricelist=pl,
        product_name="Gipskarton-Platte",
        article_number="GK-1",
        category="Gipskarton",
        price=10.00,
    )
    # Allgemeiner 5%-Rabatt + spezifischer 15%-Rabatt fuer Gipskarton
    _seed_discount(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler", discount_percent=5.0)
    _seed_discount(
        db,
        tenant_id=tid,
        user_id=uid,
        supplier_name="Kemmler",
        discount_percent=15.0,
        category="Gipskarton",
    )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Gipskarton-Platte",
        unit="m²",
        article_number="GK-1",
        today=date(2026, 4, 21),
    )
    assert result.applied_discount_percent == Decimal("15.0")
    assert result.price == Decimal("8.5000")


def test_lookup_stufe2_fuzzy_fallback_wenn_article_number_fehlt(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid)
    _seed_entry(
        db,
        pricelist=pl,
        product_name="Knauf Multifinish Universal Gips-Spachtelmasse",
        price=1.44,
    )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Knauf Multifinish Universal Spachtelmasse",  # leicht abweichend
        unit="m²",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "supplier_price"
    assert result.match_confidence >= FUZZY_MATCH_THRESHOLD


# ---------------------------------------------------------------------------
# Stufe 3 — Legacy
# ---------------------------------------------------------------------------
def test_lookup_stufe3_fallback_auf_legacy_priceentry(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    # Keine aktive Supplier-Liste, aber ein Legacy-PriceEntry
    _seed_legacy(
        db,
        tenant_id=tid,
        produktname="Knauf Uniflott Fugenspachtel",
        preis=1.85,
    )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Knauf Uniflott Fugenspachtel",
        unit="m²",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "legacy_price"
    assert result.price == Decimal("1.8500")
    assert result.supplier_name == "Knauf"


# ---------------------------------------------------------------------------
# Stufe 4 — Heuristik / Schätzung
# ---------------------------------------------------------------------------
def test_lookup_stufe4_estimated_mit_heuristik(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    # Drei Entries in Kategorie "Putzprofile", keine Liste aktiv fuer Direktmatch
    pl = _seed_supplier_list(
        db, tenant_id=tid, user_id=uid, is_active=False, status=PricelistStatus.APPROVED.value
    )
    for name, price in [
        ("Profil A", 1.00),
        ("Profil B", 2.00),
        ("Profil C", 3.00),
    ]:
        _seed_entry(
            db,
            pricelist=pl,
            product_name=name,
            category="Putzprofile",
            unit="lfm",
            effective_unit="lfm",
            price=price,
        )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Putzprofil XYZ",
        unit="lfm",
        category="Putzprofile",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "estimated"
    assert result.price == Decimal("2.0000")
    assert result.needs_review is True
    assert result.match_confidence == 0.5


def test_lookup_stufe4_estimated_ohne_kategorie_wird_not_found(client):
    db = _db(client)
    tid, _uid = _seed_tenant(db)

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Irgendwas",
        unit="m²",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "not_found"
    # Details muessen zeigen dass Estimate wegen Kategorie uebersprungen wurde
    est = [d for d in result.lookup_details if d["stage"] == "estimated"]
    assert est and est[0]["matched"] is False
    assert "Kategorie" in est[0].get("reason", "")


# ---------------------------------------------------------------------------
# Stufe 5 — not_found
# ---------------------------------------------------------------------------
def test_lookup_stufe5_not_found_triggert_review(client):
    db = _db(client)
    tid, _uid = _seed_tenant(db)

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Exotisches Zeug",
        unit="m²",
        category="UnbekannteKategorie",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "not_found"
    assert result.price is None
    assert result.needs_review is True
    # Audit-Trail muss alle 4 vorangehenden Stufen gecheckt haben
    stages = [d["stage"] for d in result.lookup_details]
    assert stages == ["override", "supplier_price", "legacy_price", "estimated", "not_found"]


# ---------------------------------------------------------------------------
# Tenant-Isolation
# ---------------------------------------------------------------------------
def test_lookup_fremder_tenant_override_wird_ignoriert(client):
    db = _db(client)
    tid_a, uid_a = _seed_tenant(db, name="A")
    tid_b, _uid_b = _seed_tenant(db, name="B")
    _seed_override(db, tenant_id=tid_a, user_id=uid_a, article_number="X-1", price=99.0)

    # Tenant B fragt nach A-1 -> darf A's Override NICHT sehen
    result = lookup_price(
        db=db,
        tenant_id=tid_b,
        material_name="Material",
        unit="m²",
        article_number="X-1",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "not_found"


def test_lookup_fremder_tenant_supplier_price_wird_ignoriert(client):
    db = _db(client)
    tid_a, uid_a = _seed_tenant(db, name="A")
    tid_b, _uid_b = _seed_tenant(db, name="B")
    pl = _seed_supplier_list(db, tenant_id=tid_a, user_id=uid_a)
    _seed_entry(db, pricelist=pl, product_name="Secret Product", article_number="SEC-1", price=77.0)

    result = lookup_price(
        db=db,
        tenant_id=tid_b,
        material_name="Secret Product",
        unit="m²",
        article_number="SEC-1",
        today=date(2026, 4, 21),
    )
    assert result.price_source == "not_found"


# ---------------------------------------------------------------------------
# Rabatt-Edge-Cases
# ---------------------------------------------------------------------------
def test_rabatt_nur_im_gueltigen_zeitraum(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler")
    _seed_entry(db, pricelist=pl, product_name="X", article_number="X-1", price=10.0)
    _seed_discount(
        db,
        tenant_id=tid,
        user_id=uid,
        supplier_name="Kemmler",
        discount_percent=20.0,
        valid_from=date(2025, 1, 1),
        valid_until=date(2025, 12, 31),
    )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="X",
        unit="m²",
        article_number="X-1",
        today=date(2026, 4, 21),
    )
    assert result.applied_discount_percent is None
    assert result.price == Decimal("10.0000")


def test_mehrere_rabatt_regeln_spezifischer_gewinnt(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler")
    _seed_entry(
        db,
        pricelist=pl,
        product_name="Platte",
        article_number="PL-1",
        category="Gipskarton",
        price=100.0,
    )
    _seed_discount(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler", discount_percent=5.0)
    _seed_discount(
        db,
        tenant_id=tid,
        user_id=uid,
        supplier_name="Kemmler",
        discount_percent=20.0,
        category="Gipskarton",
    )

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Platte",
        unit="m²",
        article_number="PL-1",
        today=date(2026, 4, 21),
    )
    assert result.applied_discount_percent == Decimal("20.0")


# ---------------------------------------------------------------------------
# Audit-Trail
# ---------------------------------------------------------------------------
def test_lookup_details_enthaelt_alle_geprueften_stufen(client):
    db = _db(client)
    tid, _uid = _seed_tenant(db)

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Nix da",
        unit="m²",
        category="Unknown",
        today=date(2026, 4, 21),
    )
    stages = [d["stage"] for d in result.lookup_details]
    assert stages == ["override", "supplier_price", "legacy_price", "estimated", "not_found"]
    # Keine Stufe hat gematcht
    assert all(d.get("matched", False) is False for d in result.lookup_details)


def test_source_description_lesbar_formuliert_fuer_supplier(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler")
    _seed_entry(db, pricelist=pl, product_name="Y", article_number="Y-1", price=10.0)
    _seed_discount(db, tenant_id=tid, user_id=uid, supplier_name="Kemmler", discount_percent=12.5)

    result = lookup_price(
        db=db,
        tenant_id=tid,
        material_name="Y",
        unit="m²",
        article_number="Y-1",
        today=date(2026, 4, 21),
    )
    # "Kemmler-Listenpreis, -12.5% Rabatt"
    desc = result.source_description
    assert "Kemmler" in desc
    assert "12.5" in desc
    assert "Rabatt" in desc


# ---------------------------------------------------------------------------
# Performance-Stichprobe
# ---------------------------------------------------------------------------
def test_lookup_unter_100ms_fuer_typische_anfrage(client):
    db = _db(client)
    tid, uid = _seed_tenant(db)
    pl = _seed_supplier_list(db, tenant_id=tid, user_id=uid)
    # 200 Entries -- realistisch fuer eine kleine Preisliste
    for i in range(200):
        _seed_entry(
            db,
            pricelist=pl,
            product_name=f"Artikel {i}",
            article_number=f"ART-{i:04d}",
            price=1.0 + i * 0.01,
        )

    start = time.perf_counter()
    for _ in range(10):
        lookup_price(
            db=db,
            tenant_id=tid,
            material_name="Artikel 150",
            unit="m²",
            article_number="ART-0150",
            today=date(2026, 4, 21),
        )
    elapsed_per_call_ms = (time.perf_counter() - start) * 100
    assert elapsed_per_call_ms < 100, f"Lookup zu langsam: {elapsed_per_call_ms:.1f}ms"


# ---------------------------------------------------------------------------
# Feature-Flag-Default
# ---------------------------------------------------------------------------
def test_tenant_use_new_pricing_defaults_to_false(client):
    db = _db(client)
    t = Tenant(name="Flag-Test")
    db.add(t)
    db.commit()
    assert t.use_new_pricing is False
