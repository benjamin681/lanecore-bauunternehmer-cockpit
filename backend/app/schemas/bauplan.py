"""Pydantic schemas for Bauplan-Analyse API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RaumSchema(BaseModel):
    model_config = {"extra": "ignore"}
    bezeichnung: str
    raum_nr: str | None = None
    flaeche_m2: float | None = None
    breite_m: float | None = None
    tiefe_m: float | None = None
    hoehe_m: float | None = None
    nutzung: str | None = None
    deckentyp: str | None = None


class WandSchema(BaseModel):
    model_config = {"extra": "ignore"}
    id: str
    typ: str  # W112 | W115 | W118 | ...
    laenge_m: float
    hoehe_m: float
    flaeche_m2: float | None = None
    von_raum: str | None = None
    zu_raum: str | None = None
    unsicher: bool = False
    notizen: str | None = None


class DeckeSchema(BaseModel):
    model_config = {"extra": "ignore"}
    raum: str
    raum_nr: str | None = None
    typ: str  # GKb-Abhangdecke glatt | Aquapanel | ...
    system: str | None = None  # D112 | D113 | HKD | ...
    flaeche_m2: float | None = None
    abhaengehoehe_m: float | None = None
    beplankung: str | None = None
    profil: str | None = None
    entfaellt: bool = False


class OeffnungSchema(BaseModel):
    model_config = {"extra": "ignore"}
    typ: str  # Tuer | Fenster
    breite_m: float
    hoehe_m: float
    wand_id: str | None = None


class DetailSchema(BaseModel):
    model_config = {"extra": "ignore"}
    detail_nr: str | None = None
    bezeichnung: str
    massstab: str | None = None
    beschreibung: str | None = None


class GestrichenePositionSchema(BaseModel):
    model_config = {"extra": "ignore"}
    bezeichnung: str
    grund: str
    original_position: str | None = None


class ProjektInfoSchema(BaseModel):
    name: str | None = None
    adresse: str | None = None
    plan_nr: str | None = None
    datum: str | None = None
    revision: str | None = None


class WandSummary(BaseModel):
    """Zusammenfassung Wandflächen nach Typ."""
    W112: float = 0.0
    W115: float = 0.0
    W116: float = 0.0
    W118: float = 0.0
    Unbekannt: float = 0.0


class DeckenSummary(BaseModel):
    """Zusammenfassung Deckenflächen nach System."""
    D112: float = 0.0
    D113: float = 0.0
    HKD: float = 0.0
    Unbekannt: float = 0.0


class AnalyseSummary(BaseModel):
    gesamt_wandflaeche: WandSummary = WandSummary()
    gesamt_deckenflaeche: DeckenSummary = DeckenSummary()
    gesamt_raumflaeche: float = 0.0
    anzahl_raeume: int = 0


# --- API Response Models ---


class AnalyseStatusResponse(BaseModel):
    job_id: UUID
    status: str  # pending | processing | completed | failed
    progress: int = Field(ge=0, le=100)
    filename: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None


class AnalyseResultResponse(BaseModel):
    job_id: UUID
    status: str
    plantyp: str | None = None
    massstab: str | None = None
    geschoss: str | None = None
    projekt: ProjektInfoSchema | None = None
    raeume: list[RaumSchema] = []
    waende: list[WandSchema] = []
    decken: list[DeckeSchema] = []
    oeffnungen: list[OeffnungSchema] = []
    details: list[DetailSchema] = []
    gestrichene_positionen: list[GestrichenePositionSchema] = []
    konfidenz: float = 0.0
    warnungen: list[str] = []
    nicht_lesbar: list[str] = []
    summary: AnalyseSummary = AnalyseSummary()

    # Audit
    model_used: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class AnalyseResultUpdate(BaseModel):
    """Partial update for editable analysis results."""
    raeume: list[RaumSchema] | None = None
    decken: list[DeckeSchema] | None = None
    waende: list[WandSchema] | None = None


class ZusatzkostenPosition(BaseModel):
    bezeichnung: str
    betrag: float = Field(ge=0)


class KalkulationParams(BaseModel):
    """Custom kalkulation parameters for editable Kundenangebot."""
    material_aufschlag_prozent: float | None = None  # e.g. 15 for 15%
    stundensatz_eigen: float | None = None  # EUR/h own employees
    stundensatz_sub: float | None = None  # EUR/h subcontractors
    stunden_pro_m2_decke: float | None = None
    stunden_pro_m2_wand: float | None = None
    anteil_eigenleistung: float | None = None  # 0.0 - 1.0
    zusatzkosten: list[ZusatzkostenPosition] = []
    # Optional: override individual material quantities
    mengen_overrides: dict[str, float] | None = None  # key=bezeichnung, value=new menge
