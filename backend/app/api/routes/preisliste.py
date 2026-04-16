"""Preislisten-Management Endpoints — Säule 2."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.exceptions import JobNotFoundError, PDFValidationError
from app.models.preisliste import Preisliste, Produkt
from app.schemas.preisliste import (
    PreislisteUploadResponse,
    PreislisteDetailResponse,
    PreislisteListResponse,
    PreisvergleichResponse,
    PreisvergleichResult,
    ProduktSchema,
)
from app.services.preisliste_service import PreislisteService

router = APIRouter()


@router.post("/upload", status_code=202)
async def upload_preisliste(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    anbieter: str = Form(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PreislisteUploadResponse:
    """Preislisten-PDF hochladen und Extraktion starten.

    Args:
        file: PDF-Datei mit Preisliste
        anbieter: Name des Anbieters (z.B. "KEMLER", "Saint-Gobain", "Knauf")
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise PDFValidationError("Nur PDF-Dateien werden akzeptiert.")

    pdf_bytes = await file.read()

    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > 50:
        raise PDFValidationError(f"Datei zu groß: {size_mb:.1f}MB (Max: 50MB)")

    preisliste = Preisliste(
        anbieter=anbieter.strip(),
        quelle="pdf_upload",
        dateiname=file.filename,
        status="pending",
    )
    db.add(preisliste)
    await db.commit()
    await db.refresh(preisliste)

    # Start extraction in background
    service = PreislisteService()
    background_tasks.add_task(service.process_preisliste_pdf, preisliste.id, pdf_bytes, anbieter)

    return PreislisteUploadResponse(
        id=preisliste.id,
        anbieter=preisliste.anbieter,
        quelle=preisliste.quelle,
        status=preisliste.status,
        dateiname=preisliste.dateiname,
        created_at=preisliste.created_at,
    )


@router.get("/", response_model=list[PreislisteListResponse])
async def list_preislisten(
    db: AsyncSession = Depends(get_db),
) -> list[PreislisteListResponse]:
    """Alle hochgeladenen Preislisten auflisten."""
    result = await db.execute(
        select(Preisliste).order_by(Preisliste.created_at.desc())
    )
    preislisten = result.scalars().all()

    return [
        PreislisteListResponse(
            id=p.id,
            anbieter=p.anbieter,
            quelle=p.quelle,
            status=p.status,
            dateiname=p.dateiname,
            produkt_count=p.produkt_count,
            created_at=p.created_at,
        )
        for p in preislisten
    ]


@router.get("/{preisliste_id}")
async def get_preisliste_detail(
    preisliste_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PreislisteDetailResponse:
    """Preisliste mit allen Produkten abrufen."""
    result = await db.execute(
        select(Preisliste)
        .options(selectinload(Preisliste.produkte))
        .where(Preisliste.id == preisliste_id)
    )
    preisliste = result.scalar_one_or_none()

    if not preisliste:
        raise JobNotFoundError(str(preisliste_id))

    return PreislisteDetailResponse(
        id=preisliste.id,
        anbieter=preisliste.anbieter,
        quelle=preisliste.quelle,
        status=preisliste.status,
        dateiname=preisliste.dateiname,
        error_message=preisliste.error_message,
        produkt_count=preisliste.produkt_count,
        produkte=[
            ProduktSchema(
                id=p.id,
                artikel_nr=p.artikel_nr,
                bezeichnung=p.bezeichnung,
                hersteller=p.hersteller,
                kategorie=p.kategorie,
                einheit=p.einheit,
                preis_netto=float(p.preis_netto),
                preis_brutto=float(p.preis_brutto) if p.preis_brutto else None,
                menge_pro_einheit=float(p.menge_pro_einheit) if p.menge_pro_einheit else None,
                verfuegbar=p.verfuegbar,
            )
            for p in preisliste.produkte
        ],
        created_at=preisliste.created_at,
    )


@router.post("/{preisliste_id}/retry")
async def retry_preisliste(
    preisliste_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Fehlgeschlagene Preisliste erneut verarbeiten."""
    result = await db.execute(
        select(Preisliste).where(Preisliste.id == preisliste_id)
    )
    preisliste = result.scalar_one_or_none()
    if not preisliste:
        raise JobNotFoundError(str(preisliste_id))
    if preisliste.status != "failed":
        return {"error": "Nur fehlgeschlagene Preislisten können erneut verarbeitet werden"}

    # Read PDF from disk
    import glob
    pdf_path = None
    for p in glob.glob(f"/tmp/lanecore-uploads/preislisten/{preisliste_id}/*") + \
             glob.glob(f"/tmp/lanecore-uploads/*/{preisliste_id}/*"):
        if p.endswith(".pdf"):
            pdf_path = p
            break

    if not pdf_path:
        return {"error": "PDF-Datei nicht mehr vorhanden. Bitte erneut hochladen."}

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # Reset status
    preisliste.status = "pending"
    preisliste.error_message = None
    preisliste.produkt_count = 0
    await db.commit()

    service = PreislisteService()
    background_tasks.add_task(service.process_preisliste_pdf, preisliste.id, pdf_bytes, preisliste.anbieter)

    return {"status": "retry_started", "id": str(preisliste_id)}


@router.delete("/{preisliste_id}", status_code=204)
async def delete_preisliste(
    preisliste_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Preisliste und alle zugehörigen Produkte löschen."""
    result = await db.execute(
        select(Preisliste).where(Preisliste.id == preisliste_id)
    )
    preisliste = result.scalar_one_or_none()

    if not preisliste:
        raise JobNotFoundError(str(preisliste_id))

    await db.delete(preisliste)
    await db.commit()


@router.get("/lieferanten")
async def list_lieferanten():
    """List all available supplier sources (PDF imports + API connections)."""
    return {
        "pdf_imports": "active",  # Always available
        "api_connections": [
            {"name": "KEMLER Baustoffe", "status": "coming_soon", "type": "api"},
            {"name": "Saint-Gobain", "status": "coming_soon", "type": "api"},
            {"name": "Knauf", "status": "coming_soon", "type": "api"},
        ],
        "hinweis": "Preislisten können als PDF hochgeladen werden. API-Anbindungen an Lieferanten folgen in v2."
    }


@router.get("/vergleich/suche")
async def preisvergleich(
    q: str = Query(..., description="Produktbezeichnung suchen"),
    kategorie: str | None = Query(None, description="Kategorie-Filter"),
    db: AsyncSession = Depends(get_db),
) -> PreisvergleichResponse:
    """Preisvergleich über alle Anbieter für ein bestimmtes Produkt."""
    service = PreislisteService()
    results = await service.preisvergleich(q, kategorie)

    guenstigster = results[0]["anbieter"] if results else None
    if len(results) >= 2:
        min_price = results[0]["produkt"]["preis_netto"]
        max_price = results[-1]["produkt"]["preis_netto"]
        diff_pct = ((max_price - min_price) / min_price * 100) if min_price > 0 else 0
    else:
        diff_pct = None

    return PreisvergleichResponse(
        suche=q,
        ergebnisse=[
            PreisvergleichResult(
                anbieter=r["anbieter"],
                produkt=ProduktSchema(**r["produkt"]),
                gesamtpreis=r["produkt"]["preis_netto"],
                ist_guenstigster=r["ist_guenstigster"],
            )
            for r in results
        ],
        guenstigster_anbieter=guenstigster,
        preisdifferenz_prozent=round(diff_pct, 1) if diff_pct else None,
    )
