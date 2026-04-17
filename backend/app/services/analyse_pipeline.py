"""Analyse-Pipeline — orchestrates full PDF→Claude→DB workflow as background task."""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.storage import storage
from app.models.analyse_job import AnalyseJob
from app.models.analyse_ergebnis import AnalyseErgebnis
from app.models.projekt import Projekt
from app.services.pdf_service import validate_pdf, pdf_to_images
from app.services.bauplan_service import BauplanAnalyseService

log = structlog.get_logger()

analyse_service = BauplanAnalyseService()


async def run_analyse_pipeline(job_id: uuid.UUID, pdf_bytes: bytes, filename: str) -> None:
    """
    Full analysis pipeline — runs as a FastAPI BackgroundTask.

    Steps:
    1. Mark job as "processing"
    2. Validate PDF
    3. Upload PDF to S3
    4. Convert pages to images
    5. Analyse each page with Claude
    6. Merge results
    7. Store AnalyseErgebnis in DB
    8. Mark job as "completed"
    """
    async with AsyncSessionLocal() as db:
        try:
            await _update_job_status(db, job_id, "processing", progress=5)

            # 1. Validate
            pdf_info = validate_pdf(pdf_bytes)
            await _update_job_status(db, job_id, "processing", progress=10)

            # 2. Upload to S3 (skip if no credentials configured)
            if settings.aws_access_key_id:
                s3_key = await storage.upload_pdf(pdf_bytes, str(job_id), filename)
            else:
                # Dev mode: save locally
                local_dir = Path(f"/tmp/lanecore-uploads/{job_id}")
                local_dir.mkdir(parents=True, exist_ok=True)
                (local_dir / filename).write_bytes(pdf_bytes)
                s3_key = f"local://{local_dir / filename}"
                log.info("pdf_saved_locally", path=str(local_dir / filename))
            await _update_s3_key(db, job_id, s3_key)
            await _update_job_status(db, job_id, "processing", progress=15)

            # 3. Convert PDF to images
            # 200 DPI ist der Norm-Wert für lesbare Pläne. Bei Production kann
            # via env var PDF_DPI gesenkt werden falls RAM knapp wird.
            dpi = int(os.getenv("PDF_DPI", "200"))
            page_images = pdf_to_images(pdf_bytes, dpi=dpi)
            total_pages = len(page_images)
            await _update_job_status(db, job_id, "processing", progress=20)

            # 4. Analyse each page
            page_results: list[dict] = []
            total_input_tokens = 0
            total_output_tokens = 0
            total_cost = 0.0
            model_used = ""

            for i, page_img in enumerate(page_images):
                progress = 20 + int((i / max(total_pages, 1)) * 60)  # 20–80%
                await _update_job_status(db, job_id, "processing", progress=progress)

                log.info("analysing_page", job_id=str(job_id), page=page_img.page_num, total=total_pages)
                result = await analyse_service.analyse_page(page_img.image_base64, page_img.page_num)
                page_results.append(result)

                # Track stats
                stats = result.get("_stats", {})
                total_input_tokens += stats.get("input_tokens", 0)
                total_output_tokens += stats.get("output_tokens", 0)
                total_cost += stats.get("cost_usd", 0.0)
                model_used = stats.get("model", model_used)

            await _update_job_status(db, job_id, "processing", progress=85)

            # 5. Merge results from all pages
            merged = _merge_page_results(page_results)

            # 6. Store result in DB
            ergebnis = AnalyseErgebnis(
                job_id=job_id,
                plantyp=merged.get("plantyp"),
                massstab=merged.get("massstab"),
                geschoss=merged.get("geschoss"),
                konfidenz=Decimal(str(merged.get("konfidenz", 0.0))),
                raeume=merged.get("raeume", []),
                waende=merged.get("waende", []),
                decken=merged.get("decken", []),
                oeffnungen=merged.get("oeffnungen", []),
                details=merged.get("details", []),
                gestrichene_positionen=merged.get("gestrichene_positionen", []),
                warnungen=merged.get("warnungen", []),
                raw_claude_response=merged.get("_raw_response"),
                prompt_hash=merged.get("_prompt_hash"),
            )
            db.add(ergebnis)

            # 7. Update job with stats
            job = await _get_job(db, job_id)
            if job:
                job.model_used = model_used
                job.input_tokens = total_input_tokens
                job.output_tokens = total_output_tokens
                job.cost_usd = Decimal(str(round(total_cost, 6)))
                job.completed_at = datetime.now(timezone.utc)

            # 8. Auto-create or assign Projekt from plan metadata
            if job and not job.projekt_id:
                projekt = await _auto_create_projekt(db, merged, job)
                if projekt:
                    job.projekt_id = projekt.id
                    log.info("projekt_auto_created",
                             projekt_id=str(projekt.id),
                             name=projekt.name,
                             auftraggeber=projekt.auftraggeber)

            await _update_job_status(db, job_id, "completed", progress=100)

            log.info(
                "analyse_complete",
                job_id=str(job_id),
                pages=total_pages,
                cost_usd=round(total_cost, 4),
                konfidenz=merged.get("konfidenz"),
            )

        except Exception as e:
            log.error("analyse_pipeline_failed", job_id=str(job_id), error=str(e))
            await _update_job_status(db, job_id, "failed", error_message=str(e))


