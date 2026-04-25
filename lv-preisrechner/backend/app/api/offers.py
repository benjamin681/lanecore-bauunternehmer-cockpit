"""Offer-API (B+4.11): Offer-Lifecycle-Endpoints.

Routen:
- POST   /lvs/{lv_id}/offers           Neue Offer aus LV
- GET    /lvs/{lv_id}/offers           Liste der Offers eines LVs
- GET    /offers/{offer_id}            Offer-Detail mit Status-History
- PATCH  /offers/{offer_id}/status     Status-Wechsel (mit optional reason)
- GET    /offers/{offer_id}/pdf        PDF im Format der Offer

Tenant-Scoping ueber lv.tenant_id == user.tenant_id und
offer.tenant_id == user.tenant_id.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import CurrentUser, DbSession
from app.models.lv import LV
from app.models.offer import Offer, OfferStatus
from app.models.tenant import Tenant
from app.schemas.offer import (
    OfferCreate,
    OfferDetail,
    OfferOut,
    OfferStatusChangeOut,
    OfferStatusUpdate,
)
from app.services.offer_service import (
    InvalidOfferTransition,
    OfferServiceError,
    change_offer_status,
    create_offer_from_lv,
    get_offer_pdf,
)

# Sub-Router unter /lvs/{lv_id}/offers
lv_offers_router = APIRouter(prefix="/lvs", tags=["offers"])

# Standalone-Router unter /offers/{offer_id}
offers_router = APIRouter(prefix="/offers", tags=["offers"])


def _load_lv(db, lv_id: str, tenant_id: str) -> LV:
    lv = (
        db.query(LV)
        .filter(LV.id == lv_id, LV.tenant_id == tenant_id)
        .first()
    )
    if lv is None:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    return lv


def _load_offer(db, offer_id: str, tenant_id: str) -> Offer:
    offer = (
        db.query(Offer)
        .filter(Offer.id == offer_id, Offer.tenant_id == tenant_id)
        .first()
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer nicht gefunden")
    return offer


# --------------------------------------------------------------------------- #
# LV-Sub-Router
# --------------------------------------------------------------------------- #
@lv_offers_router.post(
    "/{lv_id}/offers",
    response_model=OfferOut,
    status_code=201,
)
def create_offer(
    lv_id: str,
    payload: OfferCreate,
    user: CurrentUser,
    db: DbSession,
) -> OfferOut:
    lv = _load_lv(db, lv_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")

    try:
        offer = create_offer_from_lv(
            db=db,
            lv=lv,
            tenant=tenant,
            pdf_format=payload.pdf_format,
            user_id=user.id,
            notes=payload.internal_notes,
        )
        db.commit()
        db.refresh(offer)
    except OfferServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    return OfferOut.model_validate(offer)


@lv_offers_router.get(
    "/{lv_id}/offers",
    response_model=list[OfferOut],
)
def list_offers_for_lv(
    lv_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[OfferOut]:
    _load_lv(db, lv_id, user.tenant_id)
    offers = (
        db.query(Offer)
        .filter(Offer.lv_id == lv_id, Offer.tenant_id == user.tenant_id)
        .order_by(Offer.created_at.desc())
        .all()
    )
    return [OfferOut.model_validate(o) for o in offers]


# --------------------------------------------------------------------------- #
# Offer-Standalone-Router
# --------------------------------------------------------------------------- #
# WICHTIG: Statische Pfade (lv-summary) MUESSEN vor dem
# Catch-All "/{offer_id}" registriert werden — FastAPI matched in Reihenfolge.
@offers_router.get(
    "/lv-summary",
    response_model=dict[str, dict],
)
def list_offer_summary_per_lv(
    user: CurrentUser,
    db: DbSession,
) -> dict[str, dict]:
    """Liefert pro LV des Tenants einen Aggregat-Eintrag."""
    from datetime import UTC, datetime, timedelta

    rows = (
        db.query(Offer)
        .filter(Offer.tenant_id == user.tenant_id)
        .order_by(Offer.lv_id, Offer.created_at.desc())
        .all()
    )
    today = datetime.now(UTC).date()
    soon_threshold = today + timedelta(days=7)
    summary: dict[str, dict] = {}
    for o in rows:
        if o.lv_id in summary:
            summary[o.lv_id]["offer_count"] += 1
            continue
        expiring_soon = (
            o.status == OfferStatus.SENT.value
            and o.valid_until is not None
            and today <= o.valid_until <= soon_threshold
        )
        summary[o.lv_id] = {
            "offer_count": 1,
            "latest_status": o.status,
            "latest_offer_number": o.offer_number,
            "latest_valid_until": o.valid_until.isoformat() if o.valid_until else None,
            "expiring_soon": expiring_soon,
        }
    return summary


@offers_router.get(
    "/{offer_id}",
    response_model=OfferDetail,
)
def get_offer(
    offer_id: str,
    user: CurrentUser,
    db: DbSession,
) -> OfferDetail:
    offer = _load_offer(db, offer_id, user.tenant_id)
    return OfferDetail.model_validate(
        {
            **OfferOut.model_validate(offer).model_dump(),
            "status_history": [
                OfferStatusChangeOut.model_validate(c) for c in offer.status_changes
            ],
        }
    )


@offers_router.patch(
    "/{offer_id}/status",
    response_model=OfferDetail,
)
def patch_offer_status(
    offer_id: str,
    payload: OfferStatusUpdate,
    user: CurrentUser,
    db: DbSession,
) -> OfferDetail:
    offer = _load_offer(db, offer_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")

    try:
        change_offer_status(
            db=db,
            offer=offer,
            tenant=tenant,
            new_status=payload.status,
            user_id=user.id,
            reason=payload.reason,
            on_date=payload.on_date,
        )
        db.commit()
        db.refresh(offer)
    except InvalidOfferTransition as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except OfferServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    return OfferDetail.model_validate(
        {
            **OfferOut.model_validate(offer).model_dump(),
            "status_history": [
                OfferStatusChangeOut.model_validate(c) for c in offer.status_changes
            ],
        }
    )


@offers_router.get("/{offer_id}/pdf")
def download_offer_pdf(
    offer_id: str,
    user: CurrentUser,
    db: DbSession,
    inline: bool = Query(default=False),
):
    offer = _load_offer(db, offer_id, user.tenant_id)
    lv = _load_lv(db, offer.lv_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")

    try:
        pdf_bytes = get_offer_pdf(offer, lv, tenant)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    filename = f"{offer.offer_number}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )
