"""LV-API: Upload, Review, Kalkulation, Export-PDF, Download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi import status as http_status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models.lv import LV
from app.models.position import Position
from app.models.tenant import Tenant
from app.schemas.candidates import (
    CandidateOut,
    MaterialWithCandidates,
    PositionCandidatesOut,
)
from app.schemas.gaps import (
    GapResolveRequest,
    GapResolveResponse,
    GapResolutionOut,
    GapResolutionTypeSchema,
    LVGapsReport,
)
from app.schemas.job import JobOut
from app.schemas.lv import LVDetail, LVOut, PositionOut, PositionUpdate
from app.services.catalog_gaps import (
    GapResolutionError,
    compute_lv_gaps,
    resolve_gap_manual_price,
    resolve_gap_skip,
)
from app.services.lv_pdf_export import LVExportError, generate_angebot_pdf
from app.services.jobs import enqueue_job, run_parse_lv
from app.services.kalkulation import kalkuliere_lv
from app.services.lv_parser import parse_and_store
from app.services.pdf_filler import generate_filled_pdf
from app.services.pdf_utils import compute_sha256, save_upload
from app.services.price_lookup import list_candidates_for_position

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

    # PDF in DB speichern (persistent)
    lv = LV(
        tenant_id=user.tenant_id,
        original_dateiname=file.filename,
        original_pdf_sha256=sha,
        original_pdf_bytes=pdf_bytes,
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
    )
    return JobOut.model_validate(job)


@router.post("/{lv_id}/retry-parse", response_model=JobOut, status_code=202)
def retry_parse_lv(
    lv_id: str,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> JobOut:
    """Neustart des Parse-Jobs für ein LV, das in 'queued' oder 'error' hängt."""
    from app.models.job import Job
    from app.models.position import Position
    from app.services.jobs import enqueue_job, run_parse_lv

    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    if not lv.original_pdf_bytes:
        raise HTTPException(
            status_code=400,
            detail="Kein Original-PDF mehr vorhanden — bitte neu hochladen",
        )

    active = (
        db.query(Job)
        .filter(
            Job.target_id == lv.id,
            Job.target_kind == "lv",
            Job.status.in_(["queued", "running"]),
        )
        .first()
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"Job läuft bereits ({active.status}), bitte warten",
        )

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
        run_parse_lv, job_id=job.id, tenant_id=user.tenant_id, lv_id=lv.id,
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
    """Erzeugt ausgefülltes PDF und persistiert es in der DB."""
    from app.services.pdf_filler import generate_filled_pdf_bytes

    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    if lv.status not in ("calculated", "exported"):
        raise HTTPException(
            status_code=400,
            detail="LV muss erst kalkuliert werden.",
        )
    if not lv.original_pdf_bytes:
        raise HTTPException(
            status_code=400,
            detail="Kein Original-PDF gespeichert. Bitte LV neu hochladen.",
        )
    tenant = db.get(Tenant, user.tenant_id)
    assert tenant is not None
    try:
        pdf_bytes = generate_filled_pdf_bytes(lv, tenant.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail="PDF-Erzeugung fehlgeschlagen") from e
    lv.ausgefuelltes_pdf_bytes = pdf_bytes
    lv.status = "exported"
    db.commit()
    db.refresh(lv)
    return LVOut.model_validate(lv)


@router.get("/{lv_id}/download")
def download_pdf(lv_id: str, user: CurrentUser, db: DbSession):
    """Download des ausgefüllten LV-PDFs aus DB."""
    from fastapi.responses import Response

    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv or not lv.ausgefuelltes_pdf_bytes:
        raise HTTPException(status_code=404, detail="Kein ausgefülltes PDF vorhanden")
    # RFC 6266 konform: ASCII-filename + UTF-8-filename*
    import re
    from urllib.parse import quote

    raw = f"LV_mit_Preisen_{lv.projekt_name or lv.id[:8]}.pdf".replace(" ", "_")
    ascii_name = re.sub(r"[^A-Za-z0-9._\-]", "_", raw)[:100] or "lv.pdf"
    utf8_name = quote(raw, safe=".-_")
    return Response(
        content=bytes(lv.ausgefuelltes_pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
        },
    )


@router.delete("/{lv_id}", status_code=204)
def delete_lv(lv_id: str, user: CurrentUser, db: DbSession) -> None:
    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == user.tenant_id).first()
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    db.delete(lv)
    db.commit()


@router.get(
    "/{lv_id}/positions/{position_id}/candidates",
    response_model=PositionCandidatesOut,
)
def list_position_candidates(
    lv_id: str,
    position_id: str,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(3, ge=1, le=5),
) -> PositionCandidatesOut:
    """B+4.3.0b — Near-Miss-Drawer-Daten fuer eine LV-Position.

    Liefert pro Material der Position eine sortierte Kandidaten-Liste
    (Top-N echte Treffer + 1 virtueller Kategorie-Mittelwert). UT-
    Blacklist wird angewandt; Kandidaten-Reihenfolge je Material
    ist deterministisch (Rezept-Reihenfolge).
    """
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

    material_dicts = list_candidates_for_position(
        db=db,
        tenant_id=user.tenant_id,
        erkanntes_system=pos.erkanntes_system,
        feuerwiderstand=pos.feuerwiderstand,
        plattentyp=pos.plattentyp,
        limit=limit,
    )
    materials = [
        MaterialWithCandidates(
            material_name=m["material_name"],
            required_amount=m["required_amount"],
            unit=m["unit"],
            candidates=[CandidateOut(**c) for c in m["candidates"]],
        )
        for m in material_dicts
    ]
    return PositionCandidatesOut(
        position_id=str(pos.id),
        position_name=pos.erkanntes_system or pos.kurztext or "",
        materials=materials,
    )


@router.get("/{lv_id}/gaps", response_model=LVGapsReport)
def get_lv_gaps(
    lv_id: str,
    user: CurrentUser,
    db: DbSession,
    include_low_confidence: bool = Query(
        False,
        description=(
            "Wenn True, enthaelt der Report zusaetzlich supplier_price-"
            "Matches mit match_confidence < 0.5 als severity=low_confidence."
        ),
    ),
) -> LVGapsReport:
    """B+4.3.0c — Katalog-Luecken-Report fuer ein LV.

    Liefert eine strukturierte Liste aller Material-Zeilen des LVs,
    deren price_source nicht zu einem sauberen Katalog-Match gehoert
    (not_found, estimated; optional low_confidence). Nutzt
    ausschliesslich die persistierten materialien-JSONs der Positionen
    und berechnet keine neuen Lookups.
    """
    lv = (
        db.query(LV)
        .filter(LV.id == lv_id, LV.tenant_id == user.tenant_id)
        .first()
    )
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    return compute_lv_gaps(
        lv, include_low_confidence=include_low_confidence, db=db
    )


@router.post(
    "/{lv_id}/gaps/resolve",
    response_model=GapResolveResponse,
)
def resolve_lv_gap(
    lv_id: str,
    payload: GapResolveRequest,
    user: CurrentUser,
    db: DbSession,
    recalculate: bool = Query(
        default=True,
        description=(
            "Wenn True, wird das LV direkt nach der Resolve-Aktion neu "
            "kalkuliert und die neue Summe/Materialien sind sofort im "
            "LV-Detail sichtbar. Bei False uebernimmt der Aufrufer das "
            "Re-Calc (z.B. fuer Batch-Updates)."
        ),
    ),
) -> GapResolveResponse:
    """B+4.6 — Loest eine Katalog-Luecke entweder per manuellem Preis
    (legt zusaetzlich einen Tenant-Override an) oder per Skip-Marker.

    Tenant-Isolation ueber lv.tenant_id. Die Resolution ist idempotent
    pro (lv_id, material_dna, resolution_type) — mehrfacher Aufruf mit
    demselben Typ aktualisiert den bestehenden Eintrag.
    """
    lv = (
        db.query(LV)
        .filter(LV.id == lv_id, LV.tenant_id == user.tenant_id)
        .first()
    )
    if not lv:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")

    try:
        if payload.resolution_type == GapResolutionTypeSchema.MANUAL_PRICE:
            price_net = payload.value.get("price_net")
            unit = payload.value.get("unit", "")
            audit = resolve_gap_manual_price(
                db=db,
                lv=lv,
                tenant_id=user.tenant_id,
                user_id=user.id,
                material_dna=payload.material_dna,
                price_net=float(price_net) if price_net is not None else -1,
                unit=str(unit),
            )
        else:
            audit = resolve_gap_skip(
                db=db,
                lv=lv,
                tenant_id=user.tenant_id,
                user_id=user.id,
                material_dna=payload.material_dna,
            )
    except GapResolutionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    recalculated = False
    if recalculate:
        # kalkuliere_lv liest die Overrides selbst und weisst price_source
        # "override" pro betroffener Position zu.
        from app.services.kalkulation import kalkuliere_lv

        kalkuliere_lv(db, lv_id, user.tenant_id)
        recalculated = True

    db.commit()
    db.refresh(audit)

    return GapResolveResponse(
        resolution=GapResolutionOut.model_validate(audit),
        recalculated=recalculated,
    )


@router.get("/{lv_id}/export-pdf")
def export_lv_pdf(
    lv_id: str,
    user: CurrentUser,
    db: DbSession,
    inline: bool = Query(
        default=False,
        description=(
            "Wenn True, wird das PDF inline im Browser geladen (Vorschau-"
            "Modus). Default ist Download mit attachment-Disposition."
        ),
    ),
):
    """B+4.8 — Liefert das LV als professionelles Angebots-PDF.

    Liest LV + Tenant-Stammdaten (company_settings JSON), generiert via
    PyMuPDF ein A4-Layout mit Briefkopf, Empfaenger, Positionstabelle
    samt Zwischensummen, Gesamtsumme + MwSt + Brutto und Footer.

    Auth: Tenant-Scope ueber lv.tenant_id. Filename:
    "Angebot-A<datum>-<id6>.pdf".
    """
    from fastapi.responses import Response

    from app.models.tenant import Tenant
    from app.services.lv_pdf_export import _build_angebotsnummer

    lv = (
        db.query(LV)
        .filter(LV.id == lv_id, LV.tenant_id == user.tenant_id)
        .first()
    )
    if lv is None:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")

    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        # Datenintegritaet — Tenant des Users muss existieren.
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")

    try:
        pdf_bytes = generate_angebot_pdf(lv, tenant)
    except LVExportError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    angebotsnr = _build_angebotsnummer(lv)
    filename = f"Angebot-{angebotsnr}.pdf"
    disposition = "inline" if inline else "attachment"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )
