"""Pydantic schemas for Projekt API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjektCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    auftraggeber: str | None = Field(None, max_length=255)
    adresse: str | None = Field(None, max_length=500)
    beschreibung: str | None = Field(None, max_length=2000)


class ProjektUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    auftraggeber: str | None = Field(None, max_length=255)
    adresse: str | None = Field(None, max_length=500)
    status: str | None = Field(None, max_length=50)
    beschreibung: str | None = Field(None, max_length=2000)


class AnalyseJobBrief(BaseModel):
    id: UUID
    filename: str | None = None
    status: str
    progress: int = 0
    plantyp: str | None = None
    created_at: datetime | None = None


class ProjektResponse(BaseModel):
    id: UUID
    name: str
    auftraggeber: str | None = None
    bauherr: str | None = None
    architekt: str | None = None
    adresse: str | None = None
    plan_nr: str | None = None
    status: str = "aktiv"
    beschreibung: str | None = None
    created_at: datetime
    updated_at: datetime
    analyse_count: int = 0
    analysen: list[AnalyseJobBrief] = []

    model_config = {"from_attributes": True}
