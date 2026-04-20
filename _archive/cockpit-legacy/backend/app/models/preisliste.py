"""Preislisten und Produkte — Säule 2: Preisvergleich."""

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Preisliste(Base, UUIDMixin, TimestampMixin):
    """Eine hochgeladene Preisliste (PDF oder manuell)."""

    __tablename__ = "preislisten"

    anbieter: Mapped[str] = mapped_column(String(255))
    quelle: Mapped[str] = mapped_column(String(50))  # pdf_upload | manual | api
    dateiname: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending | processing | completed | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    produkt_count: Mapped[int] = mapped_column(Integer, default=0)

    # Beziehung zu Produkten
    produkte: Mapped[list["Produkt"]] = relationship(
        "Produkt", back_populates="preisliste", cascade="all, delete-orphan"
    )


class Produkt(Base, UUIDMixin, TimestampMixin):
    """Einzelnes Produkt aus einer Preisliste."""

    __tablename__ = "produkte"

    preisliste_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("preislisten.id"), nullable=False
    )
    artikel_nr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bezeichnung: Mapped[str] = mapped_column(String(500))
    hersteller: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kategorie: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # z.B. "CW-Profil", "GK-Platte", "Daemmung", "Befestigung", "Zubehoer"

    einheit: Mapped[str] = mapped_column(String(20))  # Stk, m, m2, Pkg, Bund, etc.
    preis_netto: Mapped[float] = mapped_column(Numeric(10, 4))
    preis_brutto: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    menge_pro_einheit: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    # z.B. Paket mit 10 Platten → menge_pro_einheit=10

    verfuegbar: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Original-Text aus dem PDF für Audit

    preisliste: Mapped["Preisliste"] = relationship("Preisliste", back_populates="produkte")
