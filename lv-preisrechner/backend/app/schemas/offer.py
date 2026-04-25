"""Pydantic-Schemas fuer Offer-Lifecycle (B+4.11)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.offer import OfferPdfFormat, OfferStatus


class OfferStatusChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    old_status: str | None
    new_status: str
    changed_at: datetime
    changed_by: str | None
    reason: str | None


class OfferOut(BaseModel):
    """Offer ohne History (Liste)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    lv_id: str
    project_id: str | None
    offer_number: str
    status: str
    offer_date: date
    sent_date: date | None
    accepted_date: date | None
    rejected_date: date | None
    valid_until: date | None
    betrag_netto: float
    betrag_brutto: float
    position_count: int
    pdf_format: str
    internal_notes: str | None
    created_at: datetime
    updated_at: datetime


class OfferDetail(OfferOut):
    """Offer mit Status-History — fuer Detail-Endpoint."""

    status_history: list[OfferStatusChangeOut] = Field(default_factory=list)


class OfferCreate(BaseModel):
    """POST /lvs/{lv_id}/offers Body."""

    model_config = ConfigDict(extra="forbid")

    pdf_format: OfferPdfFormat = OfferPdfFormat.EIGENES_LAYOUT
    internal_notes: str | None = Field(default=None, max_length=2000)


class OfferStatusUpdate(BaseModel):
    """PATCH /offers/{offer_id}/status Body."""

    model_config = ConfigDict(extra="forbid")

    status: OfferStatus
    reason: str | None = Field(default=None, max_length=2000)
    on_date: date | None = None


class OfferLvSummary(BaseModel):
    """Aggregat-Info fuer LV-Liste: wieviele Offers, neueste Status."""

    model_config = ConfigDict(from_attributes=True)

    offer_count: int
    latest_status: str | None
    latest_offer_number: str | None
