"""Pydantic schemas for Projekt API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjektCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    auftraggeber: str | None = Field(None, max_length=255)
    beschreibung: str | None = Field(None, max_length=2000)


class ProjektUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    auftraggeber: str | None = Field(None, max_length=255)
    beschreibung: str | None = Field(None, max_length=2000)


class ProjektResponse(BaseModel):
    id: UUID
    name: str
    auftraggeber: str | None = None
    beschreibung: str | None = None
    created_at: datetime
    updated_at: datetime
    analyse_count: int = 0

    model_config = {"from_attributes": True}
