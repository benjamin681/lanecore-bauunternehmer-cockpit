"""Background-Job-Ausführung: FastAPI BackgroundTasks mit DB-State.

Robustheitsmerkmale:
- Jobs haben Status queued/running/done/error und einen Recovery-Mechanismus
- PDFs werden aus DB geladen (persistent, überlebt Container-Neustart)
- Bei Job-Error wird das Ziel-Objekt (LV/PriceList) auch auf "error" gesetzt
- Zombie-Cleanup via cleanup_zombie_jobs() beim Startup
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Callable

import structlog
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.job import Job

log = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue_job(
    db: Session,
    *,
    tenant_id: str,
    kind: str,
    target_id: str = "",
    target_kind: str = "",
) -> Job:
    """Legt einen neuen Job an (Status 'queued'). Commit ist Aufgabe des Callers."""
    job = Job(
        tenant_id=tenant_id,
        kind=kind,
        target_id=target_id,
        target_kind=target_kind,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _update(job_id: str, **updates) -> None:
    """Aktualisiert Job-Status in eigener Session."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        for k, v in updates.items():
            setattr(job, k, v)
        db.commit()


def _mark_target_error(job: Job, error_message: str) -> None:
    """Bei Job-Fehler: das Ziel-Objekt (LV/PriceList) auch auf 'error' setzen,
    damit UI nicht auf 'parsing'/'extracting' hängen bleibt."""
    if not job.target_id or not job.target_kind:
        return
    with SessionLocal() as db:
        if job.target_kind == "lv":
            from app.models.lv import LV

            obj = db.get(LV, job.target_id)
            if obj and obj.status in ("queued", "extracting"):
                obj.status = "error"
                db.commit()
        elif job.target_kind == "price_list":
            from app.models.price_list import PriceList

            obj = db.get(PriceList, job.target_id)
            if obj and obj.status in ("queued", "parsing"):
                obj.status = "error"
                db.commit()


