"""Pydantic-Schemas fuer Aufmaß-Lifecycle (B+4.12)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AufmassPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    aufmass_id: str
    lv_position_id: str
    oz: str
    kurztext: str
    einheit: str
    lv_menge: float
    ep: float
    gemessene_menge: float
    notes: str | None
    gp_lv_snapshot: float
    gp_aufmass: float
    created_at: datetime
    updated_at: datetime


class AufmassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    lv_id: str
    source_offer_id: str
    aufmass_number: str
    status: str
    finalized_at: datetime | None
    finalized_by: str | None
    internal_notes: str | None
    created_at: datetime
    updated_at: datetime


class AufmassDetail(AufmassOut):
    positions: list[AufmassPositionOut] = Field(default_factory=list)


class AufmassCreate(BaseModel):
    """POST /offers/{offer_id}/aufmass."""

    model_config = ConfigDict(extra="forbid")

    internal_notes: str | None = Field(default=None, max_length=2000)


class AufmassPositionUpdate(BaseModel):
    """PATCH /aufmasse/{id}/positions/{pos_id}."""

    model_config = ConfigDict(extra="forbid")

    gemessene_menge: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class AufmassGroupSummary(BaseModel):
    group: str
    lv_netto: float
    aufmass_netto: float
    diff_netto: float
    position_count: int


class AufmassSummary(BaseModel):
    lv_total_netto: float
    aufmass_total_netto: float
    diff_netto: float
    diff_brutto: float
    diff_pct: float | None
    position_count: int
    by_group: list[AufmassGroupSummary]
