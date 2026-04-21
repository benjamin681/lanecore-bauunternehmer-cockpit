"""End-to-End: Gebinde-Entries treffen mit tolerantem Unit-Filter +
entpacktem Preis (B+4.2.7 Scope A)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.package_resolver import backfill_effective_units
from app.services.price_lookup import lookup_price


def _db():
    from app.core import database
    return database.SessionLocal()


def _seed(db, *, product_name, entry_unit, price_net,
          effective_unit=None, price_per_effective_unit=None,
          manufacturer=None):
    t = Tenant(name=f"Pkg-{product_name[:12]}", use_new_pricing=True)
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id,
        email=f"pkg_{abs(hash(product_name)) % 10_000_000}@example.com",
        password_hash=hash_password("pw"),
    )
    db.add(u)
    db.flush()
    pl = SupplierPriceList(
        tenant_id=t.id,
        supplier_name="Kemmler",
        list_name="Gebinde-Integration",
        valid_from=date(2026, 1, 1),
        source_file_path=f"/tmp/{product_name[:6]}.pdf",
        source_file_hash=f"h-{product_name[:6]}",
        status=PricelistStatus.APPROVED.value,
        is_active=True,
        uploaded_by_user_id=u.id,
    )
    db.add(pl)
    db.flush()
    e = SupplierPriceEntry(
        pricelist_id=pl.id,
        tenant_id=t.id,
        manufacturer=manufacturer,
        product_name=product_name,
        price_net=Decimal(str(price_net)),
        currency="EUR",
        unit=entry_unit,
        effective_unit=effective_unit or entry_unit,
        price_per_effective_unit=price_per_effective_unit or Decimal(str(price_net)),
    )
    db.add(e)
    db.commit()
    return t, e


# ---------------------------------------------------------------------------
# Integration-Tests
# ---------------------------------------------------------------------------
def test_karton_entry_mit_backfill_matcht_stueck_anfrage(client):
    """Kemmler-Karton-Entry: Parser hat effective_unit=unit belassen.
    Nach backfill_effective_units soll Stage 2c den Eintrag treffen und
    den Stueckpreis ausgeben."""
    db = _db()
    t, e = _seed(
        db,
        product_name="KV60 Kreuzverbinder für CD 60/27 - 100 Stk/Ktn.",
        entry_unit="€/Ktn.",
        price_net=12.00,
    )
    # Parser-simulierter Default: effective_unit=unit, price_per==price_net
    assert e.effective_unit == "€/Ktn."

    # Backfill
    changed = backfill_effective_units([e])
    db.commit()
    assert changed == 1
    assert e.effective_unit == "Stk."
    # SQLite rundtripped Numeric als float → Wert-, nicht Instanz-Vergleich
    assert float(e.price_per_effective_unit) == pytest.approx(0.12)

    # Lookup
    r = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="Kreuzverbinder CD 60",
        unit="Stk.",
        manufacturer=None,
        category=None,
    )
    assert r.price_source == "supplier_price"
    assert r.unit == "Stk."
    assert r.price == Decimal("0.1200")


def test_paket_m2_entry_liefert_m2_preis(client):
    """ROCKWOOL-Trennwandpl. 7,5 m²/Pak. für 45 EUR → 6 EUR/m²."""
    db = _db()
    t, e = _seed(
        db,
        product_name="ROCKWOOL Trennwandpl. Sonorock 1000x625x40 mm - 7,5 m²/Pak.",
        entry_unit="€/Paket",
        price_net=45.00,
        manufacturer="ROCKWOOL",
    )
    backfill_effective_units([e])
    db.commit()
    assert e.effective_unit == "m²"

    r = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="Sonorock 40",
        unit="m²",
        manufacturer="ROCKWOOL",
        category=None,
    )
    assert r.price_source == "supplier_price"
    assert r.unit == "m²"
    assert r.price == Decimal("6.0000")


def test_rolle_entry_m_pro_rolle(client):
    """Stuckband 30m/Rolle für 15 EUR → 0,5 EUR/m."""
    db = _db()
    t, e = _seed(
        db,
        product_name="Stuckband 30mm x 30 m 30 m/Rolle",
        entry_unit="€/Rolle",
        price_net=15.00,
    )
    backfill_effective_units([e])
    db.commit()

    r = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="Stuckband 30mm",
        unit="lfm",
        manufacturer=None,
        category=None,
    )
    assert r.price_source == "supplier_price"
    # effective_unit='m' matcht synonym gegen 'lfm'; Result-Unit ist 'm'
    assert r.unit == "m"
    assert r.price == Decimal("0.5000")


def test_entry_ohne_gebinde_muster_bleibt_unveraendert(client):
    """Normaler m²-Entry ohne Gebinde-Angabe: Backfill macht nichts,
    Lookup liefert unveraenderten Preis."""
    db = _db()
    t, e = _seed(
        db,
        product_name="Knauf DIAMANT 12,5 mm",
        entry_unit="m²",
        price_net=Decimal("3.50"),
        manufacturer="Knauf",
    )
    changed = backfill_effective_units([e])
    db.commit()
    assert changed == 0

    r = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="DIAMANT 12.5",
        unit="m²",
        manufacturer="Knauf",
        category=None,
    )
    assert r.price_source == "supplier_price"
    assert r.price == Decimal("3.5000")
    assert r.unit == "m²"


def test_bereits_vom_parser_entpackter_entry_wird_nicht_ueberschrieben(client):
    """Wenn der Parser effective_unit selbst gesetzt hat, bleibt das
    erhalten (auch wenn es nicht dem Namen entspricht)."""
    db = _db()
    t, e = _seed(
        db,
        product_name="Kreuzverbinder KV60 100 Stk/Ktn.",
        entry_unit="€/Ktn.",
        price_net=Decimal("10.00"),
        effective_unit="Stk.",
        price_per_effective_unit=Decimal("0.25"),  # bewusst abweichend
    )
    changed = backfill_effective_units([e])
    db.commit()
    assert changed == 0
    # Lookup liefert die Parser-Werte, nicht die Resolver-Werte
    r = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="Kreuzverbinder KV60",
        unit="Stk.",
        manufacturer=None,
        category=None,
    )
    assert r.price_source == "supplier_price"
    assert float(r.price) == pytest.approx(0.25)


def test_rabatt_wird_auf_effective_price_angewendet(client):
    """Rabatt auf einen Karton-Entry, der via Backfill auf Stueck
    entpackt ist: Rabatt trifft den ENTPACKTEN Preis, nicht den
    Gesamt-Kartonpreis."""
    db = _db()
    from app.models.pricing import TenantDiscountRule
    from app.models.user import User as _U
    t, e = _seed(
        db,
        product_name="KV60 Kreuzverbinder 100 Stk/Ktn.",
        entry_unit="€/Ktn.",
        price_net=Decimal("10.00"),
    )
    backfill_effective_units([e])
    # Hole einen User aus demselben Tenant (der wurde in _seed erstellt)
    u = db.query(_U).filter(_U.tenant_id == t.id).first()
    # Rabatt-Regel 20 % fuer Kemmler
    rule = TenantDiscountRule(
        tenant_id=t.id,
        supplier_name="Kemmler",
        discount_percent=Decimal("20.0"),
        valid_from=date(2026, 1, 1),
        created_by_user_id=u.id,
    )
    db.add(rule)
    db.commit()

    r = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="Kreuzverbinder",
        unit="Stk.",
        manufacturer=None,
        category=None,
    )
    assert r.price_source == "supplier_price"
    # 0.10 * 0.80 = 0.08
    assert float(r.price) == pytest.approx(0.08)
    assert float(r.applied_discount_percent) == pytest.approx(20.0)
