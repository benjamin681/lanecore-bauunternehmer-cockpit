"""B+4.3.0b — Schemas fuer den Candidates-Endpoint.

GET /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates liefert fuer
jede Material-Zeile einer Position eine Liste von Preis-Kandidaten
inklusive eines virtuellen Schaetzungs-Eintrags. Die UI (B+4.3.1)
nutzt das Response zur Darstellung des Near-Miss-Drawers.

Design-Entscheidungen siehe docs/b430b_baseline.md.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CandidateOut(BaseModel):
    """Ein einzelner Preis-Kandidat."""

    pricelist_name: str
    candidate_name: str
    match_confidence: float = Field(ge=0.0, le=1.0)
    stage: str  # 'supplier_price' | 'fuzzy' | 'estimated'
    price_net: float
    unit: str
    match_reason: str

    model_config = ConfigDict(from_attributes=True)


class MaterialWithCandidates(BaseModel):
    """Ein Material einer Position mit seiner Kandidaten-Liste."""

    material_name: str
    required_amount: float
    unit: str
    candidates: list[CandidateOut]


class PositionCandidatesOut(BaseModel):
    """Response des Candidates-Endpoints."""

    position_id: str
    position_name: str
    materials: list[MaterialWithCandidates]
