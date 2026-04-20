"""Pydantic schemas for Preislisten-API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProduktSchema(BaseModel):
    id: UUID
    artikel_nr: str | None = None
    bezeichnung: str
    hersteller: str | None = None
    kategorie: str | None = None
    einheit: str
    preis_netto: float
    preis_brutto: float | None = None
    menge_pro_einheit: float | None = None
    verfuegbar: bool = True


class PreislisteUploadResponse(BaseModel):
    id: UUID
    anbieter: str
    quelle: str
    status: str
    dateiname: str | None = None
    created_at: datetime | None = None


class PreislisteDetailResponse(BaseModel):
    id: UUID
    anbieter: str
    quelle: str
    status: str
    dateiname: str | None = None
    error_message: str | None = None
    produkt_count: int = 0
    produkte: list[ProduktSchema] = []
    created_at: datetime | None = None


class PreislisteListResponse(BaseModel):
    id: UUID
    anbieter: str
    quelle: str
    status: str
    dateiname: str | None = None
    produkt_count: int = 0
    created_at: datetime | None = None


class PreisvergleichRequest(BaseModel):
    """Anfrage für Preisvergleich eines bestimmten Produkts."""
    bezeichnung: str
    kategorie: str | None = None
    menge: float = 1.0
    einheit: str | None = None


class PreisvergleichResult(BaseModel):
    """Ein Anbieter-Preis für ein bestimmtes Produkt."""
    anbieter: str
    produkt: ProduktSchema
    gesamtpreis: float
    ist_guenstigster: bool = False


class PreisvergleichResponse(BaseModel):
    """Preisvergleich-Ergebnis über alle Anbieter."""
    suche: str
    ergebnisse: list[PreisvergleichResult] = []
    guenstigster_anbieter: str | None = None
    preisdifferenz_prozent: float | None = None
