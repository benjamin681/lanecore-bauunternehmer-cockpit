"""Clerk JWT authentication for FastAPI."""

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
import httpx
import structlog

from app.core.config import settings

# Dev mode: skip auth when no Clerk keys configured
_DEV_MODE = not settings.clerk_secret_key

log = structlog.get_logger()
security = HTTPBearer(auto_error=not _DEV_MODE)

# Clerk JWKS (cached in production)
_jwks_cache: dict | None = None


async def _get_clerk_jwks() -> dict:
    """Fetch Clerk's JWKS for JWT verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.clerk.com/v1/jwks", headers={
            "Authorization": f"Bearer {settings.clerk_secret_key}",
        })
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


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