def _merge_page_results(page_results: list[dict]) -> dict:
    """Merge results from multiple pages into one combined result.

    - Rooms: deduplicated by raum_nr (first occurrence wins, highest konfidenz kept)
    - Walls: all walls from all pages combined
    - Ceilings: deduplicated by raum_nr
    - Warnings: combined from all pages (deduplicated)
    - Konfidenz: highest value across all pages
    """
    merged: dict = {
        "plantyp": None,
        "massstab": None,
        "geschoss": None,
        "projekt": None,
        "konfidenz": 0.0,
        "raeume": [],
        "waende": [],
        "decken": [],
        "oeffnungen": [],
        "details": [],
        "gestrichene_positionen": [],
        "warnungen": [],
    }

    raw_responses: list[str] = []
    prompt_hash = None

    # Deduplication indices
    seen_raum_nrs: dict[str, int] = {}   # raum_nr -> index in merged["raeume"]
    seen_decke_nrs: dict[str, int] = {}  # raum_nr -> index in merged["decken"]
    seen_warnungen: set[str] = set()

    for result in page_results:
        if result.get("type") == "skipped":
            continue

        # Take plantyp/massstab from first non-skipped page
        if merged["plantyp"] is None and result.get("plantyp"):
            merged["plantyp"] = result["plantyp"]
        if merged["massstab"] is None and result.get("massstab"):
            merged["massstab"] = result["massstab"]
        if merged["geschoss"] is None and result.get("geschoss"):
            merged["geschoss"] = result["geschoss"]
        if merged["projekt"] is None and result.get("projekt"):
            merged["projekt"] = result["projekt"]

        # Konfidenz: take highest value
        page_conf = result.get("konfidenz", 0.0)
        if isinstance(page_conf, (int, float)) and page_conf > merged["konfidenz"]:
            merged["konfidenz"] = page_conf

        # Merge rooms — deduplicate by raum_nr
        for raum in result.get("raeume", []) if isinstance(result.get("raeume"), list) else []:
            nr = raum.get("raum_nr")
            if nr and nr in seen_raum_nrs:
                continue  # skip duplicate
            merged["raeume"].append(raum)
            if nr:
                seen_raum_nrs[nr] = len(merged["raeume"]) - 1

        # Merge walls — all walls from all pages
        walls = result.get("waende", [])
        if isinstance(walls, list):
            merged["waende"].extend(walls)

        # Merge ceilings — deduplicate by raum_nr
        for decke in result.get("decken", []) if isinstance(result.get("decken"), list) else []:
            nr = decke.get("raum_nr")
            if nr and nr in seen_decke_nrs:
                continue  # skip duplicate
            merged["decken"].append(decke)
            if nr:
                seen_decke_nrs[nr] = len(merged["decken"]) - 1

        # Merge other lists without deduplication
        for key in ("oeffnungen", "details", "gestrichene_positionen"):
            items = result.get(key, [])
            if isinstance(items, list):
                merged[key].extend(items)

        # Merge warnings — deduplicate by text
        for w in result.get("warnungen", []) if isinstance(result.get("warnungen"), list) else []:
            if w not in seen_warnungen:
                seen_warnungen.add(w)
                merged["warnungen"].append(w)

        if result.get("_raw_response"):
            raw_responses.append(result["_raw_response"])
        if result.get("_prompt_hash"):
            prompt_hash = result["_prompt_hash"]

    merged["_raw_response"] = "\n\n---PAGE BREAK---\n\n".join(raw_responses)
    merged["_prompt_hash"] = prompt_hash

    # --- Detect empty results and set konfidenz to 0.0 ---
    has_elements = (
        len(merged["raeume"]) > 0
        or len(merged["waende"]) > 0
        or len(merged["decken"]) > 0
    )
    analysed_pages = [r for r in page_results if r.get("type") != "skipped"]

    if not has_elements:
        merged["konfidenz"] = 0.0
        if not analysed_pages:
            merged["warnungen"].append(
                "Keine relevanten Baupläne erkannt. Die hochgeladene Datei enthält "
                "möglicherweise keinen Grundriss, Deckenspiegel oder Schnitt."
            )
        else:
            merged["warnungen"].append(
                "Keine Bauelemente (Räume, Wände, Decken) erkannt. Mögliche Ursachen: "
                "Die Datei ist kein Bauplan (z.B. Angebot, Rechnung), der Plan ist zu "
                "niedrig aufgelöst, oder das Format wird nicht unterstützt."
            )
        merged["keine_elemente"] = True

    return merged


