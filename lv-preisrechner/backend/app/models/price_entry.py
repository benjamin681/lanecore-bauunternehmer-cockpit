"""Einzelner Preis-Eintrag in einer Preisliste."""

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class PriceEntry(Base):
    __tablename__ = "lvp_price_entries"
    __table_args__ = (
        Index("ix_lvp_price_entries_list_dna", "price_list_id", "dna"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    price_list_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_price_lists.id"), nullable=False, index=True
    )

    art_nr: Mapped[str] = mapped_column(String(100), default="")
    dna: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    hersteller: Mapped[str] = mapped_column(String(100), default="")
    kategorie: Mapped[str] = mapped_column(String(100), default="")
    produktname: Mapped[str] = mapped_column(String(300), default="")
    abmessungen: Mapped[str] = mapped_column(String(200), default="")
    variante: Mapped[str] = mapped_column(String(200), default="")

    preis: Mapped[float] = mapped_column(default=0.0)  # wie angegeben
    einheit: Mapped[str] = mapped_column(String(50), default="")  # "€/m²", "€/Paket (500 Stk)"

    # Normalisiert für Matching
    preis_pro_basis: Mapped[float] = mapped_column(default=0.0)  # €/m², €/Stk, €/lfm
    basis_einheit: Mapped[str] = mapped_column(String(20), default="")  # "m²", "Stk", "lfm"

    konfidenz: Mapped[float] = mapped_column(default=1.0)  # 0.0–1.0
    manuell_korrigiert: Mapped[bool] = mapped_column(Boolean, default=False)

    price_list: Mapped["PriceList"] = relationship(back_populates="entries")  # type: ignore  # noqa: F821
