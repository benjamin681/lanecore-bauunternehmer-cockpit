"""LV-Preisrechner — FastAPI Entry Point."""

# Load .env BEFORE importing settings, sonst wird ANTHROPIC_API_KEY nicht gefunden
from pathlib import Path as _Path
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(_Path(__file__).resolve().parents[1] / ".env", override=False)
except ImportError:
    pass

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import aufmass as aufmass_api
from app.api import auth as auth_api
from app.api import jobs as jobs_api
from app.api import lvs as lvs_api
from app.api import offers as offers_api
from app.api import price_lists as price_lists_api
from app.api import pricing as pricing_api
from app.api import tenant as tenant_api
from app.core.config import settings
from app.core.database import init_db

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    log.info("startup", env=settings.app_env)

    # Safety-Check: kein Default-SECRET in Produktion
    if settings.app_env == "production" and "insecure-change" in settings.secret_key:
        raise RuntimeError(
            "SECRET_KEY ist nicht gesetzt! Bitte ENV SECRET_KEY in Render setzen."
        )

    # Alembic statt init_db — Migrationen laufen im Dockerfile beim Startup
    # init_db nur als Fallback für lokale Entwicklung ohne alembic
    if settings.app_env != "production":
        init_db()

    # Zombie-Jobs aufräumen (überlebte keinen Restart)
    try:
        from app.services.jobs import cleanup_zombie_jobs

        n = cleanup_zombie_jobs(max_age_minutes=15)
        if n:
            log.info("zombies_cleaned", count=n)
    except Exception as e:  # noqa: BLE001
        log.warning("zombie_cleanup_failed", error=str(e))

    yield
    log.info("shutdown")


app = FastAPI(
    title="LV-Preisrechner API",
    description="Upload LV → DNA-Matching gegen Kunden-Preisliste → ausgefülltes PDF",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "lv-preisrechner", "version": "0.1.0"}


@app.get("/api/v1/debug/db")
def debug_db() -> dict:
    """Zeigt Datenbank-Info (ohne Passwort) — hilft beim Debuggen von ENV-Issues."""
    url = settings.database_url
    # Passwort maskieren
    import re

    masked = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)
    return {
        "database_url": masked,
        "backend": "postgresql" if not settings.is_sqlite else "sqlite",
        "anthropic_configured": bool(settings.anthropic_api_key),
        "app_env": settings.app_env,
    }


app.include_router(auth_api.router, prefix="/api/v1")
app.include_router(price_lists_api.router, prefix="/api/v1")
app.include_router(lvs_api.router, prefix="/api/v1")
app.include_router(jobs_api.router, prefix="/api/v1")
# Neue Pricing-API (B+1, parallel zum alten price_lists_api)
app.include_router(pricing_api.router, prefix="/api/v1")
# B+4.9: Vertriebs-Workflow — Tenant-Profil + Customers + Projects.
app.include_router(tenant_api.router, prefix="/api/v1")
app.include_router(tenant_api.customer_router, prefix="/api/v1")
app.include_router(tenant_api.project_router, prefix="/api/v1")
# B+4.11: Offer-Lifecycle.
app.include_router(offers_api.lv_offers_router, prefix="/api/v1")
app.include_router(offers_api.offers_router, prefix="/api/v1")
# B+4.12: Aufmaß und Final-Kalkulation.
app.include_router(aufmass_api.offer_aufmass_router, prefix="/api/v1")
app.include_router(aufmass_api.aufmasse_router, prefix="/api/v1")