# --- DB Helper Functions ---


async def _get_job(db: AsyncSession, job_id: uuid.UUID) -> AnalyseJob | None:
    result = await db.execute(select(AnalyseJob).where(AnalyseJob.id == job_id))
    return result.scalar_one_or_none()


async def _update_job_status(
    db: AsyncSession,
    job_id: uuid.UUID,
    status: str,
    progress: int = 0,
    error_message: str | None = None,
) -> None:
    """Atomic status update via UPDATE...WHERE (no SELECT+UPDATE race)."""
    values: dict = {
        "status": status,
        "progress": progress,
        "updated_at": func.now(),
    }
    if error_message:
        values["error_message"] = error_message
    stmt = update(AnalyseJob).where(AnalyseJob.id == job_id).values(**values)
    await db.execute(stmt)
    await db.commit()


async def _auto_create_projekt(
    db: AsyncSession, merged: dict, job: AnalyseJob
) -> Projekt | None:
    """Auto-create or find a Projekt based on plan metadata.

    If a Projekt with the same name already exists for this user, reuse it.
    Otherwise create a new one.
    """
    projekt_info = merged.get("projekt") or {}

    # Priority 1: projekt_info.name from Claude analysis
    name = projekt_info.get("name")

    # Priority 2: fallback to filename
    if not name:
        raw = job.filename.replace(".pdf", "").replace("_", " ").strip()
        name = " ".join(w.capitalize() for w in raw.split())

    if not name:
        return None

    user_id = "dev-user"  # TODO: get from job context when auth is implemented

    # Check if Projekt with same name exists
    result = await db.execute(
        select(Projekt).where(Projekt.name == name, Projekt.user_id == user_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        log.info("projekt_reused", projekt_id=str(existing.id), name=name)
        return existing

    # Create new Projekt from plan metadata
    projekt = Projekt(
        user_id=user_id,
        name=name,
        auftraggeber=projekt_info.get("auftraggeber") or projekt_info.get("bauherr"),
        bauherr=projekt_info.get("bauherr"),
        architekt=projekt_info.get("architekt"),
        adresse=projekt_info.get("adresse"),
        plan_nr=projekt_info.get("plan_nr"),
        status="aktiv",
        beschreibung=f"Auto-erstellt aus Plan: {job.filename}",
    )
    db.add(projekt)
    await db.flush()
    return projekt


async def _update_s3_key(db: AsyncSession, job_id: uuid.UUID, s3_key: str) -> None:
    job = await _get_job(db, job_id)
    if job:
        job.s3_key = s3_key
        await db.commit()
