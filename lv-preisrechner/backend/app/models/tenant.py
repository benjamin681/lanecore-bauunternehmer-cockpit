"""Tenant = Trockenbau-Betrieb (Mandant)."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text
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

    # B+4.9: typisierte Stammdaten fuer Briefkopf, Bankverbindung,
    # PDF-Footer und Default-Vertragsbedingungen. Vorher als JSON-Feld
    # company_settings (B+4.8, ersetzt durch Migration b9c4e1f2a583).
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_address_street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_address_country: Mapped[str] = mapped_column(
        String(2), nullable=False, default="DE", server_default="DE"
    )
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vat_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bank_bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_payment_terms_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=14, server_default="14"
    )
    default_offer_validity_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )
    default_agb_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_text: Mapped[str | None] = mapped_column(Text, nullable=True)

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
