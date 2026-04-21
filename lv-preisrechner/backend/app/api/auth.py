"""Auth-Routen: /register, /login, /me."""

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.models.tenant import Tenant
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TenantUpdate,
    TokenResponse,
)
from app.services.auth_service import login as _login
from app.services.auth_service import register as _register
from app.services.pricing_readiness import is_ready_for_new_pricing

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: DbSession) -> TokenResponse:
    return _register(db, req)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: DbSession) -> TokenResponse:
    return _login(db, req)


def _build_me(user, tenant) -> MeResponse:
    return MeResponse(
        user_id=user.id,
        email=user.email,
        vorname=user.vorname,
        nachname=user.nachname,
        tenant_id=tenant.id,
        firma=tenant.name,
        stundensatz_eur=tenant.stundensatz_eur,
        bgk_prozent=tenant.bgk_prozent,
        agk_prozent=tenant.agk_prozent,
        wg_prozent=tenant.wg_prozent,
        use_new_pricing=bool(getattr(tenant, "use_new_pricing", False)),
    )


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, db: DbSession) -> MeResponse:
    tenant = db.get(Tenant, user.tenant_id)
    assert tenant is not None
    return _build_me(user, tenant)


@router.patch("/me/tenant", response_model=MeResponse)
def update_tenant(update: TenantUpdate, user: CurrentUser, db: DbSession) -> MeResponse:
    """Update Firma-Namen + Kalkulations-Defaults (Stundensatz, BGK/AGK/W+G)
    + use_new_pricing-Flag.

    Wird use_new_pricing auf True gesetzt, muss der Tenant entweder eine
    aktive Lieferanten-Preisliste ODER mindestens einen Tenant-Override
    besitzen (Variante A-plus aus B+4.2). Andernfalls HTTP 400.
    """
    tenant = db.get(Tenant, user.tenant_id)
    assert tenant is not None
    data = update.model_dump(exclude_unset=True)
    if "firma" in data and data["firma"]:
        tenant.name = data["firma"]
    for key in ("stundensatz_eur", "bgk_prozent", "agk_prozent", "wg_prozent"):
        if key in data and data[key] is not None:
            setattr(tenant, key, data[key])
    if "use_new_pricing" in data and data["use_new_pricing"] is not None:
        new_value = bool(data["use_new_pricing"])
        if new_value and not is_ready_for_new_pricing(db, tenant.id):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Keine aktive Lieferanten-Preisliste und kein Preis-"
                    "Override vorhanden. Bitte mindestens eines von beidem "
                    "anlegen, bevor die neue Preis-Engine aktiviert wird."
                ),
            )
        tenant.use_new_pricing = new_value
    db.commit()
    db.refresh(tenant)
    return _build_me(user, tenant)
