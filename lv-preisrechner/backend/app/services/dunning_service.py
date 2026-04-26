"""Dunning-Service (B+4.13 Iteration 5).

Eskalierende Mahnstufen-Logik:
  Stufe 1 — freundliche Erinnerung,  7 Tage Frist,    0 EUR Gebuehr
  Stufe 2 — ernste Mahnung,         14 Tage Frist,   5 EUR Gebuehr
  Stufe 3 — letzte Mahnung,         21 Tage Frist,  15 EUR Gebuehr
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy.orm import Session

from app.models.invoice import Dunning, DunningStatus, Invoice, InvoiceStatus

log = structlog.get_logger(__name__)


# Konfig pro Stufe: (Frist-Tage, Gebuehr in EUR)
DUNNING_CONFIG: dict[int, tuple[int, Decimal]] = {
    1: (7, Decimal("0.00")),
    2: (14, Decimal("5.00")),
    3: (21, Decimal("15.00")),
}


class DunningServiceError(RuntimeError):
    """Business-Fehler im Dunning-Service."""


def create_dunning(
    db: Session,
    invoice: Invoice,
    *,
    today: date | None = None,
    notes: str | None = None,
) -> Dunning:
    """Erzeugt die naechste Mahnstufe fuer eine ueberfaellige Rechnung.

    - Invoice muss im Status overdue oder partially_paid sein.
    - Maximal 3 Mahnstufen.
    - Stufe = max(existing) + 1.

    Raises:
        DunningServiceError: Bei nicht-zulaessigem Status oder zu vielen
            Mahnungen.
    """
    if invoice.status not in (
        InvoiceStatus.OVERDUE.value,
        InvoiceStatus.PARTIALLY_PAID.value,
    ):
        raise DunningServiceError(
            f"Mahnung nur fuer overdue/partially_paid moeglich "
            f"(aktuell: {invoice.status})"
        )

    existing_levels = sorted(d.dunning_level for d in invoice.dunnings)
    next_level = (existing_levels[-1] + 1) if existing_levels else 1
    if next_level > 3:
        raise DunningServiceError(
            "Maximal 3 Mahnstufen — weitere Schritte (Inkasso) ausserhalb des Systems."
        )
    if next_level not in DUNNING_CONFIG:
        raise DunningServiceError(f"Unbekannte Mahnstufe {next_level}")

    today = today or datetime.now(UTC).date()
    days, fee = DUNNING_CONFIG[next_level]

    dunning = Dunning(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice.id,
        dunning_level=next_level,
        dunning_date=today,
        due_date=today + timedelta(days=days),
        mahngebuehr_betrag=fee,
        mahnzinsen_betrag=Decimal("0"),
        status=DunningStatus.DRAFT.value,
        internal_notes=notes,
    )
    db.add(dunning)
    log.info(
        "dunning_created",
        invoice_id=invoice.id,
        level=next_level,
        due_date=dunning.due_date.isoformat(),
        fee=str(fee),
    )
    return dunning


def mark_dunning_sent(
    db: Session, dunning: Dunning, *, today: date | None = None
) -> Dunning:
    """Setzt Status auf SENT (UI-only fuer jetzt)."""
    if dunning.status != DunningStatus.DRAFT.value:
        return dunning
    dunning.status = DunningStatus.SENT.value
    return dunning
