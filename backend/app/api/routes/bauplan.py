"""Bauplan-Analyse Endpoints — Säule 1."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.exceptions import JobNotFoundError, PDFValidationError
from app.models.analyse_job import AnalyseJob
from app.models.analyse_ergebnis import AnalyseErgebnis
from app.schemas.bauplan import (
    AnalyseResultResponse,
    AnalyseResultUpdate,
    AnalyseStatusResponse,
    AnalyseSummary,
    DeckeSchema,
    DeckenSummary,
    DetailSchema,
    GestrichenePositionSchema,
    KalkulationParams,
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


@router.get("/{job_id}/stream")
async def stream_analyse_status(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """SSE endpoint for live analysis progress."""
    import asyncio
    import json

    async def event_generator():
        last_status = None
        while True:
            # Fresh session for each poll
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(AnalyseJob).where(AnalyseJob.id == job_id))
                job = result.scalar_one_or_none()
                if not job:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    return

                current = f"{job.status}:{job.progress}"
                if current != last_status:
                    last_status = current
                    yield f"data: {json.dumps({'status': job.status, 'progress': job.progress, 'error_message': job.error_message})}\n\n"

                if job.status in ("completed", "failed"):
                    return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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


@router.patch("/{job_id}/result")
async def patch_analyse_result(
    job_id: UUID,
    update: AnalyseResultUpdate,
    db: AsyncSession = Depends(get_db),
) -> AnalyseResultResponse:
    """Analyse-Ergebnis teilweise aktualisieren (Raeume/Decken/Waende).

    Erlaubt dem Nutzer, von Claude erkannte Werte manuell zu korrigieren.
    Gibt das aktualisierte Ergebnis zurueck.
    """
    result = await db.execute(
        select(AnalyseJob)
        .options(selectinload(AnalyseJob.ergebnis))
        .where(AnalyseJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job or job.status != "completed" or not job.ergebnis:
        raise JobNotFoundError(str(job_id))

    erg = job.ergebnis

    # Apply partial updates to JSONB columns
    if update.raeume is not None:
        erg.raeume = [r.model_dump() for r in update.raeume]
    if update.decken is not None:
        erg.decken = [d.model_dump() for d in update.decken]
    if update.waende is not None:
        erg.waende = [w.model_dump() for w in update.waende]

    await db.commit()
    await db.refresh(erg)

    # Return updated result (reuse the GET logic)
    return await get_analyse_result(job_id, db)


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
        "oeffnungen": erg.oeffnungen or [],
        "details": erg.details or [],
    }

    kalkulation = await erstelle_kalkulation(analyse_data, db)
    kalkulation["job_id"] = str(job_id)
    kalkulation["filename"] = job.filename
    kalkulation["plantyp"] = erg.plantyp
    kalkulation["geschoss"] = erg.geschoss

    return kalkulation


@router.get("/{job_id}/angebot-pdf")
async def get_angebot_pdf(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    # Optional kalkulation overrides as query params
    material_aufschlag_prozent: float | None = None,
    stundensatz_eigen: float | None = None,
    stundensatz_sub: float | None = None,
    stunden_pro_m2_decke: float | None = None,
    stunden_pro_m2_wand: float | None = None,
    anteil_eigenleistung: float | None = None,
) -> StreamingResponse:
    """Kundenangebot als professionelles PDF herunterladen.

    Generiert ein 2-seitiges PDF:
      - Seite 1: Kundenangebot mit LV-Positionen und Bruttosumme
      - Seite 2: Bestellliste (intern, nach Lieferant gruppiert)

    Akzeptiert optionale Query-Parameter für benutzerdefinierte Kalkulation.
    """
    import io

    from app.services.kalkulation_service import erstelle_kalkulation
    from app.services.pdf_angebot import generate_angebot_pdf

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
        "oeffnungen": erg.oeffnungen or [],
        "details": erg.details or [],
    }

    # Build custom params from query parameters
    custom_params: dict = {}
    if material_aufschlag_prozent is not None:
        custom_params["material_aufschlag_prozent"] = material_aufschlag_prozent
    if stundensatz_eigen is not None:
        custom_params["stundensatz_eigen"] = stundensatz_eigen
    if stundensatz_sub is not None:
        custom_params["stundensatz_sub"] = stundensatz_sub
    if stunden_pro_m2_decke is not None:
        custom_params["stunden_pro_m2_decke"] = stunden_pro_m2_decke
    if stunden_pro_m2_wand is not None:
        custom_params["stunden_pro_m2_wand"] = stunden_pro_m2_wand
    if anteil_eigenleistung is not None:
        custom_params["anteil_eigenleistung"] = anteil_eigenleistung

    kalkulation = await erstelle_kalkulation(
        analyse_data, db, custom_params=custom_params if custom_params else None
    )
    kalkulation["job_id"] = str(job_id)
    kalkulation["filename"] = job.filename
    kalkulation["plantyp"] = erg.plantyp
    kalkulation["geschoss"] = erg.geschoss

    pdf_bytes = generate_angebot_pdf(kalkulation, filename=job.filename)

    safe_name = job.filename.replace(".pdf", "").replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Angebot_{safe_name}.pdf"'
        },
    )


@router.post("/{job_id}/kalkulation")
async def post_kalkulation(
    job_id: UUID,
    params: KalkulationParams,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Kalkulation mit benutzerdefinierten Parametern neu berechnen.

    Akzeptiert optionale Overrides fuer Material-Aufschlag, Stundensaetze,
    Stunden/m2, Anteil Eigenleistung, Zusatzkosten und Mengen-Overrides.
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
        "oeffnungen": erg.oeffnungen or [],
        "details": erg.details or [],
    }

    # Convert params to dict, excluding None values
    custom_params = params.model_dump(exclude_none=True)
    # Convert zusatzkosten list of models to list of dicts
    if "zusatzkosten" in custom_params:
        custom_params["zusatzkosten"] = [
            {"bezeichnung": z.bezeichnung, "betrag": z.betrag}
            for z in params.zusatzkosten
        ]

    kalkulation = await erstelle_kalkulation(analyse_data, db, custom_params=custom_params)
    kalkulation["job_id"] = str(job_id)
    kalkulation["filename"] = job.filename
    kalkulation["plantyp"] = erg.plantyp
    kalkulation["geschoss"] = erg.geschoss

    return kalkulation
