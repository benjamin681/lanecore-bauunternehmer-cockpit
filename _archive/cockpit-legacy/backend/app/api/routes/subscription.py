"""Subscription / billing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.services.subscription_service import (
    get_or_create_subscription,
    serialize_subscription,
)

router = APIRouter()


@router.get("/me")
async def get_my_subscription(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    sub = await get_or_create_subscription(db, user_id)
    return serialize_subscription(sub)


@router.get("/plans")
async def list_plans():
    """Public list of available plans + their limits."""
    from app.models.subscription import PLAN_LIMITS, Plan
    return {
        "plans": [
            {
                "id": Plan.TRIAL,
                "name": "Testversion",
                "price_monthly": 0,
                "description": "14 Tage kostenlos testen",
                "limits": PLAN_LIMITS[Plan.TRIAL],
            },
            {
                "id": Plan.STARTER,
                "name": "Starter",
                "price_monthly": 49,
                "description": "20 Analysen/Monat, 1 Nutzer",
                "limits": PLAN_LIMITS[Plan.STARTER],
            },
            {
                "id": Plan.BUSINESS,
                "name": "Business",
                "price_monthly": 149,
                "description": "Unbegrenzt, 5 Nutzer, Priority-Support",
                "limits": PLAN_LIMITS[Plan.BUSINESS],
            },
            {
                "id": Plan.ENTERPRISE,
                "name": "Enterprise",
                "price_monthly": None,
                "description": "Individuelles Angebot — auf Anfrage",
                "limits": PLAN_LIMITS[Plan.ENTERPRISE],
            },
        ]
    }
