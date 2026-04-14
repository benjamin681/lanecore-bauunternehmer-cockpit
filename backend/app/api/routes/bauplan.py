"""Bauplan-Analyse Endpoints — Säule 1."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
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
    projekt_id: UUID | None = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AnalyseStatusResponse:
    """PDF-Bauplan hochladen und Analyse starten.

    Optional: projekt_id als Query-Parameter um den Upload einem Projekt zuzuordnen.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise PDFValidationError("Nur PDF-Dateien werden akzeptiert.")

    pdf_bytes = await file.read()

    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > settings.max_pdf_size_mb:
        raise PDFValidationError(f"Datei zu groß: {size_mb:.1f}MB (Max: {settings.max_pdf_size_mb}MB)")

    # Verify projekt exists if provided
    if projekt_id:
        result = await db.execute(
            select(AnalyseJob).where(False)  # Just check the table works
        )
        from app.models.projekt import Projekt
        proj_result = await db.execute(
            select(Projekt).where(Projekt.id == projekt_id, Projekt.user_id == user_id)
        )
        if not proj_result.scalar_one_or_none():
            raise JobNotFoundError(str(projekt_id))

    job = AnalyseJob(
        projekt_id=projekt_id,
        filename=file.filename,
        s3_key="pending",
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

    # Build summary (handle None values)
    wand_summary = WandSummary()
    for w in waende:
        flaeche = w.flaeche_m2 or ((w.laenge_m or 0) * (w.hoehe_m or 0))
        if flaeche:
            current = getattr(wand_summary, w.typ, None)
            if current is not None:
                setattr(wand_summary, w.typ, current + flaeche)
            else:
                wand_summary.Unbekannt += flaeche

    decken_summary = DeckenSummary()
    for d in decken:
        if not d.entfaellt and d.flaeche_m2:
            sys_name = d.system or "Unbekannt"
            current = getattr(decken_summary, sys_name, None)
            if current is not None:
                setattr(decken_summary, sys_name, current + d.flaeche_m2)
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
            gesamt_raumflaeche=sum(r.flaeche_m2 or 0 for r in raeume),
            anzahl_raeume=len(raeume),
        ),
        model_used=job.model_used,
        input_tokens=job.input_tokens,
        output_tokens=job.output_tokens,
        cost_usd=float(job.cost_usd) if job.cost_usd else None,
    )


@router.get("/{job_id}/export")
async def export_analyse_excel(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Analyse-Ergebnis als Excel (.xlsx) herunterladen."""
    from app.services.excel_export import generate_excel
    import io

    result = await db.execute(
        select(AnalyseJob)
        .options(selectinload(AnalyseJob.ergebnis))
        .where(AnalyseJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job or job.status != "completed" or not job.ergebnis:
        raise JobNotFoundError(str(job_id))

    erg = job.ergebnis

    # Build result dict for excel export
    export_data = {
        "plantyp": erg.plantyp,
        "massstab": erg.massstab,
        "geschoss": erg.geschoss,
        "konfidenz": float(erg.konfidenz) if erg.konfidenz else 0.0,
        "raeume": erg.raeume or [],
        "waende": erg.waende or [],
        "decken": erg.decken or [],
        "warnungen": erg.warnungen or [],
        "summary": {
            "anzahl_raeume": len(erg.raeume or []),
            "gesamt_raumflaeche": sum(
                (r.get("flaeche_m2") or 0) for r in (erg.raeume or [])
            ),
        },
    }

    xlsx_bytes = generate_excel(export_data, filename=job.filename)

    safe_name = job.filename.replace(".pdf", "").replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="Massenermittlung_{safe_name}.xlsx"'
        },
    )


@router.get("/{job_id}/kalkulation")
async def get_kalkulation(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Automatische Kalkulation: Materialliste + günstigste Preise aus allen Preislisten.

    Flow: Analyse-Ergebnis → Materialien ableiten → gegen alle Preislisten matchen.
    """
    from app.services.kalkulation_service import erstelle_kalkulation

    result = await db.execute(
        select(AnalyseJob)
        .options(selectinload(AnalyseJob.ergebnis))
        .where(AnalyseJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job or job.status != "completed" or not job.ergebnis:
        raise JobNotFoundError(str(job_id))

    erg = job.ergebnis

    analyse_data = {
        "raeume": erg.raeume or [],
        "waende": erg.waende or [],
        "decken": erg.decken or [],
        "details": erg.details or [],
    }

    kalkulation = await erstelle_kalkulation(analyse_data, db)
    kalkulation["job_id"] = str(job_id)
    kalkulation["filename"] = job.filename
    kalkulation["plantyp"] = erg.plantyp
    kalkulation["geschoss"] = erg.geschoss

    return kalkulation
