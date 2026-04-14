"""Projekt model — groups Baupläne and analyses."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Projekt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projekte"

    user_id: Mapped[str] = mapped_column(String(255), index=True)  # Clerk User ID
    name: Mapped[str] = mapped_column(String(255))  # z.B. "Himmelweiler III"
    auftraggeber: Mapped[str | None] = mapped_column(String(255), index=True)
    adresse: Mapped[str | None] = mapped_column(String(500))
    plan_nr: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="aktiv")
    # aktiv | abgeschlossen | archiviert
    beschreibung: Mapped[str | None] = mapped_column(Text)
    # Aus dem Plan extrahiert:
    architekt: Mapped[str | None] = mapped_column(String(255))
    bauherr: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    analyse_jobs: Mapped[list["AnalyseJob"]] = relationship(  # type: ignore[name-defined]
        back_populates="projekt", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Projekt {self.name!r} ({self.id})>"
