"""Subscription service — manage user plans, usage, and access control."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.models.subscription import PLAN_LIMITS, Plan, Subscription

log = structlog.get_logger()


async def get_or_create_subscription(db: AsyncSession, user_id: str) -> Subscription:
    """Load user's subscription, or create a 14-day trial if none exists."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()
    if sub is not None:
        return sub

    sub = Subscription.default_trial(user_id)
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    log.info("subscription_created_trial", user_id=user_id)
    return sub


async def require_active_subscription(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Subscription:
    """FastAPI dependency — raise 402 if user has no active subscription."""
    sub = await get_or_create_subscription(db, user_id)
    if not sub.is_active:
        raise HTTPException(
            status_code=402,
            detail="Abonnement abgelaufen oder inaktiv. Bitte aktualisieren Sie Ihren Plan.",
        )
    return sub


async def require_analyse_quota(
    sub: Subscription = Depends(require_active_subscription),
    db: AsyncSession = Depends(get_db),
) -> Subscription:
    """FastAPI dependency — raise 429 if user hit analysis quota."""
    ok, reason = sub.can_analyse()
    if not ok:
        raise HTTPException(status_code=429, detail=reason or "Quota exceeded")
    return sub


async def increment_analyse_usage(db: AsyncSession, user_id: str) -> None:
    """Increment the monthly analysis counter — call after successful analysis."""
    sub = await get_or_create_subscription(db, user_id)
    sub._reset_usage_if_new_period()
    sub.analysen_used += 1
    await db.commit()


def serialize_subscription(sub: Subscription) -> dict[str, Any]:
    """Convert Subscription to API response dict."""
    limits = sub.limits
    return {
        "plan": sub.plan,
        "status": sub.status,
        "is_active": sub.is_active,
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "usage": {
            "analysen_used": sub.analysen_used,
            "analysen_limit": limits.get("max_analysen_monthly"),
            "preislisten_limit": limits.get("max_preislisten"),
            "users_limit": limits.get("max_users"),
        },
        "features": {
            "watermark": limits.get("watermark", False),
        },
    }
