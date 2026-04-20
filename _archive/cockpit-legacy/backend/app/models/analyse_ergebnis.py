"""AnalyseErgebnis model — stores structured analysis output."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class AnalyseErgebnis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analyse_ergebnisse"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyse_jobs.id"), unique=True
    )

    # Plan metadata
    plantyp: Mapped[str | None] = mapped_column(String(50))  # grundriss | deckenspiegel | ...
    massstab: Mapped[str | None] = mapped_column(String(20))  # "1:100"
    geschoss: Mapped[str | None] = mapped_column(String(100))

    # Confidence
    konfidenz: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))  # 0.000–1.000

    # Structured results (JSONB for flexible schema)
    raeume: Mapped[dict | None] = mapped_column(JSONB)
    waende: Mapped[dict | None] = mapped_column(JSONB)
    decken: Mapped[dict | None] = mapped_column(JSONB)
    oeffnungen: Mapped[dict | None] = mapped_column(JSONB)
    details: Mapped[dict | None] = mapped_column(JSONB)
    gestrichene_positionen: Mapped[dict | None] = mapped_column(JSONB)
    warnungen: Mapped[dict | None] = mapped_column(JSONB)

    # Audit trail
    raw_claude_response: Mapped[str | None] = mapped_column(Text)
    prompt_hash: Mapped[str | None] = mapped_column(String(64))

    # Relationship
    job: Mapped["AnalyseJob"] = relationship(back_populates="ergebnis")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<AnalyseErgebnis plantyp={self.plantyp} konfidenz={self.konfidenz}>"
