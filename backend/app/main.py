"""LaneCore AI — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import LaneCoreError, lanecore_exception_handler
from app.api.routes import health, bauplan, projekte, stats, preisliste


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
)

# Exception handlers
app.add_exception_handler(LaneCoreError, lanecore_exception_handler)  # type: ignore[arg-type]


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return traceback in response so we can debug production errors."""
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": "".join(tb[-5:])},
    )

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
