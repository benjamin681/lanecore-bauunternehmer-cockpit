"""Bauplan-Analyse Endpoints — Säule 1."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import JobNotFoundError, PDFValidationError
from app.models.analyse_job import AnalyseJob
from app.models.analyse_ergebnis import AnalyseErgebnis
from app.schemas.bauplan import (
    AnalyseResultResponse,
    AnalyseStatusResponse,
    AnalyseSummary,
    DeckeSchema,
    DeckenSummary,
    DetailSchema,
    GestrichenePositionSchema,
    OeffnungSchema,
    ProjektInfoSchema,
    RaumSchema,
    WandSchema,
    WandSummary,
)
from app.services.analyse_pipeline import run_analyse_pipeline

router = APIRouter()


@router.post("/upload", status_code=202)
async def upload_bauplan(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AnalyseStatusResponse:
    """PDF-Bauplan hochladen und Analyse starten."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise PDFValidationError("Nur PDF-Dateien werden akzeptiert.")

    # Read file content
    pdf_bytes = await file.read()

    # Validate size (quick check before expensive operations)
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > settings.max_pdf_size_mb:
        raise PDFValidationError(f"Datei zu groß: {size_mb:.1f}MB (Max: {settings.max_pdf_size_mb}MB)")

    # Create job record in DB
    job = AnalyseJob(
        projekt_id=None,  # TODO: verknüpfe mit Projekt wenn angegeben
        filename=file.filename,
        s3_key="pending",  # wird in Pipeline gesetzt
        status="pending",
        progress=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Start analysis pipeline in background
    background_tasks.add_task(run_analyse_pipeline, job.id, pdf_bytes, file.filename)

    return AnalyseStatusResponse(
        job_id=job.id,
        status="pending",
        progress=0,
        filename=file.filename,
    )


@router.get("/{job_id}/status")
async def get_analyse_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AnalyseStatusResponse:
    """Analyse-Status abfragen (Polling)."""
    result = await db.execute(select(AnalyseJob).where(AnalyseJob.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise JobNotFoundError(str(job_id))

    return AnalyseStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        filename=job.filename,
        error_message=job.error_message,
        created_at=job.created_at,
    )


@router.get("/{job_id}/result")
async def get_analyse_result(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AnalyseResultResponse:
    """Fertige Analyse-Ergebnisse abrufen."""
    result = await db.execute(
        select(AnalyseJob)
        .options(selectinload(AnalyseJob.ergebnis))
        .where(AnalyseJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise JobNotFoundError(str(job_id))

    if job.status != "completed" or not job.ergebnis:
        raise JobNotFoundError(str(job_id))

    erg = job.ergebnis

    # Build response from JSONB data
    raeume = [RaumSchema(**r) for r in (erg.raeume or [])]
    waende = [WandSchema(**w) for w in (erg.waende or [])]
    decken = [DeckeSchema(**d) for d in (erg.decken or [])]
    oeffnungen = [OeffnungSchema(**o) for o in (erg.oeffnungen or [])]
    details = [DetailSchema(**d) for d in (erg.details or [])]
    gestrichene = [GestrichenePositionSchema(**g) for g in (erg.gestrichene_positionen or [])]
    warnungen = erg.warnungen or []

    # Build summary
    wand_summary = WandSummary()
    for w in waende:
        flaeche = w.flaeche_m2 or (w.laenge_m * w.hoehe_m)
        current = getattr(wand_summary, w.typ, None)
        if current is not None:
            setattr(wand_summary, w.typ, current + flaeche)
        else:
            wand_summary.Unbekannt += flaeche

    decken_summary = DeckenSummary()
    for d in decken:
        if not d.entfaellt:
            sys = d.system or "Unbekannt"
            current = getattr(decken_summary, sys, None)
            if current is not None:
                setattr(decken_summary, sys, current + d.flaeche_m2)
            else:
                decken_summary.Unbekannt += d.flaeche_m2

    return AnalyseResultResponse(
        job_id=job.id,
        status=job.status,
        plantyp=erg.plantyp,
        massstab=erg.massstab,
        geschoss=erg.geschoss,
        raeume=raeume,
        waende=waende,
        decken=decken,
        oeffnungen=oeffnungen,
        details=details,
        gestrichene_positionen=gestrichene,
        konfidenz=float(erg.konfidenz) if erg.konfidenz else 0.0,
        warnungen=warnungen,
        summary=AnalyseSummary(
            gesamt_wandflaeche=wand_summary,
            gesamt_deckenflaeche=decken_summary,
            gesamt_raumflaeche=sum(r.flaeche_m2 for r in raeume),
            anzahl_raeume=len(raeume),
        ),
        model_used=job.model_used,
        input_tokens=job.input_tokens,
        output_tokens=job.output_tokens,
        cost_usd=float(job.cost_usd) if job.cost_usd else None,
    )
