"""Offer + Status-Audit (B+4.11): Offer-Lifecycle als eigenstaendiges Modell.

Eine Offer ist ein konkretes Angebot, das aus einem LV-Snapshot entsteht.
Im Unterschied zum LV (Daten-Container) hat die Offer einen Lifecycle:
draft → sent → accepted/rejected/negotiating/expired.

Snapshot-Felder (betrag_netto, betrag_brutto, position_count) werden zum
Erstellungszeitpunkt eingefroren — spaetere Aenderungen am LV beeinflussen
versendete Offers nicht. Aenderungen vor Versand passieren ueber Re-Calc
auf dem LV + neue Offer.
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


class OfferStatus(str, Enum):
    """Lifecycle-Status einer Offer."""

    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEGOTIATING = "negotiating"
    EXPIRED = "expired"


class OfferPdfFormat(str, Enum):
    """PDF-Format-Auswahl beim Erstellen einer Offer."""

    EIGENES_LAYOUT = "eigenes_layout"
    ORIGINAL_LV_FILLED = "original_lv_filled"


class Offer(Base):
    """Angebot — Snapshot eines LVs zum Erstellungszeitpunkt."""

    __tablename__ = "lvp_offers"
    __table_args__ = (
        Index("ix_lvp_offers_tenant_id", "tenant_id"),
        Index("ix_lvp_offers_lv_id", "lv_id"),
        Index("ix_lvp_offers_status", "status"),
        Index("ix_lvp_offers_tenant_offer_number", "tenant_id", "offer_number"),
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
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_projects.id", ondelete="SET NULL"),
        nullable=True,
    )

    # A-yymmdd-NN, eindeutig pro Tenant
    offer_number: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OfferStatus.DRAFT.value,
        server_default=OfferStatus.DRAFT.value,
    )

    offer_date: Mapped[date] = mapped_column(Date, nullable=False, default=_today)
    sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    accepted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rejected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Snapshot zum Erstellungszeitpunkt — werden bei spaeteren LV-Aenderungen
    # NICHT mit-aktualisiert.
    betrag_netto: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    betrag_brutto: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    position_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    pdf_format: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=OfferPdfFormat.EIGENES_LAYOUT.value,
        server_default=OfferPdfFormat.EIGENES_LAYOUT.value,
    )

    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    status_changes: Mapped[list["OfferStatusChange"]] = relationship(
        back_populates="offer",
        cascade="all, delete-orphan",
        order_by="OfferStatusChange.changed_at.desc()",
    )


class OfferStatusChange(Base):
    """Audit-Trail-Eintrag fuer einen Status-Wechsel einer Offer."""

    __tablename__ = "lvp_offer_status_changes"
    __table_args__ = (
        Index("ix_lvp_offer_status_changes_offer_id", "offer_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_offers.id", ondelete="CASCADE"),
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

    offer: Mapped["Offer"] = relationship(back_populates="status_changes")
