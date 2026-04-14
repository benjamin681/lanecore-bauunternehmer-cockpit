"""Bauplan-Analyse Endpoints — Säule 1."""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class AnalyseStatus(BaseModel):
    job_id: str
    status: str  # "pending" | "processing" | "completed" | "failed"
    progress: int  # 0–100


class AnalyseResult(BaseModel):
    job_id: str
    status: str
    raeume: list[dict]        # Erkannte Räume mit Flächen
    wandlaengen: dict         # Wandlängen nach Wandtyp (W112, W115, ...)
    deckenmassen: dict        # Deckenflächen, Deckenhöhen
    massstab: str             # Erkannter Maßstab (z.B. "1:100")
    konfidenz: float          # 0.0–1.0 — wie sicher ist die KI
    warnungen: list[str]      # Unsicherheiten, die manuell geprüft werden sollten


@router.post("/upload", response_model=AnalyseStatus)
async def upload_bauplan(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """PDF-Bauplan hochladen und Analyse starten."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Nur PDF-Dateien werden akzeptiert.")

    # TODO: Sprint 1 — S3-Upload, Job-Queue, Analyse-Pipeline
    job_id = "placeholder-job-id"
    return AnalyseStatus(job_id=job_id, status="pending", progress=0)


@router.get("/{job_id}/status", response_model=AnalyseStatus)
async def get_analyse_status(job_id: str):
    """Analyse-Status abfragen (Polling)."""
    # TODO: Sprint 1 — Aus DB laden
    return AnalyseStatus(job_id=job_id, status="pending", progress=0)


@router.get("/{job_id}/result", response_model=AnalyseResult)
async def get_analyse_result(job_id: str):
    """Fertige Analyse-Ergebnisse abrufen."""
    # TODO: Sprint 2 — Aus DB laden
    raise HTTPException(status_code=404, detail="Analyse-Ergebnis nicht gefunden.")
