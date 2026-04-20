"""Einzelne LV-Position: OZ, Menge, Einheit, Kurztext, EP, GP."""

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class Position(Base):
    __tablename__ = "lvp_positions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    lv_id: Mapped[str] = mapped_column(ForeignKey("lvp_lvs.id"), nullable=False, index=True)

    reihenfolge: Mapped[int] = mapped_column(default=0)

    # Aus PDF extrahiert
    oz: Mapped[str] = mapped_column(String(50), default="")  # "610.1", "02.03.01"
    titel: Mapped[str] = mapped_column(String(300), default="")  # "Innenwände in Trockenbauweise"
    kurztext: Mapped[str] = mapped_column(Text, default="")
    langtext: Mapped[Text] = mapped_column(Text, default="")

    menge: Mapped[float] = mapped_column(default=0.0)
    einheit: Mapped[str] = mapped_column(String(20), default="")  # "m²", "Stk", "lfm", "psch"

    # Systemerkennung
    erkanntes_system: Mapped[str] = mapped_column(String(50), default="")  # "W112", "W115", ...
    feuerwiderstand: Mapped[str] = mapped_column(String(20), default="")  # "F30", "F90"
    plattentyp: Mapped[str] = mapped_column(String(50), default="")  # "GKB", "GKF", "GKFi"

    # Fabrikat-Angaben (aus LV extrahiert, vom Bieter auszufuellen)
    leit_fabrikat: Mapped[str] = mapped_column(String(200), default="")  # z.B. "Knauf o.glw." aus LV-Text
    angebotenes_fabrikat: Mapped[str] = mapped_column(String(200), default="")  # was der Bieter anbietet

    # Materialrezept (JSON: [{dna, menge, einheit, preis, gp}])
    materialien: Mapped[list] = mapped_column(JSON, default=list)

    # Kalkulation
    material_ep: Mapped[float] = mapped_column(default=0.0)
    lohn_stunden: Mapped[float] = mapped_column(default=0.0)
    lohn_ep: Mapped[float] = mapped_column(default=0.0)
    zuschlaege_ep: Mapped[float] = mapped_column(default=0.0)
    ep: Mapped[float] = mapped_column(default=0.0)  # Einheitspreis final
    gp: Mapped[float] = mapped_column(default=0.0)  # Gesamtpreis = Menge * EP

    konfidenz: Mapped[float] = mapped_column(default=0.0)
    manuell_korrigiert: Mapped[bool] = mapped_column(Boolean, default=False)
    warnung: Mapped[str] = mapped_column(Text, default="")  # z.B. "Kein Match für GKF 15mm"

    lv: Mapped["LV"] = relationship(back_populates="positions")  # type: ignore  # noqa: F821
