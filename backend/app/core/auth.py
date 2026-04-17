"""Clerk JWT authentication for FastAPI with JWKS TTL + Subscription Guard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

log = structlog.get_logger()

# Dev mode: skip auth when no Clerk keys configured
_DEV_MODE = not settings.clerk_secret_key

security = HTTPBearer(auto_error=not _DEV_MODE)

# --- JWKS Cache with TTL ---------------------------------------------------
_JWKS_TTL = timedelta(hours=12)
_jwks_cache: dict[str, Any] = {"data": None, "expires_at": None}


async def _get_clerk_jwks() -> dict:
    """Fetch Clerk's JWKS for JWT verification (cached 12h)."""
    now = datetime.now(timezone.utc)
    data = _jwks_cache.get("data")
    expires = _jwks_cache.get("expires_at")
    if data is not None and expires is not None and expires > now:
        return data

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://api.clerk.com/v1/jwks",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
        )
        resp.raise_for_status()
        jwks = resp.json()

    _jwks_cache["data"] = jwks
    _jwks_cache["expires_at"] = now + _JWKS_TTL
    return jwks


def invalidate_jwks_cache() -> None:
    """Force-refresh JWKS on next request (e.g. after key rotation)."""
    _jwks_cache["data"] = None
    _jwks_cache["expires_at"] = None


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    """
    FastAPI dependency: validates Clerk JWT and returns user ID.
    In dev mode (no CLERK_SECRET_KEY), returns a dev user ID.
    """
    if _DEV_MODE:
        return "dev-user"

    if credentials is None:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert.")

    token = credentials.credentials

    try:
        jwks = await _get_clerk_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        rsa_key = None
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                rsa_key = key
                break

        if rsa_key is None:
            # Key-Rotation: invalidate cache & try again once
            invalidate_jwks_cache()
            jwks = await _get_clerk_jwks()
            for key in jwks.get("keys", []):
                if key["kid"] == kid:
                    rsa_key = key
                    break
            if rsa_key is None:
                raise HTTPException(status_code=401, detail="Token-Schlüssel nicht gefunden.")

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Kein Benutzer im Token.")

        return user_id

    except JWTError as e:
        log.warning("jwt_validation_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Ungültiges Token.") from e


# --- Optional user (for endpoints that work with or without auth) ----------
async def get_current_user_id_optional(
    credentials: HTTPAuthorizationCredentials | None = Security(HTTPBearer(auto_error=False)),
) -> str | None:
    if credentials is None:
        return None
    try:
        return await get_current_user_id(credentials)
    except HTTPException:
        return None
