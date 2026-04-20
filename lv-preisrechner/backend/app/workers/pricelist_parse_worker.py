"""Background-Worker für das Parsen einer SupplierPriceList (B+2).

Orchestriert die Status-Uebergaenge:
  PENDING_PARSE -> PARSING -> PARSED / ERROR

Wird aus FastAPI-BackgroundTasks aufgerufen. Nutzt SessionLocal() fuer eine
eigene DB-Session (Request-Session ist im Background nicht verfuegbar).

Retry-Policy: max 2 Versuche bei transienten Fehlern (ConnectionError,
TimeoutError). Andere Exceptions werden nicht retried.
"""

from __future__ import annotations

import time

import structlog

from app.core.database import SessionLocal
from app.models.pricing import PricelistStatus, SupplierPriceList
from app.services.pricelist_parser import ParseResult, PricelistParser

log = structlog.get_logger()

_TRANSIENT_EXCEPTIONS = (ConnectionError, TimeoutError)
_MAX_RETRIES = 2
_RETRY_DELAY_S = 3.0


def run_pricelist_parse(pricelist_id: str) -> None:
    """Background-Entry-Point.

    Verwaltet Status + Retry-Logik. parsing-Errors werden als parse_error
    in der DB persistiert.
    """
    log.info("pricelist_worker_start", pricelist_id=pricelist_id)
    _set_status(pricelist_id, PricelistStatus.PARSING.value, parse_error=None)

    attempt = 0
    last_exc: Exception | None = None
    while attempt <= _MAX_RETRIES:
        attempt += 1
        try:
            result = _parse_once(pricelist_id)
            _set_status(
                pricelist_id,
                PricelistStatus.PARSED.value,
                parse_error=None,
            )
            log.info(
                "pricelist_worker_done",
                pricelist_id=pricelist_id,
                attempt=attempt,
                parsed=result.parsed_entries,
                skipped=result.skipped_entries,
                needs_review=result.needs_review_count,
                avg_confidence=round(result.avg_confidence, 3),
            )
            return
        except _TRANSIENT_EXCEPTIONS as exc:
            last_exc = exc
            log.warning(
                "pricelist_worker_transient_error",
                pricelist_id=pricelist_id,
                attempt=attempt,
                error=str(exc),
            )
            if attempt <= _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_S * attempt)
                continue
        except Exception as exc:  # noqa: BLE001 — final error handler
            last_exc = exc
            log.error(
                "pricelist_worker_failed",
                pricelist_id=pricelist_id,
                attempt=attempt,
                error=str(exc),
            )
            break

    # Alle Versuche fehlgeschlagen
    err_msg = f"Parse fehlgeschlagen nach {attempt} Versuch(en): {last_exc}"
    _set_status(
        pricelist_id,
        PricelistStatus.ERROR.value,
        parse_error=err_msg[:2000],
    )


def _parse_once(pricelist_id: str) -> ParseResult:
    """Einen Parse-Durchlauf mit eigener DB-Session."""
    with SessionLocal() as db:
        parser = PricelistParser(db=db)
        return parser.parse(pricelist_id)


def _set_status(pricelist_id: str, status: str, *, parse_error: str | None) -> None:
    """Status-Uebergang in eigener Session (atomar).

    parse_error=None bedeutet: Feld wird explizit gecleart."""
    with SessionLocal() as db:
        pl = db.get(SupplierPriceList, pricelist_id)
        if pl is None:
            log.warning("pricelist_status_update_notfound", pricelist_id=pricelist_id)
            return
        pl.status = status
        if parse_error is None:
            pl.parse_error = None
        else:
            pl.parse_error = parse_error
        db.commit()
