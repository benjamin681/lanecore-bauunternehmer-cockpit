"""LV = ein hochgeladenes Leistungsverzeichnis."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class LV(Base):
    __tablename__ = "lvs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)

    projekt_name: Mapped[str] = mapped_column(String(300), default="")
    auftraggeber: Mapped[str] = mapped_column(String(300), default="")

    original_dateiname: Mapped[str] = mapped_column(String(500), default="")
    original_pdf_pfad: Mapped[str] = mapped_column(String(500), default="")
    original_pdf_sha256: Mapped[str] = mapped_column(String(64), default="")
    ausgefuelltes_pdf_pfad: Mapped[str] = mapped_column(String(500), default="")

    # "uploaded" | "extracting" | "review_needed" | "calculated" | "exported"
    status: Mapped[str] = mapped_column(String(30), default="uploaded")

    positionen_gesamt: Mapped[int] = mapped_column(default=0)
    positionen_gematcht: Mapped[int] = mapped_column(default=0)
    positionen_unsicher: Mapped[int] = mapped_column(default=0)

    angebotssumme_netto: Mapped[float] = mapped_column(default=0.0)

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
