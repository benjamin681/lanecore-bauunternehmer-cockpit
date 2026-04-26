"""Aufmaß + Aufmaß-Positionen (B+4.12 Iteration 4).

Ein Aufmaß ist die Erfassung der tatsaechlich gebauten Mengen nach
Auftragserteilung. Es entsteht aus einem ACCEPTED Offer und enthaelt
fuer jede LV-Position einen Snapshot (lv_menge, ep, einheit, kurztext)
sowie die editierbare gemessene_menge.

Status-Lifecycle:
  in_progress -> finalized   (gp_aufmass eingefroren, keine Edits mehr)
  in_progress -> cancelled   (Aufmaß verworfen)

Aus einem finalized Aufmaß kann ein neuer Offer mit pdf_format
"aufmass_basiert" erstellt werden, der die gemessenen Mengen verwendet.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
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


class AufmassStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"


class Aufmass(Base):
    """Erfassung der tatsaechlich gebauten Mengen."""

    __tablename__ = "lvp_aufmasse"
    __table_args__ = (
        Index("ix_lvp_aufmasse_tenant_id", "tenant_id"),
        Index("ix_lvp_aufmasse_lv_id", "lv_id"),
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

    aufmass_number: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AufmassStatus.IN_PROGRESS.value,
        server_default=AufmassStatus.IN_PROGRESS.value,
    )

    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalized_by: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    positions: Mapped[list["AufmassPosition"]] = relationship(
        back_populates="aufmass",
        cascade="all, delete-orphan",
        order_by="AufmassPosition.created_at",
    )


class AufmassPosition(Base):
    """Eine Position im Aufmaß: Snapshot von LV-Position + gemessene Menge."""

    __tablename__ = "lvp_aufmass_positions"
    __table_args__ = (
        Index("ix_lvp_aufmass_positions_aufmass_id", "aufmass_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    aufmass_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_aufmasse.id", ondelete="CASCADE"),
        nullable=False,
    )
    lv_position_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_positions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Snapshots beim Erstellen
    oz: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    kurztext: Mapped[str] = mapped_column(Text, nullable=False, default="")
    einheit: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    lv_menge: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    ep: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    # Editierbar
    gemessene_menge: Mapped[float] = mapped_column(
        Numeric(14, 3), nullable=False, default=0
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Berechnet — werden bei jedem Mengen-Edit + beim Erstellen aktualisiert
    gp_lv_snapshot: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    gp_aufmass: Mapped[float] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    aufmass: Mapped["Aufmass"] = relationship(back_populates="positions")
