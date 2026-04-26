"""Aufmaß-API (B+4.12 Iteration 4).

Routen:
- POST   /offers/{offer_id}/aufmass        Aufmaß aus accepted Offer erstellen
- GET    /lvs/{lv_id}/aufmasse             Liste der Aufmaße eines LVs
- GET    /aufmasse/{id}                    Detail mit allen Positions
- PATCH  /aufmasse/{id}/positions/{pos_id} Mengen-Edit / Notiz-Edit
- POST   /aufmasse/{id}/finalize           Status -> finalized
- GET    /aufmasse/{id}/summary            Differenz-Aggregat
- POST   /aufmasse/{id}/create-final-offer Final-Offer mit Aufmaß-Snapshot
- GET    /aufmasse/{id}/pdf                Aufmaß-Bestaetigung als PDF (Bonus)

Tenant-Scoping ueber tenant_id auf jedem Modell.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import CurrentUser, DbSession
from app.models.aufmass import Aufmass, AufmassPosition
from app.models.lv import LV
from app.models.offer import Offer
from app.models.tenant import Tenant
from app.schemas.aufmass import (
    AufmassCreate,
    AufmassDetail,
    AufmassOut,
    AufmassPositionOut,
    AufmassPositionUpdate,
    AufmassSummary,
)
from app.schemas.offer import OfferOut
from app.services.aufmass_service import (
    AufmassNotEditable,
    AufmassServiceError,
    create_aufmass_from_offer,
    create_final_offer_from_aufmass,
    finalize_aufmass,
    get_aufmass_summary,
    update_position_menge,
)

# Sub-Router unter /offers/{offer_id}/aufmass und /lvs/{lv_id}/aufmasse
offer_aufmass_router = APIRouter(tags=["aufmass"])

# Standalone-Router unter /aufmasse/{id}
aufmasse_router = APIRouter(prefix="/aufmasse", tags=["aufmass"])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_offer(db, offer_id: str, tenant_id: str) -> Offer:
    o = (
        db.query(Offer)
        .filter(Offer.id == offer_id, Offer.tenant_id == tenant_id)
        .first()
    )
    if o is None:
        raise HTTPException(status_code=404, detail="Offer nicht gefunden")
    return o


def _load_lv(db, lv_id: str, tenant_id: str) -> LV:
    lv = (
        db.query(LV)
        .filter(LV.id == lv_id, LV.tenant_id == tenant_id)
        .first()
    )
    if lv is None:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    return lv


def _load_aufmass(db, aufmass_id: str, tenant_id: str) -> Aufmass:
    a = (
        db.query(Aufmass)
        .filter(Aufmass.id == aufmass_id, Aufmass.tenant_id == tenant_id)
        .first()
    )
    if a is None:
        raise HTTPException(status_code=404, detail="Aufmaß nicht gefunden")
    return a


def _detail_payload(a: Aufmass) -> dict:
    return {
        **AufmassOut.model_validate(a).model_dump(),
        "positions": [AufmassPositionOut.model_validate(p) for p in a.positions],
    }


# --------------------------------------------------------------------------- #
# /offers/{offer_id}/aufmass + /lvs/{lv_id}/aufmasse
# --------------------------------------------------------------------------- #
@offer_aufmass_router.post(
    "/offers/{offer_id}/aufmass",
    response_model=AufmassDetail,
    status_code=201,
)
def create_aufmass(
    offer_id: str,
    payload: AufmassCreate,
    user: CurrentUser,
    db: DbSession,
) -> AufmassDetail:
    offer = _load_offer(db, offer_id, user.tenant_id)
    lv = _load_lv(db, offer.lv_id, user.tenant_id)
    try:
        aufmass = create_aufmass_from_offer(
            db=db, offer=offer, lv=lv, notes=payload.internal_notes
        )
        db.commit()
        db.refresh(aufmass)
    except AufmassServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return AufmassDetail.model_validate(_detail_payload(aufmass))


@offer_aufmass_router.get(
    "/lvs/{lv_id}/aufmasse",
    response_model=list[AufmassOut],
)
def list_aufmasse_for_lv(
    lv_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[AufmassOut]:
    _load_lv(db, lv_id, user.tenant_id)
    rows = (
        db.query(Aufmass)
        .filter(Aufmass.lv_id == lv_id, Aufmass.tenant_id == user.tenant_id)
        .order_by(Aufmass.created_at.desc())
        .all()
    )
    return [AufmassOut.model_validate(a) for a in rows]


# --------------------------------------------------------------------------- #
# /aufmasse/{id}/...  — WICHTIG: statische Pfade vor /{id}-Catchall
# --------------------------------------------------------------------------- #
@aufmasse_router.get("/{aufmass_id}/summary", response_model=AufmassSummary)
def get_summary(
    aufmass_id: str,
    user: CurrentUser,
    db: DbSession,
) -> AufmassSummary:
    a = _load_aufmass(db, aufmass_id, user.tenant_id)
    return AufmassSummary.model_validate(get_aufmass_summary(a))


@aufmasse_router.post(
    "/{aufmass_id}/finalize", response_model=AufmassDetail
)
def finalize(
    aufmass_id: str,
    user: CurrentUser,
    db: DbSession,
) -> AufmassDetail:
    a = _load_aufmass(db, aufmass_id, user.tenant_id)
    try:
        finalize_aufmass(db, a, user_id=user.id)
        db.commit()
        db.refresh(a)
    except AufmassServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return AufmassDetail.model_validate(_detail_payload(a))


@aufmasse_router.post(
    "/{aufmass_id}/create-final-offer",
    response_model=OfferOut,
    status_code=201,
)
def create_final_offer(
    aufmass_id: str,
    user: CurrentUser,
    db: DbSession,
) -> OfferOut:
    a = _load_aufmass(db, aufmass_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")
    try:
        offer = create_final_offer_from_aufmass(db, a, tenant, user_id=user.id)
        db.commit()
        db.refresh(offer)
    except AufmassServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return OfferOut.model_validate(offer)


@aufmasse_router.patch(
    "/{aufmass_id}/positions/{pos_id}",
    response_model=AufmassPositionOut,
)
def patch_position(
    aufmass_id: str,
    pos_id: str,
    payload: AufmassPositionUpdate,
    user: CurrentUser,
    db: DbSession,
) -> AufmassPositionOut:
    a = _load_aufmass(db, aufmass_id, user.tenant_id)
    pos = (
        db.query(AufmassPosition)
        .filter(
            AufmassPosition.id == pos_id,
            AufmassPosition.aufmass_id == aufmass_id,
        )
        .first()
    )
    if pos is None:
        raise HTTPException(status_code=404, detail="Aufmaß-Position nicht gefunden")
    try:
        update_position_menge(
            db, a, pos,
            new_menge=payload.gemessene_menge,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(pos)
    except AufmassNotEditable as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except AufmassServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    return AufmassPositionOut.model_validate(pos)


@aufmasse_router.get("/{aufmass_id}/pdf")
def download_aufmass_pdf(
    aufmass_id: str,
    user: CurrentUser,
    db: DbSession,
    inline: bool = Query(default=False),
):
    """Bonus (Phase 10): Aufmaß-Bestaetigung als PDF.

    Verwendet das eigenes_layout-Template mit den gemessenen Mengen,
    aber ohne Status-Header — dient als Aufmaß-Beleg (nicht als Angebot).
    """
    a = _load_aufmass(db, aufmass_id, user.tenant_id)
    lv = _load_lv(db, a.lv_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")
    from app.services.aufmass_pdf import generate_aufmass_offer_pdf

    try:
        pdf_bytes = generate_aufmass_offer_pdf(a, lv, tenant)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    filename = f"Aufmass-{a.aufmass_number}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )


@aufmasse_router.get("/{aufmass_id}", response_model=AufmassDetail)
def get_aufmass(
    aufmass_id: str,
    user: CurrentUser,
    db: DbSession,
) -> AufmassDetail:
    a = _load_aufmass(db, aufmass_id, user.tenant_id)
    return AufmassDetail.model_validate(_detail_payload(a))
