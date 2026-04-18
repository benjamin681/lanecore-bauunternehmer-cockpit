"""Preisliste eines Kunden."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class PriceList(Base):
    __tablename__ = "lvp_price_lists"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id"), nullable=False, index=True
    )

    haendler: Mapped[str] = mapped_column(String(200), nullable=False)
    niederlassung: Mapped[str] = mapped_column(String(200), default="")
    stand_monat: Mapped[str] = mapped_column(String(20), default="")

    original_dateiname: Mapped[str] = mapped_column(String(500), default="")
    original_pdf_pfad: Mapped[str] = mapped_column(String(500), default="")
    original_pdf_sha256: Mapped[str] = mapped_column(String(64), default="")

    # "parsing" | "review" | "aktiv" | "archiviert"
    status: Mapped[str] = mapped_column(String(20), default="parsing")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=False)

    eintraege_gesamt: Mapped[int] = mapped_column(default=0)
    eintraege_unsicher: Mapped[int] = mapped_column(default=0)  # Konfidenz < 0.85

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped["Tenant"] = relationship(back_populates="price_lists")  # type: ignore  # noqa: F821
    entries: Mapped[list["PriceEntry"]] = relationship(  # type: ignore  # noqa: F821
        back_populates="price_list",
        cascade="all, delete-orphan",
    )