def run_job(job_id: str, fn: Callable[[Session, Job], None]) -> None:
    """Führt fn im Hintergrund mit vollem Status-Tracking aus."""
    _update(job_id, status="running", started_at=_now(), progress=5)
    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job:
                log.error("job_not_found", job_id=job_id)
                return
            try:
                fn(db, job)
                db.commit()
            except Exception:
                db.rollback()
                raise
        _update(job_id, status="done", finished_at=_now(), progress=100)
        log.info("job_done", job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("job_failed", job_id=job_id, error=str(exc))
        msg = str(exc)[:2000]
        # Anthropic-Fehler lesbar machen
        if "invalid_request_error" in msg.lower():
            msg = f"Claude-API-Fehler: {msg[:500]}"
        elif "rate_limit" in msg.lower() or "429" in msg:
            msg = "Claude-API-Rate-Limit erreicht. Bitte in 1 Minute erneut versuchen."
        elif "overloaded" in msg.lower() or "529" in msg:
            msg = "Claude-API überlastet. Bitte erneut versuchen."
        _update(
            job_id,
            status="error",
            finished_at=_now(),
            error_message=msg,
        )
        # Ziel-Objekt auch auf error setzen
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                _mark_target_error(job, msg)


def cleanup_zombie_jobs(max_age_minutes: int = 15) -> int:
    """Bei Startup: Jobs, die länger als max_age in 'running'/'queued' hängen,
    werden als 'error' markiert. Grund: Container-Restart killed Tasks."""
    cutoff = _now() - timedelta(minutes=max_age_minutes)
    count = 0
    with SessionLocal() as db:
        zombies = (
            db.query(Job)
            .filter(
                Job.status.in_(["queued", "running"]),
                Job.created_at < cutoff,
            )
            .all()
        )
        for job in zombies:
            job.status = "error"
            job.finished_at = _now()
            job.error_message = "Task wurde vom Server abgebrochen (Timeout/Neustart). Bitte erneut starten."
            count += 1
            _mark_target_error(job, job.error_message)
        db.commit()
    if count:
        log.info("cleanup_zombie_jobs", count=count)
    return count


# --- Konkrete Job-Handler --------------------------------------------------
def run_parse_price_list(
    job_id: str,
    tenant_id: str,
    price_list_id: str,
) -> None:
    """Background: Parse Preisliste. Lädt PDF-Bytes aus DB."""
    from app.core.config import settings as _settings
    from app.models.price_entry import PriceEntry
    from app.models.price_list import PriceList
    from app.services.claude_client import claude
    from app.services.pdf_utils import pdf_batch_images, pdf_total_pages
    from app.services.price_list_parser import (
        SYSTEM_PROMPT,
        _normalize_to_base,
        build_dna,
    )

    def _runner(db: Session, job: Job) -> None:
        pl = db.get(PriceList, price_list_id)
        if not pl:
            raise ValueError("PriceList verschwunden")
        if not pl.original_pdf_bytes:
            raise ValueError("Kein Original-PDF in DB gespeichert")
        pl.status = "parsing"
        db.flush()

        pdf_bytes = bytes(pl.original_pdf_bytes)

        total_pages = pdf_total_pages(pdf_bytes, max_pages=80)
        batch_size = max(1, _settings.claude_pages_per_batch)
        total_batches = max(1, (total_pages + batch_size - 1) // batch_size)

        seen_dna: set[str] = set()
        unsicher = 0
        total_eintraege = 0

        skipped_batches = 0
        for bi, start in enumerate(range(0, total_pages, batch_size)):
            batch = pdf_batch_images(pdf_bytes, batch_start=start, batch_size=batch_size)
            progress = int(10 + (bi / total_batches) * 85)
            _update(
                job.id,
                progress=progress,
                message=f"Batch {bi + 1}/{total_batches} (Seiten {start + 1}-{start + len(batch)})",
            )
            try:
                parsed, _model = claude.extract_json(system=SYSTEM_PROMPT, images=batch)
            except Exception as batch_err:  # noqa: BLE001
                log.warning(
                    "batch_failed_skipped",
                    batch=bi + 1,
                    total=total_batches,
                    error=str(batch_err)[:200],
                )
                skipped_batches += 1
                del batch
                continue
            del batch
            for row in parsed.get("eintraege", []):
                dna_key = "|".join(
                    str(row.get(k, ""))
                    for k in (
                        "hersteller", "kategorie", "produktname", "abmessungen", "variante"
                    )
                )
                if dna_key in seen_dna:
                    continue
                seen_dna.add(dna_key)
                preis = float(row.get("preis", 0.0) or 0.0)
                einheit = str(row.get("einheit", ""))
                preis_basis, basis_einheit = _normalize_to_base(
                    preis,
                    einheit,
                    variante=str(row.get("variante", "")),
                    abmessungen=str(row.get("abmessungen", "")),
                )
                konf = float(row.get("konfidenz", 1.0) or 1.0)
                if konf < 0.85:
                    unsicher += 1
                e = PriceEntry(
                    price_list_id=pl.id,
                    art_nr=str(row.get("art_nr", ""))[:100],
                    hersteller=str(row.get("hersteller", ""))[:100],
                    kategorie=str(row.get("kategorie", ""))[:100],
                    produktname=str(row.get("produktname", ""))[:300],
                    abmessungen=str(row.get("abmessungen", ""))[:200],
                    variante=str(row.get("variante", ""))[:200],
                    dna=build_dna(
                        str(row.get("hersteller", "")),
                        str(row.get("kategorie", "")),
                        str(row.get("produktname", "")),
                        str(row.get("abmessungen", "")),
                        str(row.get("variante", "")),
                    )[:500],
                    preis=preis,
                    einheit=einheit[:50],
                    preis_pro_basis=preis_basis,
                    basis_einheit=basis_einheit[:20],
                    konfidenz=max(0.0, min(1.0, konf)),
                )
                db.add(e)
                total_eintraege += 1

        pl.eintraege_gesamt = total_eintraege
        pl.eintraege_unsicher = unsicher
        pl.status = "review"
        if skipped_batches:
            _update(
                job.id,
                message=f"Fertig ({total_eintraege} Einträge; {skipped_batches}/{total_batches} Batches übersprungen)",
            )
        if total_eintraege == 0 and total_batches > 0:
            raise ValueError(
                f"Claude konnte keine Einträge erkennen ({skipped_batches}/{total_batches} Batches ohne Antwort)"
            )

    run_job(job_id, _runner)


def run_parse_lv(
    job_id: str,
    tenant_id: str,
    lv_id: str,
) -> None:
    """Background: Parse LV. Lädt PDF-Bytes aus DB."""
    from app.core.config import settings as _settings
    from app.models.lv import LV
    from app.models.position import Position
    from app.services.claude_client import claude
    from app.services.lv_parser import SYSTEM_PROMPT
    from app.services.pdf_utils import pdf_batch_images, pdf_total_pages

    def _runner(db: Session, job: Job) -> None:
        lv = db.get(LV, lv_id)
        if not lv:
            raise ValueError("LV verschwunden")
        if not lv.original_pdf_bytes:
            raise ValueError("Kein Original-PDF in DB gespeichert")
        lv.status = "extracting"
        db.flush()

        pdf_bytes = bytes(lv.original_pdf_bytes)
        total_pages = pdf_total_pages(pdf_bytes, max_pages=80)
        batch_size = max(1, _settings.claude_pages_per_batch)
        total_batches = max(1, (total_pages + batch_size - 1) // batch_size)

        positionen: list[dict] = []
        projekt_name = ""
        auftraggeber = ""

        skipped_batches = 0
        for bi, start in enumerate(range(0, total_pages, batch_size)):
            batch = pdf_batch_images(pdf_bytes, batch_start=start, batch_size=batch_size)
            progress = int(10 + (bi / total_batches) * 85)
            _update(
                job.id,
                progress=progress,
                message=f"Batch {bi + 1}/{total_batches} (Seiten {start + 1}-{start + len(batch)})",
            )
            try:
                parsed, _model = claude.extract_json(system=SYSTEM_PROMPT, images=batch)
            except Exception as batch_err:  # noqa: BLE001
                log.warning(
                    "batch_failed_skipped",
                    batch=bi + 1,
                    total=total_batches,
                    error=str(batch_err)[:200],
                )
                skipped_batches += 1
                del batch
                continue
            del batch
            if not projekt_name:
                projekt_name = str(parsed.get("projekt_name", ""))
            if not auftraggeber:
                auftraggeber = str(parsed.get("auftraggeber", ""))
            positionen.extend(parsed.get("positionen", []))

        lv.projekt_name = projekt_name[:300]
        lv.auftraggeber = auftraggeber[:300]

        unsicher = 0
        for idx, row in enumerate(positionen):
            konf = float(row.get("konfidenz", 0.7) or 0.7)
            if konf < 0.85:
                unsicher += 1
            p = Position(
                lv_id=lv.id,
                reihenfolge=int(row.get("reihenfolge", idx + 1) or idx + 1),
                oz=str(row.get("oz", ""))[:50],
                titel=str(row.get("titel", ""))[:300],
                kurztext=str(row.get("kurztext", "")),
                langtext=str(row.get("langtext", "")),
                menge=float(row.get("menge", 0.0) or 0.0),
                einheit=str(row.get("einheit", ""))[:20],
                erkanntes_system=str(row.get("erkanntes_system", ""))[:50],
                feuerwiderstand=str(row.get("feuerwiderstand", ""))[:20],
                plattentyp=str(row.get("plattentyp", ""))[:50],
                konfidenz=max(0.0, min(1.0, konf)),
            )
            db.add(p)

        lv.positionen_gesamt = len(positionen)
        lv.positionen_unsicher = unsicher
        lv.status = "review_needed"
        if skipped_batches:
            _update(
                job.id,
                message=f"Fertig ({len(positionen)} Positionen; {skipped_batches}/{total_batches} Batches übersprungen)",
            )
        if len(positionen) == 0 and total_batches > 0:
            raise ValueError(
                f"Claude konnte keine Positionen erkennen ({skipped_batches}/{total_batches} Batches ohne Antwort)"
            )

    run_job(job_id, _runner)
