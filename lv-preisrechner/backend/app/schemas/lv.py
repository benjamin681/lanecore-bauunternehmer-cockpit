"""LV- und Position-Schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reihenfolge: int
    oz: str
    titel: str
    kurztext: str
    menge: float
    einheit: str
    erkanntes_system: str
    feuerwiderstand: str
    plattentyp: str
    materialien: list
    material_ep: float
    lohn_stunden: float
    lohn_ep: float
    zuschlaege_ep: float
    ep: float
    gp: float
    konfidenz: float
    manuell_korrigiert: bool
    warnung: str

    # B+4.2: Preis-Herkunft (aggregiert pro Position). Details stecken im
    # `materialien`-JSON pro Material-Item.
    needs_price_review: bool = False
    price_source_summary: str = ""


class PositionUpdate(BaseModel):
    menge: float | None = None
    einheit: str | None = None
    kurztext: str | None = None
    erkanntes_system: str | None = None
    ep: float | None = None


class LVOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    projekt_name: str
    auftraggeber: str
    original_dateiname: str
    status: str
    positionen_gesamt: int
    positionen_gematcht: int
    positionen_unsicher: int
    angebotssumme_netto: float
    created_at: datetime
    updated_at: datetime


class LVDetail(LVOut):
    positions: list[PositionOut]
