"""Parser für Lieferanten-Preislisten (Sub-Block B+2).

Scope heute: Nur Kemmler-Format. Andere Lieferanten folgen bei Bedarf.

Architektur — Zwei-Phasen-Parsing:
1. pdfplumber (schnell, lokal): Layout-Info als Context für Phase 2
2. Claude Vision (präzise, API): Inhalts-Extraktion pro Batch

Der Parser wird via Background-Task aus pricelist_parse_worker.py aufgerufen.
Status-Übergänge: PENDING_PARSE -> PARSING -> PARSED / ERROR.

Die Einheiten-Intelligenz ist in diesem Modul isoliert (reines Python,
ohne Claude-API), damit sie unabhängig testbar ist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Typen
# ---------------------------------------------------------------------------
SupplierFormat = Literal["kemmler"]  # noqa: Y026 — erweitert sich spaeter


@dataclass
class ParseResult:
    """Ergebnis eines kompletten Parse-Laufs."""

    pricelist_id: str
    total_entries: int = 0
    parsed_entries: int = 0
    skipped_entries: int = 0
    avg_confidence: float = 0.0
    needs_review_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_entries == 0:
            return 0.0
        return self.parsed_entries / self.total_entries


@dataclass
class UnitInfo:
    """Normalisierte Einheiten-Information fuer einen Preis-Eintrag."""

    unit: str                               # Original-Einheit wie im Parser gelesen
    effective_unit: str                     # Normalisierte "Echt-Einheit" fuer Matching
    price_per_effective_unit: float         # Normalisierter Preis
    package_size: float | None = None       # z.B. 25.0 bei "25 kg/Sack"
    package_unit: str | None = None         # z.B. "kg" bei "25 kg/Sack"
    pieces_per_package: int | None = None   # z.B. 8 bei "8 St./Bd."
    confidence: float = 1.0                 # 0..1
    needs_review: bool = False
    note: str = ""                          # Freitext-Hinweis fuer Reviewer


# ---------------------------------------------------------------------------
# Format-Erkennung
# ---------------------------------------------------------------------------
_KEMMLER_FILENAME_HINTS = ("kemmler", "ausbau-", "a-liste", "a+-liste", "a_liste")


def _detect_format(
    file_path: Path | str,
    *,
    supplier_hint: str | None = None,
    first_page_text: str | None = None,
) -> SupplierFormat | None:
    """Erkennt das Preislisten-Format anhand von Dateiname + optionalem Text.

    Heute unterstuetzt: Kemmler.
    Return None wenn nicht sicher erkennbar -> Caller muss entscheiden
    ob abbrechen oder generischen Fallback-Parser nutzen.
    """
    fn = str(file_path).lower()
    hint = (supplier_hint or "").lower()

    # Expliziter supplier_hint hat Vorrang
    if "kemmler" in hint:
        return "kemmler"

    # Dateiname-basierte Hints
    if any(h in fn for h in _KEMMLER_FILENAME_HINTS):
        return "kemmler"

    # Text-basierte Erkennung (Header auf erster Seite)
    if first_page_text:
        text_lower = first_page_text.lower()
        if "kemmler" in text_lower:
            return "kemmler"

    return None


# ---------------------------------------------------------------------------
# Einheiten-Intelligenz
# ---------------------------------------------------------------------------
# Regex: "X kg/Sack", "25kg/sack", "12,5 l/Eimer" etc.
_PACKAGE_UNIT_RE = re.compile(
    r"(?P<size>\d+(?:[,\.]\d+)?)\s*"
    r"(?P<pkg_unit>kg|g|l|ml|m²|qm|m2|m|lfm|stk|st)\s*/\s*"
    r"(?P<pkg_kind>sack|eimer|beutel|flasche|kanister|rolle|dose|gebinde)",
    re.IGNORECASE,
)

# Regex: "8 St./Bd.", "10 Stk./Bund", "16 St/Bd" etc.
_PIECES_PER_BUNDLE_RE = re.compile(
    r"(?P<pieces>\d+)\s*(?:st|stk)\.?\s*/\s*(?:bd|bund|pak|paket)\.?",
    re.IGNORECASE,
)

# Regex: "BL=2600 mm", "BL 3000mm", "L = 3.00 m" (Bundellaenge)
_BUNDLE_LENGTH_RE = re.compile(
    r"\b(?:bl|l)\s*=?\s*(?P<len>\d+(?:[,\.]\d+)?)\s*(?P<unit>mm|cm|m)\b",
    re.IGNORECASE,
)

# Regex: Rollen-Groesse "1100 mm x 50 m/Ro", "1.1 x 50m"
_ROLL_SIZE_RE = re.compile(
    r"(?P<width>\d+(?:[,\.]\d+)?)\s*(?P<wu>mm|cm|m)\s*[x×]\s*"
    r"(?P<length>\d+(?:[,\.]\d+)?)\s*(?P<lu>mm|cm|m)",
    re.IGNORECASE,
)

# Regex: Plattenformat "2000x1250x12,5 mm"
_PLATE_SIZE_RE = re.compile(
    r"(?P<w>\d+)\s*[x×]\s*(?P<h>\d+)\s*(?:[x×]\s*\d+(?:[,\.]\d+)?)?\s*mm",
    re.IGNORECASE,
)


def _to_float(s: str) -> float:
    """'12,5' -> 12.5 ; '3.00' -> 3.0."""
    return float(s.replace(",", "."))


def _to_meters(value: float, unit: str) -> float:
    unit_l = unit.lower()
    if unit_l == "mm":
        return value / 1000.0
    if unit_l == "cm":
        return value / 100.0
    return value


def _normalize_unit(
    raw_unit: str,
    *,
    product_name: str = "",
    price: float = 0.0,
) -> UnitInfo:
    """Ermittelt effektive Einheit + normalisierten Preis aus roher Einheit.

    Fuenf Regeln (aus B+2-Spec):
      R1: "X kg/Sack" & Co.       -> package_size, effective_unit=pkg_unit
      R2: "N St./Bd." mit BL      -> UNKLAR, needs_review=True
      R3: "X l/Eimer"             -> analog R1
      R4: Plattenware €/m²        -> direkt
      R5: Rollen WxL              -> m² berechnen

    Fallback: effective_unit=raw_unit, needs_review=True, confidence<0.7.
    """
    raw = raw_unit.strip()
    raw_lower = raw.lower()
    combined = f"{product_name} {raw_unit}"

    # --- R4: Plattenware mit direktem €/m² (EINFACHER Pfad zuerst) -------
    if raw_lower in ("€/m²", "eur/m²", "€/qm", "eur/qm", "m²", "qm"):
        # Haeufiger Fall: Gipskartonplatte 2000x1250x12,5mm, 3.00 €/m² -> direkt
        return UnitInfo(
            unit=raw,
            effective_unit="m²",
            price_per_effective_unit=price,
            confidence=1.0,
        )
    if raw_lower in ("€/m", "eur/m", "€/lfm", "eur/lfm", "m", "lfm"):
        # Spezial-Check: laufende Meter bei Profilen mit "N St./Bd."
        bundle_match = _PIECES_PER_BUNDLE_RE.search(combined)
        length_match = _BUNDLE_LENGTH_RE.search(combined)
        if bundle_match and length_match:
            # R2: Bundpreis — unklar, markiere zum Review.
            return UnitInfo(
                unit=raw,
                effective_unit="lfm",
                price_per_effective_unit=price,
                pieces_per_package=int(bundle_match.group("pieces")),
                package_size=_to_meters(
                    _to_float(length_match.group("len")), length_match.group("unit")
                ),
                package_unit="m",
                confidence=0.55,
                needs_review=True,
                note=(
                    "Bundpreis vs. Einzelpreis unklar — "
                    "der €/m koennte sich auf eine Einzelstange oder den Bund beziehen."
                ),
            )
        # Sonst: klarer lfm-Preis
        return UnitInfo(
            unit=raw,
            effective_unit="lfm",
            price_per_effective_unit=price,
            confidence=0.95,
        )
    if raw_lower in ("€/stk", "eur/stk", "stk", "stk.", "€/st", "st."):
        return UnitInfo(
            unit=raw,
            effective_unit="Stk",
            price_per_effective_unit=price,
            confidence=1.0,
        )
    if raw_lower in ("€/kg", "eur/kg", "kg"):
        return UnitInfo(
            unit=raw,
            effective_unit="kg",
            price_per_effective_unit=price,
            confidence=1.0,
        )

    # --- R1 / R3: Gebinde-Einheit wie "25 kg/Sack" oder "12,5 l/Eimer" -----
    m = _PACKAGE_UNIT_RE.search(combined)
    if m:
        size = _to_float(m.group("size"))
        pkg_unit = m.group("pkg_unit").lower()
        pkg_kind = m.group("pkg_kind").lower()
        # Wenn der Preis pro Gebinde angegeben ist (z.B. "47,50 €/Eimer"),
        # rechnen wir auf pkg_unit runter.
        if (
            pkg_kind in raw_lower
            or raw_lower == f"€/{pkg_kind}"
            or raw_lower == f"eur/{pkg_kind}"
        ):
            if size > 0:
                return UnitInfo(
                    unit=raw,
                    effective_unit=pkg_unit,
                    price_per_effective_unit=round(price / size, 4),
                    package_size=size,
                    package_unit=pkg_unit,
                    confidence=0.95,
                )

    # --- R5: Rollen mit WxL-Angabe + €/m² (kein Direktmatch oben) ---
    if "rolle" in raw_lower or "/ro" in raw_lower or "/rolle" in raw_lower:
        roll_match = _ROLL_SIZE_RE.search(combined)
        if roll_match:
            w = _to_meters(_to_float(roll_match.group("width")), roll_match.group("wu"))
            l = _to_meters(_to_float(roll_match.group("length")), roll_match.group("lu"))
            area = w * l
            if area > 0:
                return UnitInfo(
                    unit=raw,
                    effective_unit="m²",
                    price_per_effective_unit=round(price / area, 4),
                    package_size=area,
                    package_unit="m²",
                    confidence=0.90,
                )

    # --- Fallback: unklar, Review noetig -----------------------------------
    return UnitInfo(
        unit=raw,
        effective_unit=raw or "unknown",
        price_per_effective_unit=price,
        confidence=0.3,
        needs_review=True,
        note=f"Einheit '{raw_unit}' nicht automatisch erkannt. Manuelle Pruefung noetig.",
    )


def _extract_price_per_effective_unit(
    raw_unit: str,
    price: float,
    *,
    product_name: str = "",
) -> float:
    """Convenience-Wrapper: nur den normalisierten Preis zurueck."""
    info = _normalize_unit(raw_unit, product_name=product_name, price=price)
    return info.price_per_effective_unit
