"""Invoice-Service (B+4.13 Iteration 5).

Business-Logik fuer Rechnungs-Lifecycle.

Wichtige Invarianten:
- Invoice kann nur aus accepted Offer ODER aus draft Final-Offer
  (pdf_format=aufmass_basiert) entstehen.
- Numerierung R-yyyy-NN ist durchlaufend pro Tenant pro Jahr
  (steuerlich relevant), UNIQUE-Index.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.invoice import (
    Invoice,
    InvoiceStatus,
    InvoiceStatusChange,
    InvoiceType,
)
from app.models.offer import Offer, OfferPdfFormat, OfferStatus
from app.models.tenant import Tenant

log = structlog.get_logger(__name__)

# 19% UStr
USTR_RATE = Decimal("0.19")

# Erlaubte Status-Transitions
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    InvoiceStatus.DRAFT.value: {
        InvoiceStatus.SENT.value,
        InvoiceStatus.CANCELLED.value,
    },
    InvoiceStatus.SENT.value: {
        InvoiceStatus.PAID.value,
        InvoiceStatus.PARTIALLY_PAID.value,
        InvoiceStatus.OVERDUE.value,
        InvoiceStatus.CANCELLED.value,
    },
    InvoiceStatus.PARTIALLY_PAID.value: {
        InvoiceStatus.PAID.value,
        InvoiceStatus.OVERDUE.value,
        InvoiceStatus.CANCELLED.value,
    },
    InvoiceStatus.OVERDUE.value: {
        InvoiceStatus.PAID.value,
        InvoiceStatus.PARTIALLY_PAID.value,
        InvoiceStatus.CANCELLED.value,
    },
    InvoiceStatus.PAID.value: set(),
    InvoiceStatus.CANCELLED.value: set(),
}


class InvoiceServiceError(RuntimeError):
    """Business-Fehler im Invoice-Service."""


class InvalidInvoiceTransition(InvoiceServiceError):
    """Status-Wechsel ist nicht erlaubt."""


def generate_invoice_number(
    db: Session, tenant_id: str, today: date | None = None
) -> str:
    """Generiert R-yyyy-NN durchlaufend pro Tenant pro Jahr."""
    today = today or datetime.now(UTC).date()
    yyyy = today.strftime("%Y")
    prefix = f"R-{yyyy}-"
    n_existing = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.invoice_number.like(f"{prefix}%"),
        )
        .scalar()
    ) or 0
    return f"{prefix}{n_existing + 1:02d}"


def create_invoice_from_offer(
    db: Session,
    offer: Offer,
    tenant: Tenant,
    *,
    invoice_type: InvoiceType = InvoiceType.SCHLUSSRECHNUNG,
    user_id: str | None = None,
    notes: str | None = None,
) -> Invoice:
    """Erzeugt Rechnung aus accepted Offer oder draft AUFMASS_BASIERT-Offer.

    Schlussrechnung-Default: ein Final-Offer (pdf_format=aufmass_basiert)
    auch im Status draft ist als Quelle erlaubt — typischer Workflow.

    Raises:
        InvoiceServiceError: Wenn Offer-Status nicht passend.
    """
    # Akzeptierte Quellen:
    # 1. Jeder accepted Offer
    # 2. Ein draft Offer mit pdf_format=aufmass_basiert (Final-Offer)
    is_accepted = offer.status == OfferStatus.ACCEPTED.value
    is_draft_final = (
        offer.status == OfferStatus.DRAFT.value
        and offer.pdf_format == OfferPdfFormat.AUFMASS_BASIERT.value
    )
    if not (is_accepted or is_draft_final):
        raise InvoiceServiceError(
            f"Rechnung benoetigt accepted Offer oder draft Final-Offer "
            f"(aktueller Status: {offer.status}, format: {offer.pdf_format})"
        )

    netto = Decimal(str(offer.betrag_netto or 0))
    ust = (netto * USTR_RATE).quantize(Decimal("0.01"))
    brutto = (netto + ust).quantize(Decimal("0.01"))

    invoice_number = generate_invoice_number(db, tenant.id)

    invoice = Invoice(
        tenant_id=tenant.id,
        lv_id=offer.lv_id,
        source_offer_id=offer.id,
        source_aufmass_id=offer.aufmass_id,
        invoice_number=invoice_number,
        invoice_type=invoice_type.value,
        status=InvoiceStatus.DRAFT.value,
        invoice_date=datetime.now(UTC).date(),
        betrag_netto=netto,
        betrag_ust=ust,
        betrag_brutto=brutto,
        position_count=offer.position_count,
        internal_notes=notes,
    )
    db.add(invoice)
    db.flush()

    db.add(
        InvoiceStatusChange(
            invoice_id=invoice.id,
            old_status=None,
            new_status=InvoiceStatus.DRAFT.value,
            changed_by=user_id,
            reason=f"created_from_offer:{offer.offer_number}",
        )
    )
    log.info(
        "invoice_created",
        invoice_id=invoice.id,
        invoice_number=invoice_number,
        offer_id=offer.id,
        tenant_id=tenant.id,
        netto=str(netto),
    )
    return invoice


def change_invoice_status(
    db: Session,
    invoice: Invoice,
    tenant: Tenant,
    new_status: InvoiceStatus,
    *,
    user_id: str | None = None,
    reason: str | None = None,
    on_date: date | None = None,
) -> Invoice:
    """Status-Wechsel mit Audit-Trail-Eintrag.

    Setzt zusaetzlich:
    - sent_date + due_date beim Wechsel auf SENT
      (due_date = sent_date + tenant.default_payment_terms_days)
    - paid_date bei PAID
    """
    old = invoice.status
    new = new_status.value
    if old == new:
        return invoice
    allowed = _ALLOWED_TRANSITIONS.get(old, set())
    if new not in allowed:
        raise InvalidInvoiceTransition(
            f"Wechsel von '{old}' zu '{new}' nicht erlaubt."
        )
    today = on_date or datetime.now(UTC).date()
    invoice.status = new

    if new == InvoiceStatus.SENT.value:
        invoice.sent_date = today
        days = tenant.default_payment_terms_days or 14
        invoice.due_date = today + timedelta(days=days)
    elif new == InvoiceStatus.PAID.value:
        invoice.paid_date = today

    db.add(
        InvoiceStatusChange(
            invoice_id=invoice.id,
            old_status=old,
            new_status=new,
            changed_by=user_id,
            reason=reason,
        )
    )
    log.info(
        "invoice_status_changed",
        invoice_id=invoice.id,
        old=old, new=new, user_id=user_id,
    )
    return invoice


def record_payment(
    db: Session,
    invoice: Invoice,
    *,
    amount: float,
    payment_date: date | None = None,
    user_id: str | None = None,
    note: str | None = None,
) -> Invoice:
    """Erfasst Zahlungseingang. Setzt Status automatisch.

    - paid_amount kumuliert.
    - amount >= betrag_brutto: Status -> PAID, paid_date gesetzt.
    - 0 < amount < betrag_brutto: Status -> PARTIALLY_PAID.
    - amount <= 0: ValueError.
    """
    if amount <= 0:
        raise InvoiceServiceError("Zahlungsbetrag muss > 0 sein.")
    if invoice.status in (InvoiceStatus.CANCELLED.value, InvoiceStatus.DRAFT.value):
        raise InvoiceServiceError(
            f"Zahlung nicht moeglich im Status {invoice.status}."
        )
    pay_date = payment_date or datetime.now(UTC).date()
    new_total = (
        Decimal(str(invoice.paid_amount or 0)) + Decimal(str(amount))
    ).quantize(Decimal("0.01"))
    invoice.paid_amount = new_total

    brutto = Decimal(str(invoice.betrag_brutto or 0))
    old = invoice.status
    if new_total >= brutto:
        invoice.status = InvoiceStatus.PAID.value
        invoice.paid_date = pay_date
        new = InvoiceStatus.PAID.value
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID.value
        new = InvoiceStatus.PARTIALLY_PAID.value

    audit_reason = (
        f"payment:{amount:.2f} cumulative:{new_total} "
        f"on:{pay_date.isoformat()}"
    )
    if note:
        audit_reason = f"{audit_reason} note:{note}"
    db.add(
        InvoiceStatusChange(
            invoice_id=invoice.id,
            old_status=old,
            new_status=new,
            changed_by=user_id,
            reason=audit_reason,
        )
    )
    log.info(
        "invoice_payment_recorded",
        invoice_id=invoice.id,
        amount=amount,
        cumulative=str(new_total),
        new_status=new,
    )
    return invoice


def check_overdue_invoices(
    db: Session, tenant_id: str, *, today: date | None = None
) -> int:
    """Setzt SENT-Invoices mit due_date < heute auf OVERDUE.

    Returns:
        Anzahl der aktualisierten Invoices.
    """
    today = today or datetime.now(UTC).date()
    rows = (
        db.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.SENT.value,
            Invoice.due_date != None,  # noqa: E711
            Invoice.due_date < today,
        )
        .all()
    )
    n = 0
    for inv in rows:
        old = inv.status
        inv.status = InvoiceStatus.OVERDUE.value
        db.add(
            InvoiceStatusChange(
                invoice_id=inv.id,
                old_status=old,
                new_status=InvoiceStatus.OVERDUE.value,
                changed_by=None,
                reason=f"auto_overdue_check:due_date={inv.due_date.isoformat()}",
            )
        )
        n += 1
    if n > 0:
        log.info("invoice_overdue_detected", tenant_id=tenant_id, count=n)
    return n


def get_finance_overview(db: Session, tenant_id: str) -> dict:
    """Tenant-weites Finanz-Aggregat fuer das Cockpit."""
    today = datetime.now(UTC).date()
    year_start = date(today.year, 1, 1)

    open_q = db.query(
        func.count(Invoice.id), func.coalesce(func.sum(Invoice.betrag_brutto), 0)
    ).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(
            [
                InvoiceStatus.SENT.value,
                InvoiceStatus.PARTIALLY_PAID.value,
                InvoiceStatus.OVERDUE.value,
            ]
        ),
    )
    open_count, open_brutto = open_q.one()

    overdue_q = db.query(
        func.count(Invoice.id), func.coalesce(func.sum(Invoice.betrag_brutto), 0)
    ).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status == InvoiceStatus.OVERDUE.value,
    )
    overdue_count, overdue_brutto = overdue_q.one()

    paid_year = (
        db.query(func.coalesce(func.sum(Invoice.paid_amount), 0))
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.PAID.value,
            Invoice.paid_date != None,  # noqa: E711
            Invoice.paid_date >= year_start,
        )
        .scalar()
    ) or 0

    return {
        "offene_rechnungen_count": int(open_count or 0),
        "offene_summe_brutto": float(Decimal(str(open_brutto or 0))),
        "ueberfaellige_count": int(overdue_count or 0),
        "ueberfaellige_summe_brutto": float(Decimal(str(overdue_brutto or 0))),
        "gezahlte_summe_jahr_aktuell": float(Decimal(str(paid_year))),
        "year": today.year,
    }


def list_overdue_invoices(db: Session, tenant_id: str) -> list[dict]:
    """Liste aller ueberfaelligen Rechnungen mit days_overdue + next_dunning_due."""
    today = datetime.now(UTC).date()
    rows = (
        db.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.OVERDUE.value,
        )
        .order_by(Invoice.due_date.asc())
        .all()
    )
    out = []
    for inv in rows:
        days_overdue = (today - inv.due_date).days if inv.due_date else None
        # next_dunning_due heuristik: wenn keine Mahnung -> sofort,
        # sonst due_date der hoechsten existierenden Mahnung
        if inv.dunnings:
            highest = max(inv.dunnings, key=lambda d: d.dunning_level)
            next_due = highest.due_date.isoformat() if highest.due_date else None
            highest_level = highest.dunning_level
        else:
            next_due = today.isoformat()
            highest_level = 0
        out.append(
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "betrag_brutto": float(inv.betrag_brutto),
                "paid_amount": float(inv.paid_amount or 0),
                "open_amount": float(
                    Decimal(str(inv.betrag_brutto)) - Decimal(str(inv.paid_amount or 0))
                ),
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": days_overdue,
                "highest_dunning_level": highest_level,
                "next_dunning_due": next_due,
                "lv_id": inv.lv_id,
            }
        )
    return out
