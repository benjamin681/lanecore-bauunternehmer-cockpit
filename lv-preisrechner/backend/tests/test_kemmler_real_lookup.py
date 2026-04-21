"""Integration-Tests: reale Kemmler-Produktnamen laufen durch den vollen
lookup_price-Pfad und landen in Stage 2 (supplier_price), NICHT in Stage 4
(estimated).

Das ist der produktionsrelevante End-to-End-Nachweis fuer B+4.2.5:
- material_normalizer wird vom price_lookup-Service eingesetzt.
- Reale Produktnamen aus tests/fixtures/kemmler_real_names.json werden
  in SupplierPriceEntries gespielt, die DNA-basierte Anfrage durchlaeuft
  den Lookup.
- Erwartung: price_source == "supplier_price" in allen positiven Faellen.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

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


FIXTURES = Path(__file__).parent / "fixtures" / "kemmler_real_names.json"


def _load_fixtures():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data["positives"], data["negatives"]


_positives, _negatives = _load_fixtures()


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------
def _db():
    from app.core import database
    return database.SessionLocal()


def _seed_tenant_with_entry(db, *, product_name: str, manufacturer: str | None,
                            category: str | None, unit: str = "m²"):
    t = Tenant(name=f"KemmlerTest-{product_name[:20]}", use_new_pricing=True)
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id,
        email=f"real_{abs(hash(product_name)) % 10_000_000}@example.com",
        password_hash=hash_password("pw"),
    )
    db.add(u)
    db.flush()
    pl = SupplierPriceList(
        tenant_id=t.id,
        supplier_name="Kemmler",
        list_name="Ausbau 2026-04 (Real-Fixture)",
        valid_from=date(2026, 1, 1),
        source_file_path="/tmp/fixture.pdf",
        source_file_hash=f"h-{product_name[:10]}",
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
        category=category,
        price_net=1.00,
        currency="EUR",
        unit=unit,
        effective_unit=unit,
        price_per_effective_unit=1.00,
    )
    db.add(e)
    db.commit()
    return t, e


def _query_from_dna(dna_pattern: str) -> dict:
    """Aus DNA-Pattern 'Hersteller|Kategorie|Produkt|Abm|Variante' die
    lookup_price-Parameter generieren (analog zu kalkulation._parse_dna_pattern)."""
    parts = [p.strip() for p in dna_pattern.split("|")]
    hersteller = parts[0] if len(parts) > 0 and parts[0] else None
    kategorie = parts[1] if len(parts) > 1 and parts[1] else None
    produkt = parts[2] if len(parts) > 2 else ""
    abmess = parts[3] if len(parts) > 3 else ""
    variante = parts[4] if len(parts) > 4 else ""
    material_name = " ".join(p for p in (produkt, abmess, variante) if p).strip()
    return dict(
        material_name=material_name,
        manufacturer=hersteller,
        category=kategorie,
    )


# ---------------------------------------------------------------------------
# Positive-Fixtures: muessen Stage 2 (supplier_price) treffen
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fixture", _positives, ids=[f["id"] for f in _positives])
def test_kemmler_real_name_reaches_supplier_price_stage(client, fixture):
    db = _db()
    # Einheiten-Heuristik fuer diese Fixtures:
    # - "30kg" / "25kg" / "800g" Pattern → unit "Sack"/"Fl." wuerden den
    #   Unit-Filter stoeren. Wir nutzen dasselbe `unit` auf beiden Seiten.
    # DNA enthaelt die Einheit nicht explizit → fix "m²" fuer Platten,
    # "m" fuer Profile, "Sack" fuer Putz, "Fl." fuer Brio.
    dna = fixture["dna_pattern"]
    fid = fixture["id"]
    if "ua_" in fid or "cw_" in fid:
        unit = "m"
    elif fid.startswith("gkb") or fid.startswith("gkf") or "_siniat" in fid or "_diamant" in fid or "silentboard" in fid:
        unit = "m²"
    elif "falzkleber" in fid:
        unit = "Fl."
    else:
        unit = "Sack"

    # Hersteller aus DNA extrahieren (leer = None)
    q = _query_from_dna(dna)
    mfr = q["manufacturer"]
    cat = q["category"]

    t, _e = _seed_tenant_with_entry(
        db,
        product_name=fixture["product_name"],
        manufacturer=mfr,
        category=cat,
        unit=unit,
    )
    result = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name=q["material_name"],
        unit=unit,
        manufacturer=mfr,
        category=cat,
    )
    assert result.price_source == "supplier_price", (
        f"Fixture {fid}: expected supplier_price stage, got {result.price_source}. "
        f"material='{q['material_name']}' product='{fixture['product_name']}'"
    )
    # Confidence in [0.85, 1.0] erwartet (exakter Match oder Fuzzy)
    assert result.match_confidence >= 0.85


# ---------------------------------------------------------------------------
# Negative-Fixtures: duerfen Stage 2 NICHT treffen
# ---------------------------------------------------------------------------
def _entry_mfr_for_negative(fid: str, product_name: str, query_mfr: str | None) -> str | None:
    """Fuer den wrong-manufacturer-Fall weicht der Entry-Hersteller bewusst
    vom Query-Hersteller ab (der Katalog enthaelt Knauf-Platten, die Anfrage
    sucht Siniat). Fuer alle anderen Negative-Cases stimmt der Entry-mfr
    mit dem im Produktnamen fuehrenden Hersteller ueberein."""
    if fid == "neg_wrong_manufacturer":
        return "Knauf"  # Entry traegt Knauf, Query sucht Siniat
    # sonst: ersten Hersteller-Token aus Produktname ziehen (oder query mfr)
    return query_mfr


@pytest.mark.parametrize("fixture", _negatives, ids=[f["id"] for f in _negatives])
def test_kemmler_negative_does_not_reach_supplier_price(client, fixture):
    db = _db()
    unit = "m²"
    q = _query_from_dna(fixture["dna_pattern"])
    entry_mfr = _entry_mfr_for_negative(fixture["id"], fixture["product_name"], q["manufacturer"])
    t, _e = _seed_tenant_with_entry(
        db,
        product_name=fixture["product_name"],
        manufacturer=entry_mfr,
        category=q["category"],
        unit=unit,
    )
    result = lookup_price(
        db=db,
        tenant_id=t.id,
        material_name=q["material_name"],
        unit=unit,
        manufacturer=q["manufacturer"],
        category=q["category"],
    )
    # Darf NICHT supplier_price treffen. Entweder "not_found" oder
    # "estimated" ist akzeptabel — Hauptsache kein Fuzzy-Fehltreffer.
    assert result.price_source != "supplier_price", (
        f"Negative {fixture['id']} wrongly matched at supplier_price. "
        f"product='{fixture['product_name']}' "
        f"pattern='{fixture['dna_pattern']}'"
    )


# ---------------------------------------------------------------------------
# Aggregate: Match-Rate ueber positive Fixtures >= 85 %
# ---------------------------------------------------------------------------
def test_kemmler_real_lookup_aggregate_match_rate(client):
    """Acceptance Criterion: in >=85% der positiven Fixtures greift der
    neue Fuzzy-Pfad (supplier_price) statt der Heuristik (estimated)."""
    db = _db()
    hits = 0
    for fx in _positives:
        fid = fx["id"]
        if "ua_" in fid or "cw_" in fid:
            unit = "m"
        elif fid.startswith("gkb") or fid.startswith("gkf") or "_siniat" in fid or "_diamant" in fid or "silentboard" in fid:
            unit = "m²"
        elif "falzkleber" in fid:
            unit = "Fl."
        else:
            unit = "Sack"
        q = _query_from_dna(fx["dna_pattern"])
        t, _e = _seed_tenant_with_entry(
            db,
            product_name=fx["product_name"],
            manufacturer=q["manufacturer"],
            category=q["category"],
            unit=unit,
        )
        r = lookup_price(
            db=db,
            tenant_id=t.id,
            material_name=q["material_name"],
            unit=unit,
            manufacturer=q["manufacturer"],
            category=q["category"],
        )
        if r.price_source == "supplier_price":
            hits += 1
    rate = hits / len(_positives)
    assert rate >= 0.85, (
        f"Aggregate Kemmler match rate {rate:.0%} ({hits}/{len(_positives)}) < 85%"
    )
