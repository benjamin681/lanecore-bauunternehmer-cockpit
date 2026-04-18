"""Auth-Service: Registrierung, Login."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


def register(db: Session, req: RegisterRequest) -> TokenResponse:
    """Neuer Tenant + erster User."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-Mail bereits registriert",
        )

    tenant = Tenant(name=req.firma)
    db.add(tenant)
    db.flush()  # tenant.id verfügbar

    user = User(
        tenant_id=tenant.id,
        email=req.email.lower(),
        password_hash=hash_password(req.password),
        vorname=req.vorname,
        nachname=req.nachname,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(tenant)

    token = create_access_token(subject=user.id, extra={"tid": tenant.id})
    return TokenResponse(
        access_token=token, user_id=user.id, email=user.email, firma=tenant.name
    )


def login(db: Session, req: LoginRequest) -> TokenResponse:
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-Mail oder Passwort falsch",
        )
    if not user.aktiv:
        raise HTTPException(status_code=403, detail="Account deaktiviert")
    tenant = db.get(Tenant, user.tenant_id)
    token = create_access_token(subject=user.id, extra={"tid": user.tenant_id})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        firma=tenant.name if tenant else "",
    )
