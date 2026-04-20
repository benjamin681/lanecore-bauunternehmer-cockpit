"""Pricing-Modell: Lieferanten-Preislisten + Tenant-Overrides + Rabatt-Regeln.

Parallel-Architektur (siehe Entscheidung 2026-04-20, Option A):
- Diese 4 Tabellen sind ADDITIV zur bestehenden PriceList/PriceEntry-Struktur.
- Die bestehende Pricing-Infrastruktur (alte PriceList, alte PriceEntry) bleibt
  unverändert und voll funktional.
- Die Brücke zwischen alt und neu (Migration der Kalkulations-Pipeline auf das
  neue Modell) wird in späteren Phasen gebaut.

Warum parallel statt sofort ersetzen?
- Keine Regression am produktiven DNA-Matcher.
- Keine Änderungen an Kalkulation, Jobs, API /api/v1/price-lists.
- Rollback-Möglichkeit falls sich das neue Modell als suboptimal erweist.

Die `legacy_*_id` und `migrated_from_legacy` Felder dienen dem späteren
Migrations-Tracking.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Status-Enum (als Strings in der DB, Python-Seite typsicher)
# ---------------------------------------------------------------------------
class PricelistStatus(str, Enum):
    PENDING_PARSE = "PENDING_PARSE"
    PARSING = "PARSING"
    PARSED = "PARSED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Tabelle 1: SupplierPriceList
# ---------------------------------------------------------------------------
class SupplierPriceList(Base):
    __tablename__ = "lvp_supplier_pricelists"
    __table_args__ = (
        Index(
            "ix_lvp_supplier_pricelists_tenant_supplier",
            "tenant_id",
            "supplier_name",
        ),
        Index(
            "ix_lvp_supplier_pricelists_tenant_status",
            "tenant_id",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    list_name: Mapped[str] = mapped_column(String(200), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    source_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=PricelistStatus.PENDING_PARSE.value
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    entries_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entries_reviewed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    uploaded_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Migrations-Tracking (aktuell ungenutzt, Platzhalter fuer Phase 2):
    legacy_pricelist_id: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_price_lists.id"), nullable=True
    )
    migrated_from_legacy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    entries: Mapped[list["SupplierPriceEntry"]] = relationship(
        back_populates="pricelist",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Tabelle 2: SupplierPriceEntry
# ---------------------------------------------------------------------------
class SupplierPriceEntry(Base):
    __tablename__ = "lvp_supplier_price_entries"
    __table_args__ = (
        Index(
            "ix_lvp_supplier_price_entries_pricelist_article",
            "pricelist_id",
            "article_number",
        ),
        Index(
            "ix_lvp_supplier_price_entries_tenant_manufacturer",
            "tenant_id",
            "manufacturer",
        ),
        Index(
            "ix_lvp_supplier_price_entries_tenant_category",
            "tenant_id",
            "category",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    pricelist_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_supplier_pricelists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identifikation
    article_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Preis
    price_net: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # Einheiten-Intelligenz (Normalisierung fuer Matching)
    package_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pieces_per_package: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    price_per_effective_unit: Mapped[float] = mapped_column(Float, nullable=False)

    # Flexible Attribute (Abmessungen, Farbe, etc.)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Metadaten & Review-Workflow
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_row_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    correction_applied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Migrations-Tracking
    legacy_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_price_entries.id"), nullable=True
    )
    migrated_from_legacy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    pricelist: Mapped["SupplierPriceList"] = relationship(back_populates="entries")


# ---------------------------------------------------------------------------
# Tabelle 3: TenantPriceOverride
# ---------------------------------------------------------------------------
class TenantPriceOverride(Base):
    __tablename__ = "lvp_tenant_price_overrides"
    __table_args__ = (
        Index(
            "ix_lvp_tenant_price_overrides_tenant_article",
            "tenant_id",
            "article_number",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    article_number: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    override_price: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


# ---------------------------------------------------------------------------
# Tabelle 4: TenantDiscountRule
# ---------------------------------------------------------------------------
class TenantDiscountRule(Base):
    __tablename__ = "lvp_tenant_discount_rules"
    __table_args__ = (
        Index(
            "ix_lvp_tenant_discount_rules_tenant_supplier",
            "tenant_id",
            "supplier_name",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
