"""B+4.2.7 Teil 1 — Golden-Tests fuer den Pieces-per-Length-Resolver.

Hintergrund: Kemmler-Profile-Entries wie
``CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.`` tragen als `price_net`
den Gesamt-Bundle-Preis (167,40 EUR), obwohl `unit` bereits „€/m" ist.
Die bestehenden `resolve_package`-Muster R1..R4 greifen nur bei
Gebinde-Einheiten (Ktn./Pak./Bd./Rolle) und rühren diesen Fall nicht an.

Die neue Funktion :func:`resolve_pieces_per_length` schliesst diese
Luecke — sie entpackt Bundle-Preise genau dann, wenn die Einheit bereits
eine Laenge ist und der Parser bereits `pieces_per_package` +
`package_size` strukturell aus der Produktbeschreibung gelesen hat.

Status-Uebersicht:
- Test 1, 2, 3: **rot** auf aktuellem Stub (Funktion gibt None zurueck).
- Test 4, 5, 6: **green guards** — praefen, dass die Funktion NICHT in
  Faellen eingreift, fuer die sie nicht zustaendig ist, und dass das
  bestehende R1..R4-Verhalten unberuehrt bleibt.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.services.package_resolver import (
    resolve_package,
    resolve_pieces_per_length,
)


# --------------------------------------------------------------------------- #
# Minimaler Entry-Shape, der die strukturellen Felder traegt.
# Bewusst kein SQLAlchemy-Model, damit die Tests keinen DB-Context brauchen.
# --------------------------------------------------------------------------- #
@dataclass
class _E:
    """Lean-Entry fuer Resolver-Tests — trägt nur die Felder, die die
    Funktion liest. In der Produktion wird der echte
    `SupplierPriceEntry` gereicht; duck-typing reicht."""

    price_net: Decimal
    unit: str
    pieces_per_package: int | None = None
    package_size: Decimal | float | None = None
    package_unit: str | None = None


# --------------------------------------------------------------------------- #
# Test 1 — Happy Path CW-Profil (realer Kemmler-Eintrag)
# --------------------------------------------------------------------------- #
def test_cw_profil_bundle_zu_laufmeter():
    """Entpacke den echten Kemmler-CW-100-Eintrag.

    167,40 EUR / (8 Stangen * 2,60 m) = 8,048... EUR/m.

    Erwarteter Status heute: ROT (Stub gibt None).
    Erwarteter Status nach Phase-3-Fix: GRUEN.
    """
    entry = _E(
        price_net=Decimal("167.40"),
        unit="€/m",
        pieces_per_package=8,
        package_size=Decimal("2.6"),
        package_unit="m",
    )
    result = resolve_pieces_per_length(entry)
    assert result is not None, (
        "Stub gibt None; nach Fix erwarten wir ('m', ~8.05)."
    )
    eff_unit, ppe = result
    assert eff_unit == "m"
    # 8.048 ... mit Float-Toleranz
    assert Decimal("8.04") <= Decimal(ppe) <= Decimal("8.06"), (
        f"Erwartet 8,04 ≤ ppe ≤ 8,06 EUR/m, bekommen {ppe}"
    )


# --------------------------------------------------------------------------- #
# Test 2 — Happy Path Kantenprofil (10 Stangen * 2,50 m)
# --------------------------------------------------------------------------- #
def test_kantenprofil_bundle_zu_laufmeter():
    """Entpacke ein Kantenprofil-Bundle mit 10 Stangen a 2,5 m.

    50,00 EUR / (10 * 2,50 m) = 2,00 EUR/m.

    Erwarteter Status heute: ROT (Stub gibt None).
    Erwarteter Status nach Phase-3-Fix: GRUEN.
    """
    entry = _E(
        price_net=Decimal("50.00"),
        unit="€/m",
        pieces_per_package=10,
        package_size=Decimal("2.5"),
        package_unit="m",
    )
    result = resolve_pieces_per_length(entry)
    assert result is not None, "Stub gibt None; nach Fix erwarten wir ('m', 2.0)."
    eff_unit, ppe = result
    assert eff_unit == "m"
    assert Decimal("1.99") <= Decimal(ppe) <= Decimal("2.01"), (
        f"Erwartet ~2,00 EUR/m, bekommen {ppe}"
    )


# --------------------------------------------------------------------------- #
# Test 3 — package_unit in Millimeter (automatische Umrechnung auf m)
# --------------------------------------------------------------------------- #
def test_package_size_in_mm_wird_auf_m_umgerechnet():
    """Parser liefert die Bundel-Laenge in ``mm`` statt ``m``.

    Eingaben: pieces=8, package_size=2600 (mm), package_unit="mm".
    Erwartung: wie Test 1 — 167,40 / (8 * 2,6 m) = 8,05 EUR/m.

    Erwarteter Status heute: ROT (Stub gibt None).
    Erwarteter Status nach Phase-3-Fix: GRUEN.
    """
    entry = _E(
        price_net=Decimal("167.40"),
        unit="€/m",
        pieces_per_package=8,
        package_size=Decimal("2600"),
        package_unit="mm",
    )
    result = resolve_pieces_per_length(entry)
    assert result is not None, "Stub gibt None; nach Fix erwarten wir ('m', ~8.05)."
    eff_unit, ppe = result
    assert eff_unit == "m"
    assert Decimal("8.04") <= Decimal(ppe) <= Decimal("8.06"), (
        f"mm->m Normierung fehlgeschlagen: bekommen {ppe}"
    )


# --------------------------------------------------------------------------- #
# Test 4 — Guard: Fehlende strukturelle Felder
# --------------------------------------------------------------------------- #
def test_fehlende_pieces_per_package_liefert_none():
    """Guard-Test: Ohne `pieces_per_package` kann diese Funktion nichts
    entpacken.

    Aktueller Status: GRUEN (Stub gibt None, der Vertrag definiert None
    als Signal „nicht zustaendig").

    Erwarteter Status nach Phase-3-Fix: GRUEN. Die Fix-Implementierung
    muss bei fehlenden Feldern weiterhin None zurueckgeben, damit
    `backfill_effective_units` den Entry unveraendert durchreicht oder
    an andere Resolver delegiert.

    Wenn dieser Test nach einem Fix ROT wird, greift die Funktion in
    Faelle, fuer die ihr die Daten fehlen — dann wuerde mit None- oder
    0-Feldern gerechnet und die DB mit Schrott gefuellt.
    """
    entry = _E(
        price_net=Decimal("167.40"),
        unit="€/m",
        pieces_per_package=None,
        package_size=Decimal("2.6"),
        package_unit="m",
    )
    assert resolve_pieces_per_length(entry) is None


# --------------------------------------------------------------------------- #
# Test 5 — Guard: Falsche Unit (kein Laengen-Typ)
# --------------------------------------------------------------------------- #
def test_unit_stk_liefert_none():
    """Guard-Test: Stueck-Einheiten sind Sache der R1/R4-Muster in
    `resolve_package`, nicht dieser Funktion.

    Aktueller Status: GRUEN (Stub gibt None).

    Erwarteter Status nach Phase-3-Fix: GRUEN. Die Fix-Implementierung
    muss den Laengen-Unit-Filter (m/lfm/lfdm) streng halten. Stk./Ktn./
    Pak. etc. gehoeren nicht hierher.

    Wenn dieser Test nach einem Fix ROT wird, ist die Unit-Gate-Logik
    zu locker — die Funktion wuerde Entries entpacken, die bereits von
    der bestehenden R1 entpackt werden (Doppel-Entpackung-Risiko).
    """
    entry = _E(
        price_net=Decimal("12.00"),
        unit="€/Stk",
        pieces_per_package=100,
        package_size=Decimal("2.6"),
        package_unit="m",
    )
    assert resolve_pieces_per_length(entry) is None


# --------------------------------------------------------------------------- #
# Test 6 — Regression-Schutz: bestehende R1..R4 bleiben unberuehrt
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "unit,name,price,expected_unit",
    [
        # R1: Stk./Ktn.
        ("€/Ktn.", "KV60 Kreuzverbinder ... 100 Stk/Ktn.", 12.0, "Stk."),
        # R2: m/Rolle
        ("€/Rolle", "Stuckband 30mm x 30 m 30 m/Rolle", 15.0, "m"),
        # R3: m²/Pak.
        ("€/Pak.", "Trennwandpl. Sonorock 7,5 m²/Pak.", 22.50, "m²"),
    ],
)
def test_resolve_package_R1_R4_bleiben_gruen(unit, name, price, expected_unit):
    """Regression-Schutz: die alten Muster R1..R4 in `resolve_package`
    muessen unabhaengig vom neuen `resolve_pieces_per_length`-Pfad
    weiter korrekt funktionieren.

    Aktueller Status: GRUEN.
    Erwarteter Status nach Phase-3-Fix: GRUEN.

    Wenn dieser Test nach einem Fix ROT wird, hat die Phase-3-Implem
    versehentlich an `resolve_package` geruettelt — das darf nicht
    passieren; R6 lebt NEBEN den alten Mustern, nicht IN ihnen.
    """
    result_unit, _result_price = resolve_package(unit, name, price)
    assert result_unit == expected_unit
