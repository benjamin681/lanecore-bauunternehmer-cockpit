"""Tenant = Trockenbau-Betrieb (Mandant)."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Tenant(Base):
    __tablename__ = "lvp_tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Kalkulations-Defaults des Betriebs
    stundensatz_eur: Mapped[float] = mapped_column(default=46.0)
    bgk_prozent: Mapped[float] = mapped_column(default=10.0)
    agk_prozent: Mapped[float] = mapped_column(default=12.0)
    wg_prozent: Mapped[float] = mapped_column(default=5.0)

    # Feature-Flag: aktiviert die neue Pricing-Pipeline (SupplierPriceEntry +
    # price_lookup.py) fuer diesen Tenant. Default False -- Integration in die
    # Kalkulation erfolgt erst in einem spaeteren Sub-Block.
    use_new_pricing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # B+4.8: freie JSON-Stammdaten fuer Briefkopf, Bankverbindung,
    # Footer im Angebots-PDF. Erwartete Keys siehe Migration
    # e7a8d2c5b14f. Nullable; PDF-Service nutzt sinnvolle Defaults
    # wenn Felder fehlen (z.B. tenant.name als firma).
    company_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["User"]] = relationship(  # type: ignore  # noqa: F821
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    price_lists: Mapped[list["PriceList"]] = relationship(  # type: ignore  # noqa: F821
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    lvs: Mapped[list["LV"]] = relationship(  # type: ignore  # noqa: F821
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
