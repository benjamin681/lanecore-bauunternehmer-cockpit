"""LaneCore AI — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import LaneCoreError, lanecore_exception_handler
from app.api.routes import health, bauplan, projekte, stats


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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(bauplan.router, prefix="/api/v1/bauplan", tags=["bauplan-analyse"])
app.include_router(projekte.router, prefix="/api/v1/projekte", tags=["projekte"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["statistics"])
