"""B+4.2.7 Teil 2 — Integration-Tests fuer backfill_effective_units
mit Pieces-per-Length-Fallback.

Pfad A (bestehend, R1..R4) wurde bereits durch
`tests/test_package_resolver.py::test_backfill_*` abgedeckt. Hier
testen wir den neuen Fallback-Pfad B.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.services.package_resolver import backfill_effective_units


@dataclass
class _FakeEntry:
    """Duck-typed Stand-in fuer SupplierPriceEntry in Resolver-Tests.

    Die Felder entsprechen 1:1 denen im echten Model. Der Resolver
    arbeitet via getattr(), braucht also keine Session.
    """

    price_net: Decimal
    unit: str
    product_name: str = ""
    pieces_per_package: int | None = None
    package_size: Decimal | None = None
    package_unit: str | None = None
    effective_unit: str | None = None
    price_per_effective_unit: Decimal | None = None


def test_backfill_entpackt_cw_profil_bundle_preis():
    """CW-Profil mit price_net == Bundle-Gesamtpreis bekommt PPE = 8.05."""
    entry = _FakeEntry(
        price_net=Decimal("167.40"),
        unit="€/m",
        product_name="CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.",
        pieces_per_package=8,
        package_size=Decimal("2.6"),
        package_unit="m",
        effective_unit="lfm",  # Parser setzt das schon auf Laenge
        price_per_effective_unit=Decimal("167.40"),  # noch == price_net
    )
    changed = backfill_effective_units([entry])
    assert changed == 1
    assert entry.effective_unit == "m"
    assert Decimal("8.04") <= entry.price_per_effective_unit <= Decimal("8.06")


def test_backfill_ueberspringt_wenn_ppe_bereits_korrekt_gesetzt():
    """Wenn price_per_effective_unit != price_net, ist bereits eine Auf-
    loesung erfolgt — Backfill ruehrt das nicht an (Safety-Check)."""
    entry = _FakeEntry(
        price_net=Decimal("167.40"),
        unit="€/m",
        product_name="CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.",
        pieces_per_package=8,
        package_size=Decimal("2.6"),
        package_unit="m",
        effective_unit="m",
        price_per_effective_unit=Decimal("5.00"),  # bereits etwas anderes
    )
    changed = backfill_effective_units([entry])
    assert changed == 0
    assert entry.price_per_effective_unit == Decimal("5.00")  # unveraendert


def test_backfill_uebernimmt_mm_zu_m_normalisierung():
    """Parser hat package_unit=mm geliefert — Backfill rechnet auf m."""
    entry = _FakeEntry(
        price_net=Decimal("100.00"),
        unit="€/lfm",
        product_name="Kantenprofil 3502 BL=2500 mm 20 St./Bd.",
        pieces_per_package=20,
        package_size=Decimal("2500"),
        package_unit="mm",
        effective_unit="lfm",
        price_per_effective_unit=Decimal("100.00"),
    )
    changed = backfill_effective_units([entry])
    assert changed == 1
    # 100 / (20 * 2.5) = 2.00
    assert Decimal("1.99") <= entry.price_per_effective_unit <= Decimal("2.01")
    assert entry.effective_unit == "m"


def test_backfill_pfad_a_hat_vorrang_vor_pfad_b():
    """Wenn R1 (Ktn.-Muster) greift, wird Pfad B nicht zusaetzlich
    angewandt. Der Entry bleibt beim R1-Ergebnis."""
    entry = _FakeEntry(
        price_net=Decimal("12.00"),
        unit="€/Ktn.",
        product_name="KV60 Kreuzverbinder 100 Stk/Ktn.",
        pieces_per_package=None,  # absichtlich: Pfad B waere nicht anwendbar
        package_size=None,
        package_unit=None,
        effective_unit="€/Ktn.",
        price_per_effective_unit=Decimal("12.00"),
    )
    changed = backfill_effective_units([entry])
    assert changed == 1
    assert entry.effective_unit == "Stk."
    # 12.00 / 100 = 0.12
    assert Decimal("0.11") <= entry.price_per_effective_unit <= Decimal("0.13")


def test_backfill_ignoriert_entry_ohne_bundle_felder():
    """Entry ohne pieces_per_package bleibt unveraendert."""
    entry = _FakeEntry(
        price_net=Decimal("3.30"),
        unit="€/m²",
        product_name="Gipskartonpl. 12,5 mm",
        effective_unit="m²",
        price_per_effective_unit=Decimal("3.30"),
    )
    changed = backfill_effective_units([entry])
    assert changed == 0
    assert entry.price_per_effective_unit == Decimal("3.30")
