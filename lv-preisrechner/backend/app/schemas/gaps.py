"""Schemas fuer den Katalog-Luecken-Report (B+4.3.0c).

Siehe ``docs/b430c_baseline.md`` fuer Design-Entscheidungen und
Response-Beispiele. Die Felder sind bewusst additiv zum B+4.2-
Materialien-JSON-Schema — es werden keine zusaetzlichen Daten im
Model persistiert.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class UniqueMissingMaterial(BaseModel):
    """Dedupliziertes Gap pro material_dna mit Liste betroffener Positionen.

    Kern-Datenstruktur fuer das UI: ein Material, alle betroffenen OZs
    auf einen Blick, plus geschaetzter Preis aus einem eventuell
    vorhandenen estimated-Fallback aus derselben Preisliste.
    """

    material_dna: str
    material_name: str
    unit: str
    severity: GapSeverity
    betroffene_positionen: list[str] = Field(
        default_factory=list,
        description="Liste von OZ-Kennungen der betroffenen Positionen.",
    )
    total_required_amount: float = 0.0
    geschaetzter_preis: float | None = None
    geschaetzter_preis_einheit: str | None = None
    resolution: dict[str, Any] | None = Field(
        default=None,
        description="Aktive Resolution (falls vorhanden): resolution_type + resolved_value.",
    )


class LVGapsReport(BaseModel):
    lv_id: str
    total_positions: int
    total_materials: int
    gaps_count: int
    missing_count: int
    estimated_count: int
    low_confidence_count: int
    gaps: list[CatalogGapEntry]
    unique_missing_materials: list[UniqueMissingMaterial] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Resolution (B+4.6)
# --------------------------------------------------------------------------- #
class GapResolutionTypeSchema(str, Enum):
    MANUAL_PRICE = "manual_price"
    SKIP = "skip"


class GapResolveRequest(BaseModel):
    """POST /lvs/{lv_id}/gaps/resolve.

    corrected_value ist typ-abhaengig — Validierung im Service-Layer:
    - MANUAL_PRICE: {price_net: float>0, unit: str}
    - SKIP: {} (leer; Marker-Eintrag reicht).
    """

    model_config = ConfigDict(extra="forbid")

    material_dna: str = Field(..., min_length=1, max_length=500)
    resolution_type: GapResolutionTypeSchema
    value: dict[str, Any] = Field(default_factory=dict)


class GapResolutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lv_id: str
    tenant_id: str
    material_dna: str
    resolution_type: str
    resolved_value: dict[str, Any] | None
    tenant_price_override_id: str | None
    created_by_user_id: str
    created_at: datetime


class GapResolveResponse(BaseModel):
    resolution: GapResolutionOut
    recalculated: bool = Field(
        default=False,
        description="True wenn das LV nach der Aktion neu kalkuliert wurde.",
    )
