"""LV-API: Upload, Review, Kalkulation, Export-PDF, Download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models.lv import LV
from app.models.position import Position
from app.models.tenant import Tenant
from app.schemas.job import JobOut
from app.schemas.lv import LVDetail, LVOut, PositionOut, PositionUpdate
from app.services.jobs import enqueue_job, run_parse_lv
from app.services.kalkulation import kalkuliere_lv
from app.services.lv_parser import parse_and_store
from app.services.pdf_filler import generate_filled_pdf
from app.services.pdf_utils import compute_sha256, save_upload

router = APIRouter(prefix="/lvs", tags=["lvs"])


@router.post("/upload-async", response_model=JobOut, status_code=202)
async def upload_lv_async(
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> JobOut:
    """Async-Upload: liefert sofort Job-ID zurück."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nur PDF-Dateien erlaubt")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF > 50 MB nicht erlaubt")

    sha = compute_sha256(pdf_bytes)
    dest = settings.upload_dir / "lvs" / user.tenant_id
    pdf_path = save_upload(pdf_bytes, dest, file.filename)

    lv = LV(
        tenant_id=user.tenant_id,
        original_dateiname=file.filename,
        original_pdf_pfad=str(pdf_path),
        original_pdf_sha256=sha,
        status="queued",
    )
    db.add(lv)
    db.flush()

    job = enqueue_job(
        db,
        tenant_id=user.tenant_id,
        kind="parse_lv",
        target_id=lv.id,
        target_kind="lv",
    )
    background_tasks.add_task(
        run_parse_lv,
        job_id=job.id,
        tenant_id=user.tenant_id,
        lv_id=lv.id,
        pdf_bytes=pdf_bytes,
    )
    return JobOut.model_validate(job)


@router.post("/{lv_id}/retry-parse", response_model=JobOut, status_code=202)
def retry_parse_lv(
    lv_id: str,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> JobOut:
    """Neustart des Parse-Jobs für ein LV, das in 'queued' oder 'error' hängt.

    Liest das Original-PDF aus dem Upload-Ordner und startet den Background-Task neu.
    """
    from pathlib import Path

    from app.models.position import Position
    from app.services.jobs import enqueue_job, run_parse_lv

    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    if not lv.original_pdf_pfad:
        raise HTTPException(status_code=400, detail="Kein Original-PDF gespeichert")
    pdf_path = Path(lv.original_pdf_pfad)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Original-PDF verloren (Disk)")

    pdf_bytes = pdf_path.read_bytes()

    # Alte Positionen löschen
    db.query(Position).filter(Position.lv_id == lv.id).delete()
    lv.status = "queued"
    lv.positionen_gesamt = 0
    lv.positionen_gematcht = 0
    lv.positionen_unsicher = 0
    lv.projekt_name = ""
    lv.auftraggeber = ""
    db.commit()

    job = enqueue_job(
        db, tenant_id=user.tenant_id, kind="parse_lv",
        target_id=lv.id, target_kind="lv",
    )
    background_tasks.add_task(
        run_parse_lv, job_id=job.id, tenant_id=user.tenant_id,
        lv_id=lv.id, pdf_bytes=pdf_bytes,
    )
    return JobOut.model_validate(job)


@router.post("/upload", response_model=LVDetail, status_code=201)
async def upload_lv(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> LVDetail:
    """LV-PDF hochladen → Positionen werden via Claude Vision extrahiert."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nur PDF-Dateien erlaubt")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF > 50 MB nicht erlaubt")

    lv = parse_and_store(
        db=db, tenant_id=user.tenant_id, pdf_bytes=pdf_bytes, original_dateiname=file.filename
    )
    return LVDetail.model_validate(
        {
            **LVOut.model_validate(lv).model_dump(),
            "positions": [PositionOut.model_validate(p) for p in lv.positions],
        }
    )


@router.get("", response_model=list[LVOut])
def list_lvs(user: CurrentUser, db: DbSession) -> list[LVOut]:
    rows = (
        db.query(LV)
        .filter(LV.tenant_id == user.tenant_id)
        .order_by(LV.created_at.desc())
        .all()
    )
    return [LVOut.model_validate(r) for r in rows]


@router.get("/{lv_id}", response_model=LVDetail)
def get_lv(lv_id: str, user: CurrentUser, db: DbSession) -> LVDetail:
    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    return LVDetail.model_validate(
        {
            **LVOut.model_validate(lv).model_dump(),
            "positions": [PositionOut.model_validate(p) for p in lv.positions],
        }
    )


@router.patch(
    "/{lv_id}/positions/{position_id}", response_model=PositionOut
)
def update_position(
    lv_id: str,
    position_id: str,
    update: PositionUpdate,
    user: CurrentUser,
    db: DbSession,
) -> PositionOut:
    """Manuelle Positions-Korrektur vor der Kalkulation."""
    pos = (
        db.query(Position)
        .join(LV, Position.lv_id == LV.id)
        .filter(
            Position.id == position_id,
            LV.id == lv_id,
            LV.tenant_id == user.tenant_id,
        )
        .first()
    )
    if not pos:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")
    data = update.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(pos, k, v)
    pos.manuell_korrigiert = True
    db.commit()
    db.refresh(pos)
    return PositionOut.model_validate(pos)


@router.post("/{lv_id}/kalkulation", response_model=LVDetail)
def run_kalkulation(lv_id: str, user: CurrentUser, db: DbSession) -> LVDetail:
    """Berechnet EP/GP für alle Positionen mit der aktuell aktiven Preisliste."""
    try:
        lv = kalkuliere_lv(db, lv_id, user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return LVDetail.model_validate(
        {
            **LVOut.model_validate(lv).model_dump(),
            "positions": [PositionOut.model_validate(p) for p in lv.positions],
        }
    )


@router.post("/{lv_id}/export", response_model=LVOut)
def export_pdf(lv_id: str, user: CurrentUser, db: DbSession) -> LVOut:
    """Erzeugt ausgefülltes PDF und legt den Pfad im LV ab."""
    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    if lv.status not in ("calculated", "exported"):
        raise HTTPException(
            status_code=400,
            detail="LV muss erst kalkuliert werden (Status 'calculated').",
        )
    tenant = db.get(Tenant, user.tenant_id)
    assert tenant is not None
    try:
        path = generate_filled_pdf(lv, tenant.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF-Erzeugung fehlgeschlagen: {e}") from e
    lv.ausgefuelltes_pdf_pfad = str(path)
    lv.status = "exported"
    db.commit()
    db.refresh(lv)
    return LVOut.model_validate(lv)


@router.get("/{lv_id}/download")
def download_pdf(lv_id: str, user: CurrentUser, db: DbSession) -> FileResponse:
    """Download des ausgefüllten LV-PDFs."""
    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv or not lv.ausgefuelltes_pdf_pfad:
        raise HTTPException(status_code=404, detail="Kein ausgefülltes PDF vorhanden")
    path = Path(lv.ausgefuelltes_pdf_pfad)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF-Datei fehlt auf Server")
    filename = f"LV_mit_Preisen_{lv.projekt_name or lv.id[:8]}.pdf"
    return FileResponse(path=path, media_type="application/pdf", filename=filename)


@router.delete("/{lv_id}", status_code=204)
def delete_lv(lv_id: str, user: CurrentUser, db: DbSession) -> None:
    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    db.delete(lv)
    db.commit()
