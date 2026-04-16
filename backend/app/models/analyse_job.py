"""AnalyseJob model — tracks PDF analysis lifecycle."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class AnalyseJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analyse_jobs"

    projekt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projekte.id"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    s3_key: Mapped[str] = mapped_column(String(512))

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending | processing | completed | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0–100
    error_message: Mapped[str | None] = mapped_column(Text)

    # Claude API cost tracking
    model_used: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    projekt: Mapped["Projekt"] = relationship(back_populates="analyse_jobs")  # type: ignore[name-defined]
    ergebnis: Mapped["AnalyseErgebnis | None"] = relationship(  # type: ignore[name-defined]
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<AnalyseJob {self.filename!r} status={self.status}>"
