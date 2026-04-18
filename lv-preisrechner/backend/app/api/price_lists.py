"""Preislisten-API: Upload, List, Detail, Review/Update, Activate, Delete."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models.price_entry import PriceEntry
from app.models.price_list import PriceList
from app.schemas.job import JobOut
from app.schemas.price_list import (
    PriceEntryOut,
    PriceEntryUpdate,
    PriceListDetail,
    PriceListOut,
)
from app.services.jobs import enqueue_job, run_parse_price_list
from app.services.pdf_utils import compute_sha256, save_upload
from app.services.price_list_parser import activate, build_dna, parse_and_store

router = APIRouter(prefix="/price-lists", tags=["price-lists"])


@router.post("/upload-async", response_model=JobOut, status_code=202)
async def upload_price_list_async(
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    haendler: str = Form(...),
    niederlassung: str = Form(""),
    stand_monat: str = Form(""),
) -> JobOut:
    """Async-Upload: liefert sofort Job-ID zurück. Client pollt /jobs/{id}."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nur PDF-Dateien unterstützt")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF > 50 MB nicht erlaubt")

    sha = compute_sha256(pdf_bytes)

    # PDF in DB speichern (persistent, ueberlebt Render-Redeploys)
    pl = PriceList(
        tenant_id=user.tenant_id,
        haendler=haendler,
        niederlassung=niederlassung,
        stand_monat=stand_monat,
        original_dateiname=file.filename,
        original_pdf_sha256=sha,
        original_pdf_bytes=pdf_bytes,
        status="queued",
    )
    db.add(pl)
    db.flush()

    job = enqueue_job(
        db,
        tenant_id=user.tenant_id,
        kind="parse_price_list",
        target_id=pl.id,
        target_kind="price_list",
    )

    # Background-Task liest pdf_bytes aus DB (nicht mehr im Parameter halten)
    background_tasks.add_task(
        run_parse_price_list,
        job_id=job.id,
        tenant_id=user.tenant_id,
        price_list_id=pl.id,
    )
    return JobOut.model_validate(job)


@router.post("/{price_list_id}/retry-parse", response_model=JobOut, status_code=202)
def retry_parse_price_list(
    price_list_id: str,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> JobOut:
    """Neustart des Parse-Jobs für eine Preisliste, die in 'queued' oder 'error' hängt."""
    from app.models.job import Job
    from app.services.jobs import enqueue_job, run_parse_price_list

    pl = (
        db.query(PriceList)
        .filter(PriceList.id == price_list_id, PriceList.tenant_id == user.tenant_id)
        .first()
    )
    if not pl:
        raise HTTPException(status_code=404, detail="Preisliste nicht gefunden")
    if not pl.original_pdf_bytes:
        raise HTTPException(
            status_code=400,
            detail="Kein Original-PDF mehr vorhanden — bitte neu hochladen",
        )

    # Nicht retry'en wenn schon ein Job aktiv ist
    active = (
        db.query(Job)
        .filter(
            Job.target_id == pl.id,
            Job.target_kind == "price_list",
            Job.status.in_(["queued", "running"]),
        )
        .first()
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"Job läuft bereits ({active.status}), bitte warten",
        )

    # Alte Einträge löschen
    db.query(PriceEntry).filter(PriceEntry.price_list_id == pl.id).delete()
    pl.status = "queued"
    pl.eintraege_gesamt = 0
    pl.eintraege_unsicher = 0
    db.commit()

    job = enqueue_job(
        db, tenant_id=user.tenant_id, kind="parse_price_list",
        target_id=pl.id, target_kind="price_list",
    )
    background_tasks.add_task(
        run_parse_price_list,
        job_id=job.id,
        tenant_id=user.tenant_id,
        price_list_id=pl.id,
    )
    return JobOut.model_validate(job)


@router.post("/upload", response_model=PriceListDetail, status_code=201)
async def upload_price_list(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    haendler: str = Form(...),
    niederlassung: str = Form(""),
    stand_monat: str = Form(""),
) -> PriceListDetail:
    """Preisliste hochladen. Claude Vision parst sie in Produkt-DNA-Einträge."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nur PDF-Dateien unterstützt")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF > 50 MB nicht erlaubt")

    pl = parse_and_store(
        db=db,
        tenant_id=user.tenant_id,
        pdf_bytes=pdf_bytes,
        original_dateiname=file.filename,
        haendler=haendler,
        niederlassung=niederlassung,
        stand_monat=stand_monat,
    )
    return PriceListDetail.model_validate(
        {**PriceListOut.model_validate(pl).model_dump(), "entries": pl.entries}
    )


@router.get("", response_model=list[PriceListOut])
def list_price_lists(user: CurrentUser, db: DbSession) -> list[PriceListOut]:
    rows = (
        db.query(PriceList)
        .filter(PriceList.tenant_id == user.tenant_id)
        .order_by(PriceList.created_at.desc())
        .all()
    )
    return [PriceListOut.model_validate(r) for r in rows]


@router.get("/{price_list_id}", response_model=PriceListDetail)
def get_price_list(price_list_id: str, user: CurrentUser, db: DbSession) -> PriceListDetail:
    pl = (
        db.query(PriceList)
        .filter(PriceList.id == price_list_id, PriceList.tenant_id == user.tenant_id)
        .first()
    )
    if not pl:
        raise HTTPException(status_code=404, detail="Preisliste nicht gefunden")
    return PriceListDetail.model_validate(
        {
            **PriceListOut.model_validate(pl).model_dump(),
            "entries": [PriceEntryOut.model_validate(e) for e in pl.entries],
        }
    )


@router.patch("/{price_list_id}/entries/{entry_id}", response_model=PriceEntryOut)
def update_entry(
    price_list_id: str,
    entry_id: str,
    update: PriceEntryUpdate,
    user: CurrentUser,
    db: DbSession,
) -> PriceEntryOut:
    """Manuelle Korrektur eines Eintrags."""
    entry = (
        db.query(PriceEntry)
        .join(PriceList, PriceEntry.price_list_id == PriceList.id)
        .filter(
            PriceEntry.id == entry_id,
            PriceList.id == price_list_id,
            PriceList.tenant_id == user.tenant_id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")

    data = update.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(entry, key, value)

    # DNA neu berechnen
    entry.dna = build_dna(
        entry.hersteller, entry.kategorie, entry.produktname, entry.abmessungen, entry.variante
    )
    entry.manuell_korrigiert = True
    entry.konfidenz = 1.0
    db.commit()
    db.refresh(entry)
    return PriceEntryOut.model_validate(entry)


@router.post("/{price_list_id}/activate", response_model=PriceListOut)
def activate_price_list(price_list_id: str, user: CurrentUser, db: DbSession) -> PriceListOut:
    pl = activate(db, user.tenant_id, price_list_id)
    return PriceListOut.model_validate(pl)


@router.delete("/{price_list_id}", status_code=204)
def delete_price_list(price_list_id: str, user: CurrentUser, db: DbSession) -> None:
    pl = (
        db.query(PriceList)
        .filter(PriceList.id == price_list_id, PriceList.tenant_id == user.tenant_id)
        .first()
    )
    if not pl:
        raise HTTPException(status_code=404, detail="Preisliste nicht gefunden")
    db.delete(pl)
    db.commit()
