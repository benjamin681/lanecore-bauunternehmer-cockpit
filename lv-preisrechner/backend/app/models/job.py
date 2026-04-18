"""Background-Job-Tracking für lange Operationen (Preislisten-/LV-Parsing)."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Job(Base):
    """Ein asynchroner Hintergrund-Job.

    kind: "parse_price_list" | "parse_lv" | "calculate_lv" | "export_pdf"
    status: "queued" | "running" | "done" | "error"
    target_id: ID des Ziel-Objekts (price_list_id oder lv_id)
    """

    __tablename__ = "lvp_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lvp_tenants.id"), nullable=False, index=True
    )

    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    target_id: Mapped[str] = mapped_column(String(100), default="")
    target_kind: Mapped[str] = mapped_column(String(50), default="")  # "price_list" | "lv"

    progress: Mapped[int] = mapped_column(default=0)  # 0-100
    message: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
