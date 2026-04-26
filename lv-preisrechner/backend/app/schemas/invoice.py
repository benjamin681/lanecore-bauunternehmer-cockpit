"""Pydantic-Schemas fuer Invoice + Dunning + Finance (B+4.13)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.invoice import InvoiceStatus, InvoiceType


class InvoiceStatusChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    old_status: str | None
    new_status: str
    changed_at: datetime
    changed_by: str | None
    reason: str | None


class DunningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    invoice_id: str
    dunning_level: int
    dunning_date: date
    due_date: date
    mahngebuehr_betrag: float
    mahnzinsen_betrag: float
    status: str
    internal_notes: str | None
    created_at: datetime
    updated_at: datetime


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    lv_id: str
    source_offer_id: str
    source_aufmass_id: str | None
    invoice_number: str
    invoice_type: str
    status: str
    invoice_date: date
    sent_date: date | None
    due_date: date | None
    paid_date: date | None
    paid_amount: float
    betrag_netto: float
    betrag_ust: float
    betrag_brutto: float
    position_count: int
    internal_notes: str | None
    created_at: datetime
    updated_at: datetime


class InvoiceDetail(InvoiceOut):
    status_history: list[InvoiceStatusChangeOut] = Field(default_factory=list)
    dunnings: list[DunningOut] = Field(default_factory=list)


class InvoiceCreate(BaseModel):
    """POST /offers/{offer_id}/invoice."""

    model_config = ConfigDict(extra="forbid")

    invoice_type: InvoiceType = InvoiceType.SCHLUSSRECHNUNG
    internal_notes: str | None = Field(default=None, max_length=2000)


class InvoiceStatusUpdate(BaseModel):
    """PATCH /invoices/{id}/status."""

    model_config = ConfigDict(extra="forbid")

    status: InvoiceStatus
    reason: str | None = Field(default=None, max_length=2000)
    on_date: date | None = None


class PaymentCreate(BaseModel):
    """POST /invoices/{id}/payments."""

    model_config = ConfigDict(extra="forbid")

    amount: float = Field(..., gt=0)
    payment_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


class DunningCreate(BaseModel):
    """POST /invoices/{id}/dunnings."""

    model_config = ConfigDict(extra="forbid")

    internal_notes: str | None = Field(default=None, max_length=2000)


class FinanceOverview(BaseModel):
    offene_rechnungen_count: int
    offene_summe_brutto: float
    ueberfaellige_count: int
    ueberfaellige_summe_brutto: float
    gezahlte_summe_jahr_aktuell: float
    year: int


class OverdueInvoiceRow(BaseModel):
    id: str
    invoice_number: str
    betrag_brutto: float
    paid_amount: float
    open_amount: float
    due_date: str | None
    days_overdue: int | None
    highest_dunning_level: int
    next_dunning_due: str | None
    lv_id: str


class EmailDraftOut(BaseModel):
    """POST /invoices/{id}/email — voraus gefuellter Mailto-Link."""

    mailto: str
    subject: str
    body: str
    to: str | None
