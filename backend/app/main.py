"""LaneCore AI — FastAPI Application Entry Point."""

import os
import traceback
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.exceptions import LaneCoreError, lanecore_exception_handler
from app.api.routes import bauplan, health, preisliste, projekte, stats, subscription

# Optional: audit route (added by separate feature)
try:
    from app.api.routes import audit as _audit_module  # type: ignore
except ImportError:
    _audit_module = None

log = structlog.get_logger()

# --- Sentry (optional, prod only) -----------------------------------------
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=settings.app_env,
            release=os.getenv("RELEASE_VERSION", "dev"),
            traces_sample_rate=0.1,  # 10% traces to reduce cost
            profiles_sample_rate=0.0,
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                SqlalchemyIntegration(),
            ],
            send_default_pii=False,
        )
        log.info("sentry_initialized", env=settings.app_env)
    except ImportError:
        log.warning("sentry_sdk_not_installed_but_dsn_set")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup: DB connection pool, etc.
    yield
    # Shutdown: cleanup


app = FastAPI(
    title="LaneCore AI API",
    description="Bauunternehmer-Cockpit — Bauplan-Analyse, Preisvergleich, Angebotserstellung",
    version="0.1.0",
    lifespan=lifespan,
    # Honor X-Forwarded-Proto from Render/Vercel/Cloudflare so redirects use HTTPS
    root_path=os.getenv("ROOT_PATH", ""),
)

# Exception handlers
app.add_exception_handler(LaneCoreError, lanecore_exception_handler)  # type: ignore[arg-type]


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return traceback in response so we can debug production errors."""
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    # Hide full traceback in production — log it, return minimal info
    if settings.app_env == "production":
        log.error("unhandled_exception", error=str(exc), path=str(request.url), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "trace_id": request.headers.get("x-request-id")},
        )
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": "".join(tb[-5:])},
    )


# --- HTTPS redirect middleware for Render/Cloudflare -----------------------
@app.middleware("http")
async def force_https_in_proxied_redirects(request: Request, call_next):
    """Render/Cloudflare terminate TLS, so scheme on request is 'http'.

    Starlette uses request.url_for(...) which reads scheme — we force HTTPS
    behind a proxy by trusting X-Forwarded-Proto before handing to the app.
    """
    forwarded = request.headers.get("x-forwarded-proto", "").lower()
    if forwarded == "https":
        request.scope["scheme"] = "https"
    response = await call_next(request)
    # Fix any Location headers that might have leaked http://
    location = response.headers.get("location")
    if location and location.startswith("http://") and forwarded == "https":
        response.headers["location"] = "https://" + location[len("http://"):]
    return response

# CORS — allow Vercel preview URLs + configured origins
_cors_origins = list(settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*-lanecore-ai\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(bauplan.router, prefix="/api/v1/bauplan", tags=["bauplan-analyse"])
app.include_router(projekte.router, prefix="/api/v1/projekte", tags=["projekte"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["statistics"])
app.include_router(preisliste.router, prefix="/api/v1/preislisten", tags=["preislisten"])
app.include_router(subscription.router, prefix="/api/v1/subscription", tags=["subscription"])
if _audit_module is not None:
    app.include_router(_audit_module.router, prefix="/api/v1/audit-logs", tags=["audit"])
