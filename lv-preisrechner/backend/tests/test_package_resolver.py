"""Tests fuer package_resolver (B+4.2.7 Scope A).

Fixtures sind an realen Kemmler-04/2026-Artikelnamen angelehnt.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.package_resolver import (
    backfill_effective_units,
    resolve_package,
)


# ---------------------------------------------------------------------------
# Positive: Gebinde-Einheit + Entpackungsmuster → entpackter Einzelpreis
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "unit,name,price,exp_unit,exp_price",
    [
        # Karton (Ktn.)
        ("€/Ktn.", "KV60 Kreuzverbinder fuer CD 60/27 gestreckt, 100 Stk/Ktn.", 12.0, "Stk.", Decimal("0.1200")),
        ("€/Ktn.", "DA125 Direktabhänger 125 mm - 100 Stk/Ktn.", 25.0, "Stk.", Decimal("0.2500")),
        ("€/Ktn.", "Kemmler NA60 Noniusabhänger - 100 Stk/Ktn.", 30.0, "Stk.", Decimal("0.3000")),
        ("Ktn.", "Ankerschnellabhänger 100 Stk/Ktn.", 40.0, "Stk.", Decimal("0.4000")),
        # Paket (Pak.)
        ("€/Paket", "OWA Spannabhänger Nr. 12/44 100 St./Pak.", 10.0, "Stk.", Decimal("0.1000")),
        ("€/Paket", "ACP Gipsplattenschrauben CE 3,9x25 mm - 1000 St./Pak.", 50.0, "Stk.", Decimal("0.0500")),
        ("€/Paket", "Anschlusswinkel 50 St./Pak.", 7.5, "Stk.", Decimal("0.1500")),
        # Paket mit m² (Trennwand-Platten)
        ("€/Paket", "ROCKWOOL Trennwandpl. Sonorock 1000x625x40 mm - 7,5 m²/Pak.", 45.0, "m²", Decimal("6.0000")),
        ("€/Paket", "Knauf Trennwandpl. Thermolan 9,375 m²/Pak.", 28.125, "m²", Decimal("3.0000")),
        # Rolle (m/Rolle)
        ("€/Rolle", "Kemmler Dachrinnenschlauch 210 mm x 100 m/Rolle", 50.0, "m", Decimal("0.5000")),
        ("€/Rolle", "Stuckband-EK 30mm x 30 m 30 m/Rolle", 15.0, "m", Decimal("0.5000")),
        ("€/Rolle", "Schutzvlies 1000 mm x 50 m/Rolle", 100.0, "m", Decimal("2.0000")),
        # Bund
        ("€/m", "OWA Tragprofil BL=3750 mm - 20 St./Bd.", 2.0, "€/m", Decimal("2")),
        # Alternative Schreibweise "a 50 Stk"
        ("€/Paket", "Knauf Universalverbinder Pak. = 100 Stk.", 20.0, "Stk.", Decimal("0.2000")),
    ],
)
def test_resolve_package_entpackung(unit, name, price, exp_unit, exp_price):
    got_unit, got_price = resolve_package(unit, name, price)
    assert got_unit == exp_unit, f"unit: expected {exp_unit!r} got {got_unit!r}"
    assert got_price == exp_price, f"price: expected {exp_price} got {got_price}"


# ---------------------------------------------------------------------------
# Negativ: Nicht-Gebinde / kein Muster / Default-Fall
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "unit,name,price,exp_unit,exp_price",
    [
        ("m²", "Knauf DIAMANT Hartgipspl. GKFI 2000x1250x12,5 mm", 3.50, "m²", Decimal("3.50")),
        ("lfm", "CW-Profil 100x50x0,6 mm BL=2600 mm", 2.80, "lfm", Decimal("2.80")),
        ("Sack", "Knauf Goldband 30 kg/Sack", 8.50, "Sack", Decimal("8.50")),
        # Gebinde-Einheit, aber KEIN Entpackungsmuster im Namen
        ("€/Ktn.", "Kemmler Mysteriöser Karton-Artikel", 10.0, "€/Ktn.", Decimal("10.0")),
        # leere Inputs
        ("", "irgendetwas", 5.0, "", Decimal("5.0")),
        ("€/Ktn.", "", 5.0, "€/Ktn.", Decimal("5.0")),
    ],
)
def test_resolve_package_default(unit, name, price, exp_unit, exp_price):
    got_unit, got_price = resolve_package(unit, name, price)
    assert got_unit == exp_unit
    assert got_price == exp_price


# ---------------------------------------------------------------------------
# Edge: Umlaute, Dezimal-Komma, mehrere Zahlen im Namen
# ---------------------------------------------------------------------------
def test_resolve_package_umlaute_ascii_form():
    u, p = resolve_package("€/Ktn.", "Kemmler Abhänger 50 Stueck/Ktn.", 25.0)
    assert u == "Stk."
    assert p == Decimal("0.5000")


def test_resolve_package_umlaute_unicode_form():
    u, p = resolve_package("€/Ktn.", "Kemmler Abhänger 50 Stück/Ktn.", 25.0)
    assert u == "Stk."
    assert p == Decimal("0.5000")


def test_resolve_package_dezimal_menge_komma():
    u, p = resolve_package("€/Pak.", "Platte 7,5 m²/Pak.", Decimal("45.00"))
    assert u == "m²"
    assert p == Decimal("6.0000")


def test_resolve_package_mehrere_zahlen_im_namen():
    # Muster greift nur auf "100 Stk/Ktn." — 60/27 im Profil-Namen
    # darf nicht ausgewertet werden.
    u, p = resolve_package("€/Ktn.", "NA60 Abhänger für CD 60/27 - 100 Stk/Ktn.", 30.0)
    assert u == "Stk."
    assert p == Decimal("0.3000")


def test_resolve_package_price_as_float_string_decimal():
    # API akzeptiert float, int, str, Decimal
    for price in (12.0, 12, "12", "12.00", Decimal("12")):
        u, p = resolve_package("€/Ktn.", "X 100 Stk/Ktn.", price)
        assert u == "Stk."
        assert p == Decimal("0.1200")


# ---------------------------------------------------------------------------
# backfill_effective_units
# ---------------------------------------------------------------------------
class _FakeEntry:
    def __init__(self, **kw):
        self.unit = kw.get("unit")
        self.effective_unit = kw.get("effective_unit", self.unit)
        self.product_name = kw.get("product_name")
        self.price_net = kw.get("price_net")
        self.price_per_effective_unit = kw.get("price_per_effective_unit", self.price_net)


def test_backfill_aendert_nur_gebinde_faelle():
    entries = [
        _FakeEntry(unit="€/Ktn.", product_name="X 100 Stk/Ktn.", price_net=Decimal("10.00")),
        _FakeEntry(unit="m²", product_name="Platte 12,5 mm", price_net=Decimal("3.50")),
        _FakeEntry(unit="€/Rolle", product_name="Stuckband 50 m/Rolle", price_net=Decimal("25.00")),
        _FakeEntry(unit="€/Ktn.", product_name="Karton ohne Auflösungshinweis", price_net=Decimal("8.00")),
    ]
    changed = backfill_effective_units(entries)
    assert changed == 2, f"expected 2 changes, got {changed}"
    assert entries[0].effective_unit == "Stk."
    assert entries[0].price_per_effective_unit == Decimal("0.1000")
    assert entries[1].effective_unit == "m²"
    assert entries[2].effective_unit == "m"
    assert entries[2].price_per_effective_unit == Decimal("0.5000")
    # Unveraendert (kein Entpackungsmuster)
    assert entries[3].effective_unit == "€/Ktn."


def test_backfill_respektiert_bereits_gesetzte_effective_unit():
    """Wenn der Parser bereits effective_unit != unit gesetzt hat, NICHT ueberschreiben."""
    e = _FakeEntry(
        unit="€/Ktn.",
        effective_unit="Stk.",  # Parser hat das schon gemacht
        product_name="X 100 Stk/Ktn.",
        price_net=Decimal("10.00"),
        price_per_effective_unit=Decimal("0.25"),  # bewusst anders
    )
    changed = backfill_effective_units([e])
    assert changed == 0
    assert e.effective_unit == "Stk."
    assert e.price_per_effective_unit == Decimal("0.25")  # unveraendert


def test_backfill_ignoriert_none_werte():
    e = _FakeEntry(unit=None, product_name="egal", price_net=Decimal("1"))
    e2 = _FakeEntry(unit="Ktn.", product_name=None, price_net=Decimal("1"))
    e3 = _FakeEntry(unit="Ktn.", product_name="X 100 Stk/Ktn.", price_net=None)
    changed = backfill_effective_units([e, e2, e3])
    assert changed == 0
