"""End-to-End-Tests fuer das tolerante Unit-Matching in price_lookup
(B+4.2.6 Scope A).

Szenarien: Der SupplierPriceEntry traegt eine abweichende Unit-Form
als die Lookup-Query, aber die Synonym-Tabelle im unit_normalizer
erklaert beide Formen als aequivalent. Stage 2c muss das erkennen.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.price_lookup import lookup_price


def _db():
    from app.core import database
    return database.SessionLocal()


def _seed(db, *, entry_unit: str, product_name: str, manufacturer: str | None):
    t = Tenant(name=f"Unit-{entry_unit}-{product_name[:8]}", use_new_pricing=True)
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id,
        email=f"unit_{abs(hash((entry_unit, product_name))) % 10_000_000}@example.com",
        password_hash=hash_password("pw"),
    )
    db.add(u)
    db.flush()
    pl = SupplierPriceList(
        tenant_id=t.id,
        supplier_name="Kemmler",
        list_name="Unit-Tolerance-Test",
        valid_from=date(2026, 1, 1),
        source_file_path=f"/tmp/{entry_unit}.pdf",
        source_file_hash=f"h-{entry_unit}-{product_name[:6]}",
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
        price_net=1.23,
        currency="EUR",
        unit=entry_unit,
        effective_unit=entry_unit,
        price_per_effective_unit=1.23,
    )
    db.add(e)
    db.commit()
    return t


@pytest.mark.parametrize(
    "entry_unit,query_unit",
    [
        ("m", "lfm"),
        ("lfm", "m"),
        ("Stk.", "St."),
        ("St.", "Stück"),
        ("m²", "qm"),
        ("€/m", "lfm"),  # Entry mit Currency-Prefix — der Normalizer strippt das
    ],
    ids=["m-vs-lfm", "lfm-vs-m", "stk-vs-st", "st-vs-stueck", "m2-vs-qm", "eur-m-vs-lfm"],
)
def test_unit_tolerance_stage_2c_match(client, entry_unit, query_unit):
    db = _db()
    t = _seed(
        db,
        entry_unit=entry_unit,
        product_name="CW-Profil 100",
        manufacturer=None,
    )
    result = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="CW 100",
        unit=query_unit,
        manufacturer=None,
        category=None,
    )
    assert result.price_source == "supplier_price", (
        f"Entry-Unit {entry_unit!r} gegen Query-Unit {query_unit!r} muss "
        f"via Synonym greifen. Got: {result.price_source}"
    )


def test_unit_tolerance_rejects_unrelated_units(client):
    """Kontroll-Test: 'kg' und 'lfm' duerfen NICHT als gleich gelten."""
    db = _db()
    t = _seed(
        db,
        entry_unit="kg",
        product_name="CW-Profil 100 Dummy-Sack",
        manufacturer=None,
    )
    result = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name="CW 100",
        unit="lfm",
        manufacturer=None,
        category=None,
    )
    # kein Supplier-Hit (Unit passt nicht); Estimated braucht Kategorie,
    # also not_found.
    assert result.price_source != "supplier_price"
