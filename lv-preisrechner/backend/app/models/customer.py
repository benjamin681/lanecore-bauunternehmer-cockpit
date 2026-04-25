"""Customer + Project (B+4.9): Vertriebs-Workflow-Foundation."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Customer(Base):
    """Stammdaten eines Auftraggebers eines Tenants.

    Ein Customer haelt N Projects. Loeschen eines Customers ist
    ON DELETE RESTRICT solange Projects daran haengen — der User
    muss Projects vorher zuordnen oder loeschen.
    """

    __tablename__ = "lvp_customers"
    __table_args__ = (
        Index("ix_lvp_customers_tenant_name", "tenant_id", "name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_country: Mapped[str] = mapped_column(
        String(2), nullable=False, default="DE", server_default="DE"
    )
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Project(Base):
    """Bauvorhaben — verknuepft Customer ↔ N LVs.

    Wird beim LV-Upload automatisch angelegt, wenn der Parser einen
    Projektnamen aus dem LV-Header extrahiert hat.
    """

    __tablename__ = "lvp_projects"
    __table_args__ = (
        Index("ix_lvp_projects_tenant_id", "tenant_id"),
        Index("ix_lvp_projects_customer_id", "customer_id"),
        Index("ix_lvp_projects_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    address_street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="projects")
