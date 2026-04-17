"""Subscription model — tracks user plan + usage."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    pass


# --- Plan Definitions ------------------------------------------------------
class Plan:
    TRIAL = "trial"
    STARTER = "starter"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


PLAN_LIMITS: dict[str, dict] = {
    Plan.TRIAL: {
        "max_analysen_monthly": 3,
        "max_preislisten": 5,
        "max_users": 1,
        "watermark": True,
        "trial_days": 14,
    },
    Plan.STARTER: {
        "max_analysen_monthly": 20,
        "max_preislisten": 20,
        "max_users": 1,
        "watermark": False,
    },
    Plan.BUSINESS: {
        "max_analysen_monthly": None,  # unlimited
        "max_preislisten": None,
        "max_users": 5,
        "watermark": False,
    },
    Plan.ENTERPRISE: {
        "max_analysen_monthly": None,
        "max_preislisten": None,
        "max_users": None,
        "watermark": False,
    },
}


class Subscription(Base):
    """A user's subscription status + usage tracking."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    plan: Mapped[str] = mapped_column(String(30), nullable=False, default=Plan.TRIAL)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active"
    )  # active | paused | cancelled | expired

    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Usage counters (reset monthly via cron or on-read if stale)
    usage_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    analysen_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- Helpers -------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        if self.status != "active":
            return False
        if self.plan == Plan.TRIAL and self.trial_ends_at:
            return self.trial_ends_at > datetime.now(timezone.utc)
        return True

    @property
    def limits(self) -> dict:
        return PLAN_LIMITS.get(self.plan, PLAN_LIMITS[Plan.TRIAL])

    def can_analyse(self) -> tuple[bool, str | None]:
        """Check if user may run another analysis."""
        if not self.is_active:
            return False, "Abonnement abgelaufen oder inaktiv"
        self._reset_usage_if_new_period()
        lim = self.limits.get("max_analysen_monthly")
        if lim is not None and self.analysen_used >= lim:
            return False, f"Monatliches Analyse-Limit erreicht ({lim})"
        return True, None

    def _reset_usage_if_new_period(self) -> None:
        now = datetime.now(timezone.utc)
        if now - self.usage_period_start >= timedelta(days=30):
            self.usage_period_start = now
            self.analysen_used = 0

    @classmethod
    def default_trial(cls, user_id: str) -> "Subscription":
        now = datetime.now(timezone.utc)
        return cls(
            user_id=user_id,
            plan=Plan.TRIAL,
            status="active",
            trial_ends_at=now + timedelta(days=14),
        )
