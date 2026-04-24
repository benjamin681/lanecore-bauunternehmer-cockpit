"""LV = ein hochgeladenes Leistungsverzeichnis."""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class LV(Base):
    __tablename__ = "lvp_lvs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id"), nullable=False, index=True
    )

    projekt_name: Mapped[str] = mapped_column(String(300), default="")
    auftraggeber: Mapped[str] = mapped_column(String(300), default="")

    original_dateiname: Mapped[str] = mapped_column(String(500), default="")
    original_pdf_pfad: Mapped[str] = mapped_column(String(500), default="")  # deprecated
    original_pdf_sha256: Mapped[str] = mapped_column(String(64), default="")
    ausgefuelltes_pdf_pfad: Mapped[str] = mapped_column(String(500), default="")  # deprecated
    # Persistente PDFs in DB (Render Free Tier hat ephemeres FS)
    original_pdf_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)
    ausgefuelltes_pdf_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)

    # "uploaded" | "extracting" | "review_needed" | "calculated" | "exported"
    status: Mapped[str] = mapped_column(String(30), default="uploaded")

    positionen_gesamt: Mapped[int] = mapped_column(default=0)
    positionen_gematcht: Mapped[int] = mapped_column(default=0)
    positionen_unsicher: Mapped[int] = mapped_column(default=0)

    # Angebotssumme OHNE Bedarfs- und Alternativpositionen — das ist die bindende Summe
    angebotssumme_netto: Mapped[float] = mapped_column(default=0.0)
    # Separat ausgewiesen zur Information:
    bedarfspositionen_summe: Mapped[float] = mapped_column(default=0.0)
    alternativpositionen_summe: Mapped[float] = mapped_column(default=0.0)
    # Gesamtsumme inklusive aller optionalen Positionen (zur Referenz)
    gesamtsumme_inklusive_optional: Mapped[float] = mapped_column(default=0.0)

    # Welche Preisliste wurde verwendet
    price_list_id: Mapped[str] = mapped_column(String, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    tenant: Mapped["Tenant"] = relationship(back_populates="lvs")  # type: ignore  # noqa: F821
    positions: Mapped[list["Position"]] = relationship(  # type: ignore  # noqa: F821
        back_populates="lv",
        cascade="all, delete-orphan",
        order_by="Position.reihenfolge",
    )


class GapResolutionType(str, Enum):
    """B+4.6: Arten, eine Katalog-Luecke im LV zu schliessen."""

    MANUAL_PRICE = "manual_price"
    SKIP = "skip"


class LVGapResolution(Base):
    """Audit-Trail fuer Nutzer-Aktionen auf Katalog-Luecken eines LV.

    Ergaenzt die on-the-fly berechnete :class:`app.services.catalog_gaps
    .compute_lv_gaps` um User-Entscheidungen. Der Gap-Report filtert
    Entries mit aktiven ``skip``-Resolutions aus, sodass bewusst
    akzeptierte Luecken nicht mehr als offener Handlungsbedarf gezeigt
    werden.

    ``manual_price``-Resolutions legen zusaetzlich einen
    :class:`TenantPriceOverride` an — die FK sichert die Referenz fuer
    Nachverfolgung und Loeschung.
    """

    __tablename__ = "lvp_lv_gap_resolutions"
    __table_args__ = (
        UniqueConstraint(
            "lv_id",
            "material_dna",
            "resolution_type",
            name="uq_lvp_lv_gap_resolutions_lv_material_type",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    lv_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_lvs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_dna: Mapped[str] = mapped_column(String(500), nullable=False)
    resolution_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resolved_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tenant_price_override_id: Mapped[str | None] = mapped_column(
        ForeignKey("lvp_tenant_price_overrides.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
