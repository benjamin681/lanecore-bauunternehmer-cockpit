"""Gebinde-Dekonstruktion fuer SupplierPriceEntries (B+4.2.7 Scope A).

Problem: Der Kemmler-Katalog fuehrt Kleinteile typischerweise als
Karton-Preise: `unit="€/Ktn."`, Produktname enthaelt `"100 Stk/Ktn."`.
Das Lookup fragt aber nach Stueckpreisen (`unit="Stk."`). Der
Unit-Filter wuerde diese Kandidaten aussortieren, obwohl aus dem
Produktnamen klar hervorgeht, wie sich der Karton in Einzelteile
aufloest.

Loesung: `resolve_package(unit, product_name, price)` liest Muster wie
"100 Stk/Ktn." und gibt (effective_unit, price_per_effective_unit)
zurueck. Ohne erkennbares Muster bleibt alles unveraendert.

Muster, die erkannt werden:
- "100 Stk/Ktn.", "100 Stück/Ktn.", "100 St./Ktn."
- "50 St./Pak.", "1000 Stk./Paket"
- "60 St./Bd.", "25 Stk./Bund"
- "50 m/Rolle", "30 m/Rol."
- "7,5 m²/Pak.", "5,625 m²/Karton"
- "à 50 Stk.", "Pak. = 100 Stk."
- Komma- und Punktdezimalen
- Umlaute (Stück) und deren ASCII-Variante (Stueck)

Scope-Grenze: Dieses Modul aendert KEINE Daten im SupplierPriceEntry
selbst — es ist eine pure Funktion. Der Post-Processor
`backfill_effective_units` ueberschreibt `effective_unit` +
`price_per_effective_unit` auf einer Entry-Liste (in Memory oder in
einer Session); die entsprechende DB-Transaktion muss der Caller
commiten.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable


# ---------------------------------------------------------------------------
# Kanonisierung der Ziel-Einheit (nach Entpacken)
# ---------------------------------------------------------------------------
_PIECE_SYNONYMS = ("stk.", "stk", "st.", "st", "stück", "stueck")
_M_SYNONYMS = ("m", "lfm", "lfdm")
_M2_SYNONYMS = ("m²", "m2", "qm")
_GEBINDE_KTN = ("ktn.", "ktn", "karton")
_GEBINDE_PAK = ("pak.", "pak", "paket", "packung")
_GEBINDE_BD = ("bd.", "bd", "bund")
_GEBINDE_ROL = ("rolle", "rol.", "rol", "rollen")

_GEBINDE_ALL = (*_GEBINDE_KTN, *_GEBINDE_PAK, *_GEBINDE_BD, *_GEBINDE_ROL)


def _canon_unit(u: str | None) -> str:
    """Reduziert '€/Ktn.' / ' €/Stk. ' auf 'ktn.' / 'stk.'."""
    if not u:
        return ""
    s = u.strip().lower()
    # Currency-Prefix '€/', 'EUR/' entfernen
    s = re.sub(r"^(€|eur|\$|chf)\s*/\s*", "", s, flags=re.IGNORECASE)
    return s.strip()


def _is_gebinde(u: str) -> bool:
    return _canon_unit(u) in _GEBINDE_ALL


# ---------------------------------------------------------------------------
# Regex-Muster zur Entpackung. Reihenfolge relevant (spezifischer zuerst).
# Wir suchen `<menge> <einheit> / <gebinde>` oder `<gebinde> = <menge>`.
# ---------------------------------------------------------------------------

# Nummer (Dezimal mit Komma oder Punkt)
_NUM = r"(\d+(?:[.,]\d+)?)"

# Gebinde-Token (alle Varianten)
_G = r"(?:Ktn\.?|Karton|Pak\.?|Paket|Packung|Bd\.?|Bund|Rolle|Rol\.?|Rollen)"

# Zieleinheit: Stk/St/Stück/Meter/m²
_TGT_PIECES = r"(?:Stk\.?|St\.?|Stück|Stueck)"
_TGT_M = r"(?:m|lfm|lfdm)"
_TGT_M2 = r"(?:m²|m2|qm)"

# Hauptmuster: "<menge> <Ziel> / <Gebinde>"
_PAT_PIECES_PER_GEBINDE = re.compile(
    rf"{_NUM}\s*{_TGT_PIECES}\s*[/.]\s*{_G}\b",
    re.IGNORECASE,
)
_PAT_M_PER_GEBINDE = re.compile(
    rf"{_NUM}\s*{_TGT_M}\s*/\s*{_G}\b",
    re.IGNORECASE,
)
_PAT_M2_PER_GEBINDE = re.compile(
    rf"{_NUM}\s*{_TGT_M2}\s*/\s*{_G}\b",
    re.IGNORECASE,
)

# Alternativ-Form: "Pak = 100 Stk." / "à 50 Stk." / "Paket à 20"
_PAT_GEBINDE_EQ_PIECES = re.compile(
    rf"(?:{_G}\s*(?:=|a|à)|à|a|=)\s*{_NUM}\s*{_TGT_PIECES}\b",
    re.IGNORECASE,
)

# Kanonisierung der Zieleinheit aus dem Regex-Treffer
def _canon_target(raw: str, kind: str) -> str:
    r = raw.strip().lower().rstrip(".")
    if kind == "pieces":
        if r.startswith("stü") or r.startswith("stue"):
            return "Stk."
        return "Stk."
    if kind == "m":
        return "m"
    if kind == "m2":
        return "m²"
    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def resolve_package(
    unit: str | None,
    product_name: str | None,
    price: Decimal | float | int | str,
) -> tuple[str, Decimal]:
    """Leitet (effective_unit, price_per_effective_unit) ab.

    Wenn `unit` ein Gebinde ist und im Produktnamen eine passende
    Entpackungs-Angabe steht, wird die Einzelpreis-Einheit plus
    Einzelpreis zurueckgegeben. Andernfalls: (unit, price) unveraendert.

    Beispiele:
      >>> resolve_package("€/Ktn.", "KV60 Kreuzverbinder ... 100 Stk/Ktn.", 12.0)
      ('Stk.', Decimal('0.1200'))
      >>> resolve_package("€/Rolle", "Stuckband 30mm x 30 m 30 m/Rolle", 15.0)
      ('m', Decimal('0.5000'))
      >>> resolve_package("m²", "Knauf DIAMANT 12,5 mm", 3.50)
      ('m²', Decimal('3.5'))
    """
    # Preis in Decimal
    p = Decimal(str(price)) if not isinstance(price, Decimal) else price

    if not unit or not product_name:
        return (unit or "", p)

    # Nur entpacken, wenn die Einheit tatsaechlich ein Gebinde ist.
    if not _is_gebinde(unit):
        return (unit, p)

    # Muster 1: "<menge> Stk / Gebinde"  (haeufigster Fall)
    m = _PAT_PIECES_PER_GEBINDE.search(product_name)
    if m:
        qty = _parse_decimal(m.group(1))
        if qty > 0:
            return ("Stk.", (p / qty).quantize(Decimal("0.0001")))

    # Muster 2: "<menge> m / Gebinde"
    m = _PAT_M_PER_GEBINDE.search(product_name)
    if m:
        qty = _parse_decimal(m.group(1))
        if qty > 0:
            return ("m", (p / qty).quantize(Decimal("0.0001")))

    # Muster 3: "<menge> m² / Gebinde"
    m = _PAT_M2_PER_GEBINDE.search(product_name)
    if m:
        qty = _parse_decimal(m.group(1))
        if qty > 0:
            return ("m²", (p / qty).quantize(Decimal("0.0001")))

    # Muster 4: "Gebinde = <menge> Stk" / "à 50 Stk."
    m = _PAT_GEBINDE_EQ_PIECES.search(product_name)
    if m:
        qty = _parse_decimal(m.group(1))
        if qty > 0:
            return ("Stk.", (p / qty).quantize(Decimal("0.0001")))

    # Gebinde erkannt, aber kein Entpackungs-Muster im Namen → unveraendert.
    return (unit, p)


def _parse_decimal(s: str) -> Decimal:
    """'7,5' -> Decimal('7.5'); '100' -> Decimal('100'); leer -> 0."""
    if not s:
        return Decimal(0)
    return Decimal(s.replace(",", "."))


# ---------------------------------------------------------------------------
# Post-Processor fuer eine Entry-Liste
# ---------------------------------------------------------------------------
def backfill_effective_units(entries: Iterable) -> int:
    """Setzt `effective_unit` + `price_per_effective_unit` auf jedem Entry
    der uebergebenen Iterable anhand der `resolve_package`-Logik.

    Wird NUR angewandt, wenn der Entry aktuell `effective_unit == unit`
    und `price_per_effective_unit == price_net` (also offenbar ohne
    Paket-Auflösung geparst wurde).

    Gibt die Anzahl geaenderter Einträge zurück. Der Caller entscheidet
    ueber commit().
    """
    changed = 0
    for e in entries:
        unit = getattr(e, "unit", None)
        name = getattr(e, "product_name", None)
        price = getattr(e, "price_net", None)
        if unit is None or price is None:
            continue
        eff_unit, eff_price = resolve_package(unit, name, price)
        # Nur ueberschreiben, wenn sich tatsaechlich etwas aendert
        # und der Entry derzeit "neutral" steht.
        if eff_unit == unit and eff_price == Decimal(str(price)):
            continue
        # Safety-Check: nur ueberschreiben, wenn effective_unit bisher
        # dem unit entspricht (d. h. der Parser hat nichts eigenes
        # gesetzt). Verhindert, dass wir bewusste Parser-Entscheidungen
        # ueberfahren.
        current_eff = getattr(e, "effective_unit", None)
        if current_eff and current_eff != unit:
            continue
        e.effective_unit = eff_unit
        e.price_per_effective_unit = eff_price
        changed += 1
    return changed
