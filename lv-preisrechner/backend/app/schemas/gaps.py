"""Schemas fuer den Katalog-Luecken-Report (B+4.3.0c).

Siehe ``docs/b430c_baseline.md`` fuer Design-Entscheidungen und
Response-Beispiele. Die Felder sind bewusst additiv zum B+4.2-
Materialien-JSON-Schema — es werden keine zusaetzlichen Daten im
Model persistiert.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class GapSeverity(str, Enum):
    """Prioritaets-Enum fuer Katalog-Luecken.

    Die Reihenfolge `missing > low_confidence > estimated` wird beim
    Sortieren ueber ``severity_rank`` realisiert. Die UI kann darauf
    vertrauen und nach severity filtern / sortieren.
    """

    missing = "missing"
    low_confidence = "low_confidence"
    estimated = "estimated"

    @classmethod
    def rank(cls, sev: "GapSeverity") -> int:
        return {
            cls.missing: 0,
            cls.low_confidence: 1,
            cls.estimated: 2,
        }[sev]


class CatalogGapEntry(BaseModel):
    position_id: str
    position_oz: str
    position_name: str
    material_name: str
    material_dna: str
    required_amount: float
    unit: str
    severity: GapSeverity
    price_source: str
    match_confidence: float | None
    source_description: str
    needs_review: bool


class LVGapsReport(BaseModel):
    lv_id: str
    total_positions: int
    total_materials: int
    gaps_count: int
    missing_count: int
    estimated_count: int
    low_confidence_count: int
    gaps: list[CatalogGapEntry]
