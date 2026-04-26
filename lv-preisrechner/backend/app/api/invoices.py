"""Invoice + Dunning + Finance-API (B+4.13 Iteration 5).

Routen:
- POST   /offers/{offer_id}/invoice               Rechnung aus Offer
- GET    /lvs/{lv_id}/invoices                    Liste pro LV
- GET    /invoices/{id}                           Detail mit History + Mahnungen
- PATCH  /invoices/{id}/status                    Status-Wechsel
- POST   /invoices/{id}/payments                  Zahlungseingang erfassen
- GET    /invoices/{id}/pdf                       Rechnungs-PDF
- POST   /invoices/{id}/dunnings                  Naechste Mahnstufe
- GET    /invoices/{id}/dunnings/{dunning_id}/pdf Mahnungs-PDF
- POST   /invoices/{id}/email                     Mailto-Compose-Link (Bonus)

- GET    /finance/overview                        Tenant-weite Aggregate
- GET    /finance/overdue-invoices                Liste ueberfaellig
- POST   /finance/check-overdue                   Cron-Hilfsendpoint
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import CurrentUser, DbSession
from app.models.aufmass import Aufmass
from app.models.invoice import Dunning, Invoice, InvoiceStatus
from app.models.lv import LV
from app.models.offer import Offer
from app.models.tenant import Tenant
from app.schemas.invoice import (
    DunningCreate,
    DunningOut,
    EmailDraftOut,
    FinanceOverview,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceOut,
    InvoiceStatusChangeOut,
    InvoiceStatusUpdate,
    OverdueInvoiceRow,
    PaymentCreate,
)
from app.services.dunning_pdf import generate_dunning_pdf
from app.services.dunning_service import DunningServiceError, create_dunning
from app.services.invoice_pdf import generate_invoice_pdf
from app.services.invoice_service import (
    InvalidInvoiceTransition,
    InvoiceServiceError,
    change_invoice_status,
    check_overdue_invoices,
    create_invoice_from_offer,
    get_finance_overview,
    list_overdue_invoices,
    record_payment,
)

# --------------------------------------------------------------------------- #
# Sub-routers
# --------------------------------------------------------------------------- #
offer_invoice_router = APIRouter(tags=["invoices"])
invoices_router = APIRouter(prefix="/invoices", tags=["invoices"])
finance_router = APIRouter(prefix="/finance", tags=["finance"])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_offer(db, offer_id: str, tenant_id: str) -> Offer:
    o = (
        db.query(Offer)
        .filter(Offer.id == offer_id, Offer.tenant_id == tenant_id)
        .first()
    )
    if o is None:
        raise HTTPException(status_code=404, detail="Offer nicht gefunden")
    return o


def _load_lv(db, lv_id: str, tenant_id: str) -> LV:
    lv = (
        db.query(LV)
        .filter(LV.id == lv_id, LV.tenant_id == tenant_id)
        .first()
    )
    if lv is None:
        raise HTTPException(status_code=404, detail="LV nicht gefunden")
    return lv


def _load_invoice(db, invoice_id: str, tenant_id: str) -> Invoice:
    inv = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
        .first()
    )
    if inv is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return inv


def _detail_payload(inv: Invoice) -> dict:
    return {
        **InvoiceOut.model_validate(inv).model_dump(),
        "status_history": [
            InvoiceStatusChangeOut.model_validate(c) for c in inv.status_changes
        ],
        "dunnings": [DunningOut.model_validate(d) for d in inv.dunnings],
    }


# --------------------------------------------------------------------------- #
# /offers/{offer_id}/invoice + /lvs/{lv_id}/invoices
# --------------------------------------------------------------------------- #
@offer_invoice_router.post(
    "/offers/{offer_id}/invoice",
    response_model=InvoiceDetail,
    status_code=201,
)
def create_invoice(
    offer_id: str,
    payload: InvoiceCreate,
    user: CurrentUser,
    db: DbSession,
) -> InvoiceDetail:
    offer = _load_offer(db, offer_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")
    try:
        inv = create_invoice_from_offer(
            db,
            offer,
            tenant,
            invoice_type=payload.invoice_type,
            user_id=user.id,
            notes=payload.internal_notes,
        )
        db.commit()
        db.refresh(inv)
    except InvoiceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return InvoiceDetail.model_validate(_detail_payload(inv))


@offer_invoice_router.get(
    "/lvs/{lv_id}/invoices",
    response_model=list[InvoiceOut],
)
def list_invoices_for_lv(
    lv_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[InvoiceOut]:
    _load_lv(db, lv_id, user.tenant_id)
    rows = (
        db.query(Invoice)
        .filter(Invoice.lv_id == lv_id, Invoice.tenant_id == user.tenant_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    return [InvoiceOut.model_validate(r) for r in rows]


# --------------------------------------------------------------------------- #
# /invoices/{id}/...  — statische Pfade vor dem Catch-All
# --------------------------------------------------------------------------- #
@invoices_router.patch(
    "/{invoice_id}/status", response_model=InvoiceDetail
)
def patch_status(
    invoice_id: str,
    payload: InvoiceStatusUpdate,
    user: CurrentUser,
    db: DbSession,
) -> InvoiceDetail:
    inv = _load_invoice(db, invoice_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")
    try:
        change_invoice_status(
            db, inv, tenant, payload.status,
            user_id=user.id, reason=payload.reason, on_date=payload.on_date,
        )
        db.commit()
        db.refresh(inv)
    except InvalidInvoiceTransition as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return InvoiceDetail.model_validate(_detail_payload(inv))


@invoices_router.post(
    "/{invoice_id}/payments", response_model=InvoiceDetail
)
def post_payment(
    invoice_id: str,
    payload: PaymentCreate,
    user: CurrentUser,
    db: DbSession,
) -> InvoiceDetail:
    inv = _load_invoice(db, invoice_id, user.tenant_id)
    try:
        record_payment(
            db, inv,
            amount=payload.amount,
            payment_date=payload.payment_date,
            user_id=user.id,
            note=payload.note,
        )
        db.commit()
        db.refresh(inv)
    except InvoiceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    return InvoiceDetail.model_validate(_detail_payload(inv))


@invoices_router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: str,
    user: CurrentUser,
    db: DbSession,
    inline: bool = Query(default=False),
):
    inv = _load_invoice(db, invoice_id, user.tenant_id)
    lv = _load_lv(db, inv.lv_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")
    try:
        pdf = generate_invoice_pdf(inv, lv, tenant, db=db)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    filename = f"{inv.invoice_number}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )


@invoices_router.post(
    "/{invoice_id}/dunnings",
    response_model=DunningOut,
    status_code=201,
)
def post_dunning(
    invoice_id: str,
    payload: DunningCreate,
    user: CurrentUser,
    db: DbSession,
) -> DunningOut:
    inv = _load_invoice(db, invoice_id, user.tenant_id)
    try:
        d = create_dunning(db, inv, notes=payload.internal_notes)
        db.commit()
        db.refresh(d)
    except DunningServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return DunningOut.model_validate(d)


@invoices_router.get("/{invoice_id}/dunnings/{dunning_id}/pdf")
def download_dunning_pdf(
    invoice_id: str,
    dunning_id: str,
    user: CurrentUser,
    db: DbSession,
    inline: bool = Query(default=False),
):
    inv = _load_invoice(db, invoice_id, user.tenant_id)
    d = (
        db.query(Dunning)
        .filter(Dunning.id == dunning_id, Dunning.invoice_id == invoice_id)
        .first()
    )
    if d is None:
        raise HTTPException(status_code=404, detail="Mahnung nicht gefunden")
    lv = _load_lv(db, inv.lv_id, user.tenant_id)
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht gefunden")
    try:
        pdf = generate_dunning_pdf(d, inv, lv, tenant)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    filename = f"Mahnung-Stufe{d.dunning_level}-{inv.invoice_number}.pdf"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )


@invoices_router.post("/{invoice_id}/email", response_model=EmailDraftOut)
def email_draft(
    invoice_id: str,
    user: CurrentUser,
    db: DbSession,
) -> EmailDraftOut:
    """Bonus: Mailto-Compose-Link mit voraus gefuelltem Subject + Body.

    SMTP-Versand (Anhang) ist Iteration 6 oder spaeter — hier nur Vorbereitung.
    """
    inv = _load_invoice(db, invoice_id, user.tenant_id)
    lv = _load_lv(db, inv.lv_id, user.tenant_id)

    # Empfaenger: aus dem Customer ableiten falls vorhanden, sonst leer
    to: str | None = None
    if lv.project_id is not None:
        from app.models.customer import Customer, Project

        proj = db.get(Project, lv.project_id)
        if proj is not None:
            cust = db.get(Customer, proj.customer_id)
            if cust is not None and cust.email:
                to = cust.email

    subject = f"Rechnung {inv.invoice_number}"
    if lv.projekt_name:
        subject += f" — {lv.projekt_name}"

    due = inv.due_date.strftime("%d.%m.%Y") if inv.due_date else "—"
    body = (
        f"Sehr geehrte Damen und Herren,\n\n"
        f"anbei senden wir Ihnen unsere Rechnung {inv.invoice_number} "
        f"ueber {inv.betrag_brutto:.2f} EUR brutto.\n\n"
        f"Faelligkeit: {due}\n\n"
        f"Hinweis: Bitte das PDF aus Kalkulane an diese Mail anhaengen.\n\n"
        f"Mit freundlichen Gruessen"
    )
    mailto = (
        f"mailto:{to or ''}"
        f"?subject={quote(subject)}&body={quote(body)}"
    )
    return EmailDraftOut(mailto=mailto, subject=subject, body=body, to=to)


@invoices_router.get(
    "/{invoice_id}", response_model=InvoiceDetail
)
def get_invoice(
    invoice_id: str,
    user: CurrentUser,
    db: DbSession,
) -> InvoiceDetail:
    inv = _load_invoice(db, invoice_id, user.tenant_id)
    return InvoiceDetail.model_validate(_detail_payload(inv))


# --------------------------------------------------------------------------- #
# Finance
# --------------------------------------------------------------------------- #
@finance_router.get("/overview", response_model=FinanceOverview)
def overview(
    user: CurrentUser,
    db: DbSession,
) -> FinanceOverview:
    return FinanceOverview.model_validate(get_finance_overview(db, user.tenant_id))


@finance_router.get(
    "/overdue-invoices", response_model=list[OverdueInvoiceRow]
)
def overdue(
    user: CurrentUser,
    db: DbSession,
) -> list[OverdueInvoiceRow]:
    rows = list_overdue_invoices(db, user.tenant_id)
    return [OverdueInvoiceRow.model_validate(r) for r in rows]


@finance_router.post(
    "/check-overdue", response_model=dict[str, int]
)
def check_overdue(
    user: CurrentUser,
    db: DbSession,
) -> dict[str, int]:
    """Setzt SENT-Rechnungen mit ueberschrittener Faelligkeit auf OVERDUE.

    Wird vom Frontend beim Laden des Cockpits aufgerufen, kann auch von
    einem Cron eingebunden werden.
    """
    n = check_overdue_invoices(db, user.tenant_id)
    db.commit()
    return {"updated": n}
