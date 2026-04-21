"""Einheitliches Zwischenformat fuer Preis-Ergebnisse in der Kalkulation.

Zweck: Legacy-DNA-Matcher und neuer price_lookup.lookup_price liefern
unterschiedliche Datentypen. Damit `_kalkuliere_position` beide Pfade
gleich behandeln kann, mappen wir beide auf `PriceResolution`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from app.services.dna_matcher import MatchResult
from app.services.price_lookup import PriceLookupResult


PriceSource = Literal[
    "override",
    "supplier_price",
    "legacy_price",
    "estimated",
    "not_found",
    "legacy",  # Sonderfall: alter Pfad ohne neue Klassifikation
]


@dataclass
class PriceResolution:
    """Preis-Ergebnis fuer EIN Material innerhalb einer Position.

    Wird sowohl vom Legacy-Pfad (Flag=False) als auch vom neuen
    price_lookup-Pfad (Flag=True) erzeugt. Die Kalkulation nutzt dies
    agnostisch zum zugrundeliegenden Lookup.
    """

    price: Decimal | None
    unit: str
    source: str
    source_description: str
    confidence: float
    needs_review: bool
    manufacturer: str | None = None
    product_name: str | None = None
    applied_discount_percent: Decimal | None = None
    supplier_name: str | None = None
    details: dict = field(default_factory=dict)


def from_legacy_match(m: MatchResult) -> PriceResolution:
    """Wrapper fuer den alten DNA-Matcher.

    Legacy liefert nur MatchResult; wir bauen eine Resolution mit
    source="legacy" (bewusst NICHT "legacy_price", damit die Herkunft
    vom alten DNA-Matcher klar bleibt — "legacy_price" ist die Stufe
    3 des neuen Services, die man aus dem neuen Pfad erreicht).
    """
    if m.price_entry is None:
        return PriceResolution(
            price=None,
            unit="",
            source="not_found",
            source_description=m.begruendung,
            confidence=m.konfidenz,
            needs_review=True,
            details={"legacy": True},
        )
    entry = m.price_entry
    return PriceResolution(
        price=Decimal(str(m.preis_pro_basis)),
        unit=m.basis_einheit,
        source="legacy",
        source_description=m.begruendung,
        confidence=m.konfidenz,
        needs_review=m.konfidenz < 0.85,
        manufacturer=entry.hersteller or None,
        product_name=entry.produktname or None,
        details={"legacy": True, "dna": entry.dna},
    )


def from_lookup_result(r: PriceLookupResult) -> PriceResolution:
    """Wrapper fuer den neuen price_lookup.lookup_price.

    Wichtig (siehe B+4.2-Praezisierung Nr. 1):
    - `manufacturer` stammt aus dem Entry (nicht supplier_name) und
      dient spaeter als `angebotenes_fabrikat` der Position.
    - `supplier_name` landet nur in source_description / details.
    Das manufacturer/product_name-Feld wird vom Caller aus dem
    zugehoerigen SupplierPriceEntry nachgereicht (via resolve_material).
    """
    return PriceResolution(
        price=r.price,
        unit=r.unit,
        source=r.price_source,
        source_description=r.source_description,
        confidence=r.match_confidence,
        needs_review=r.needs_review,
        applied_discount_percent=r.applied_discount_percent,
        supplier_name=r.supplier_name,
        details={
            "lookup_details": r.lookup_details,
            "pricelist_id": r.pricelist_id,
            "entry_id": r.entry_id,
        },
    )


def summarize_sources(resolutions: list[PriceResolution]) -> str:
    """Verdichtet eine Liste zu '2x override, 1x supplier_price'."""
    if not resolutions:
        return ""
    counts: dict[str, int] = {}
    for r in resolutions:
        counts[r.source] = counts.get(r.source, 0) + 1
    # sortiere nach Count absteigend
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{c}\u00d7 {s}" for s, c in items)
