"""Projekt model — groups Baupläne and analyses."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Projekt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projekte"

    user_id: Mapped[str] = mapped_column(String(255), index=True)  # Clerk User ID
    name: Mapped[str] = mapped_column(String(255))
    auftraggeber: Mapped[str | None] = mapped_column(String(255))
    beschreibung: Mapped[str | None] = mapped_column(String(2000))

    # Relationships
    analyse_jobs: Mapped[list["AnalyseJob"]] = relationship(  # type: ignore[name-defined]
        back_populates="projekt", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Projekt {self.name!r} ({self.id})>"
