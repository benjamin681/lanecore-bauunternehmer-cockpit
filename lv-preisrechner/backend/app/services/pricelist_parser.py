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
# Placeholder fuer Haupt-Parser-Klasse
# Die eigentliche Implementation kommt in den folgenden Commits:
# - Commit 2: Unit-Normalisierung (_normalize_unit)
# - Commit 3: Claude Vision Integration (PricelistParser.parse)
# ---------------------------------------------------------------------------
