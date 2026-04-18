"""Background-Job-Ausführung: FastAPI BackgroundTasks mit DB-State.

Strategie: FastAPI BackgroundTasks (in-process, kein externer Worker nötig für MVP).
Jobs laufen nach dem Request-Response im selben Prozess. Bei Scale-Up: Upgrade
auf RQ/Celery ohne API-Änderung am Job-Endpoint.

Jede Job-Funktion
- öffnet eine eigene DB-Session (NICHT die Request-Session)
- updated Job-Row mit Status/Progress
- fängt alle Exceptions und schreibt error_message
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    """Legt einen neuen Job in der DB an (Status 'queued')."""
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
    """Aktualisiert Job-Status in eigener Session (für Background-Worker)."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        for k, v in updates.items():
            setattr(job, k, v)
        db.commit()


def run_job(job_id: str, fn: Callable[[Session, Job], None]) -> None:
    """Führt `fn` im Hintergrund aus, mit vollständigem Status-Tracking.

    fn(db, job) bekommt eine frische DB-Session UND das Job-Objekt, um z.B. progress
    auf dem Job zu setzen.
    """
    _update(job_id, status="running", started_at=_now(), progress=5)
    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job:
                log.error("job_not_found", job_id=job_id)
                return
            fn(db, job)
            db.commit()
        _update(job_id, status="done", finished_at=_now(), progress=100)
        log.info("job_done", job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("job_failed", job_id=job_id, error=str(exc))
        _update(
            job_id,
            status="error",
            finished_at=_now(),
            error_message=str(exc)[:2000],
        )


# --- Konkrete Job-Handler --------------------------------------------------
def run_parse_price_list(
    job_id: str,
    tenant_id: str,
    price_list_id: str,
    pdf_bytes: bytes,
) -> None:
    """Background: Parse Preisliste → PriceList-Status 'review'."""
    from app.models.price_list import PriceList
    from app.services.price_list_parser import (
        SYSTEM_PROMPT,
        _normalize_to_base,
        build_dna,
    )
    from app.services.claude_client import claude
    from app.services.pdf_utils import pdf_to_page_images
    from app.core.config import settings as _settings
    from app.models.price_entry import PriceEntry

    def _runner(db: Session, job: Job) -> None:
        pl = db.get(PriceList, price_list_id)
        if not pl:
            raise ValueError("PriceList verschwunden")
        pl.status = "parsing"
        db.flush()

        images = pdf_to_page_images(pdf_bytes, dpi=200, max_pages=80)
        batch_size = max(1, _settings.claude_pages_per_batch)
        total_batches = max(1, (len(images) + batch_size - 1) // batch_size)

        seen_dna: set[str] = set()
        unsicher = 0
        total_eintraege = 0

        for bi, start in enumerate(range(0, len(images), batch_size)):
            batch = images[start : start + batch_size]
            progress = int(10 + (bi / total_batches) * 85)
            _update(
                job.id,
                progress=progress,
                message=f"Batch {bi + 1}/{total_batches} (Seiten {start + 1}-{start + len(batch)})",
            )
            parsed, _model = claude.extract_json(system=SYSTEM_PROMPT, images=batch)
            for row in parsed.get("eintraege", []):
                dna_key = "|".join(
                    str(row.get(k, "")) for k in (
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

    run_job(job_id, _runner)


def run_parse_lv(
    job_id: str,
    tenant_id: str,
    lv_id: str,
    pdf_bytes: bytes,
) -> None:
    from app.core.config import settings as _settings
    from app.models.lv import LV
    from app.models.position import Position
    from app.services.claude_client import claude
    from app.services.lv_parser import SYSTEM_PROMPT
    from app.services.pdf_utils import pdf_to_page_images

    def _runner(db: Session, job: Job) -> None:
        lv = db.get(LV, lv_id)
        if not lv:
            raise ValueError("LV verschwunden")
        lv.status = "extracting"
        db.flush()

        images = pdf_to_page_images(pdf_bytes, dpi=200, max_pages=80)
        batch_size = max(1, _settings.claude_pages_per_batch)
        total_batches = max(1, (len(images) + batch_size - 1) // batch_size)

        positionen: list[dict] = []
        projekt_name = ""
        auftraggeber = ""

        for bi, start in enumerate(range(0, len(images), batch_size)):
            batch = images[start : start + batch_size]
            progress = int(10 + (bi / total_batches) * 85)
            _update(
                job.id,
                progress=progress,
                message=f"Batch {bi + 1}/{total_batches} (Seiten {start + 1}-{start + len(batch)})",
            )
            parsed, _model = claude.extract_json(system=SYSTEM_PROMPT, images=batch)
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

    run_job(job_id, _runner)
