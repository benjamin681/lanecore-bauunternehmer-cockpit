"""LaneCore AI — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import health, bauplan


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="LaneCore AI API",
    description="Bauunternehmer-Cockpit — Bauplan-Analyse, Preisvergleich, Angebotserstellung",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(bauplan.router, prefix="/api/v1/bauplan", tags=["bauplan-analyse"])
