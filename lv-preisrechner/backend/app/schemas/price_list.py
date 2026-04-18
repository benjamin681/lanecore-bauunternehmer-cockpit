"""Preislisten-Schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PriceEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    art_nr: str
    dna: str
    hersteller: str
    kategorie: str
    produktname: str
    abmessungen: str
    variante: str
    preis: float
    einheit: str
    preis_pro_basis: float
    basis_einheit: str
    konfidenz: float
    manuell_korrigiert: bool


class PriceEntryUpdate(BaseModel):
    hersteller: str | None = None
    kategorie: str | None = None
    produktname: str | None = None
    abmessungen: str | None = None
    variante: str | None = None
    preis: float | None = None
    einheit: str | None = None


class PriceListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    haendler: str
    niederlassung: str
    stand_monat: str
    original_dateiname: str
    status: str
    aktiv: bool
    eintraege_gesamt: int
    eintraege_unsicher: int
    created_at: datetime


class PriceListDetail(PriceListOut):
    entries: list[PriceEntryOut]


class PriceListMeta(BaseModel):
    """Metadata beim Upload."""

    haendler: str
    niederlassung: str = ""
    stand_monat: str = ""
