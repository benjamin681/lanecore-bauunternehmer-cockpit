"""Invoice + Status-Audit + Dunning (B+4.13 Iteration 5).

Eine Invoice (Rechnung) entsteht aus einem accepted Offer (typischerweise
einem Final-Offer auf Aufmaß-Basis). Sie hat eine eigene Lifecycle:
draft → sent → paid / partially_paid / overdue / cancelled.

Aus einer overdue Invoice koennen ein bis drei Mahnungen (lvp_dunnings)
mit eskalierenden Fristen + Mahngebuehren erzeugt werden.

Steuerlich: invoice_number ist eine durchlaufende Sequenz pro Tenant
pro Jahr (R-yyyy-NN), die nicht doppelt vergeben werden darf.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _today() -> date:
    return datetime.now(UTC).date()


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class InvoiceType(str, Enum):
    SCHLUSSRECHNUNG = "schlussrechnung"
    ABSCHLAGSRECHNUNG = "abschlagsrechnung"


class DunningStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID_AFTER = "paid_after"


class Invoice(Base):
    """Rechnung — Snapshot eines accepted Offers."""

    __tablename__ = "lvp_invoices"
    __table_args__ = (
        Index("ix_lvp_invoices_tenant_id", "tenant_id"),
        Index("ix_lvp_invoices_lv_id", "lv_id"),
        Index("ix_lvp_invoices_status", "status"),
        Index("ix_lvp_invoices_due_date", "due_date"),
        Index(
            "ix_lvp_invoices_tenant_invoice_number",
            "tenant_id",
            "invoice_number",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    lv_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_lvs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_offer_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_offers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_aufmass_id: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_aufmasse.id", ondelete="SET NULL"),
        nullable=True,
    )

    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False)
    invoice_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=InvoiceType.SCHLUSSRECHNUNG.value,
        server_default=InvoiceType.SCHLUSSRECHNUNG.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InvoiceStatus.DRAFT.value,
        server_default=InvoiceStatus.DRAFT.value,
    )

    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, default=_today)
    sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    paid_amount: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0, server_default="0"
    )

    # Snapshot
    betrag_netto: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    betrag_ust: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    betrag_brutto: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    position_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    status_changes: Mapped[list["InvoiceStatusChange"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceStatusChange.changed_at.desc()",
    )
    dunnings: Mapped[list["Dunning"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="Dunning.dunning_level",
    )


class InvoiceStatusChange(Base):
    """Audit-Trail-Eintrag pro Status-Wechsel + record_payment."""

    __tablename__ = "lvp_invoice_status_changes"
    __table_args__ = (
        Index("ix_lvp_invoice_status_changes_invoice_id", "invoice_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    invoice_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    changed_by: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="status_changes")


class Dunning(Base):
    """Mahnung — eskalierende Stufe 1/2/3."""

    __tablename__ = "lvp_dunnings"
    __table_args__ = (
        Index("ix_lvp_dunnings_tenant_id", "tenant_id"),
        Index("ix_lvp_dunnings_invoice_id", "invoice_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    invoice_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    dunning_level: Mapped[int] = mapped_column(Integer, nullable=False)
    dunning_date: Mapped[date] = mapped_column(Date, nullable=False, default=_today)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    mahngebuehr_betrag: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0, server_default="0"
    )
    mahnzinsen_betrag: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0, server_default="0"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DunningStatus.DRAFT.value,
        server_default=DunningStatus.DRAFT.value,
    )
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="dunnings")
