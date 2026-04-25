"""Offer-Service (B+4.11): Offer-Lifecycle-Logik.

Eine Offer ist ein Snapshot eines LVs zum Zeitpunkt der Erstellung.
Aenderungen am LV beeinflussen versendete Offers nicht.

Das Modul kennt vier oeffentliche Funktionen:
- :func:`create_offer_from_lv` — Offer aus LV-Snapshot erzeugen
- :func:`change_offer_status` — Status-Wechsel mit Audit-Trail
- :func:`get_offer_pdf` — PDF im gewaehlten Format zuruecksenden
- :func:`generate_offer_number` — Sequenz pro Tenant pro Tag

Der Service committed nicht selbst — der Caller (Router) ist fuer
Transaction-Boundaries verantwortlich.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lv import LV
from app.models.offer import (
    Offer,
    OfferPdfFormat,
    OfferStatus,
    OfferStatusChange,
)
from app.models.tenant import Tenant

log = structlog.get_logger(__name__)

# Brutto-Berechnung: 19 Prozent Umsatzsteuer.
USTR_RATE = Decimal("0.19")

# Erlaubte Status-Wechsel. Endzustaende rejected/expired bleiben terminal,
# accepted ist ebenfalls terminal — nur via DELETE rueckholbar.
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    OfferStatus.DRAFT.value: {
        OfferStatus.SENT.value,
        OfferStatus.REJECTED.value,
    },
    OfferStatus.SENT.value: {
        OfferStatus.ACCEPTED.value,
        OfferStatus.REJECTED.value,
        OfferStatus.NEGOTIATING.value,
        OfferStatus.EXPIRED.value,
    },
    OfferStatus.NEGOTIATING.value: {
        OfferStatus.ACCEPTED.value,
        OfferStatus.REJECTED.value,
        OfferStatus.SENT.value,
        OfferStatus.EXPIRED.value,
    },
    OfferStatus.ACCEPTED.value: set(),
    OfferStatus.REJECTED.value: set(),
    OfferStatus.EXPIRED.value: set(),
}


class OfferServiceError(RuntimeError):
    """Business-Fehler im Offer-Service."""


class InvalidOfferTransition(OfferServiceError):
    """Status-Wechsel ist nicht erlaubt."""


def generate_offer_number(db: Session, tenant_id: str, today: date | None = None) -> str:
    """Generiert eine A-yymmdd-NN-Nummer eindeutig pro Tenant pro Tag.

    Sequenz wird durch SELECT count + Pattern-LIKE ermittelt. Race-Conditions
    waeren theoretisch moeglich, der Tenant-Offer-Number-Index ist UNIQUE,
    sodass eine Kollision in einen klaren IntegrityError laeuft. Der Caller
    kann dann retry'en.
    """
    today = today or datetime.now(UTC).date()
    yymmdd = today.strftime("%y%m%d")
    prefix = f"A-{yymmdd}-"

    n_existing = (
        db.query(func.count(Offer.id))
        .filter(
            Offer.tenant_id == tenant_id,
            Offer.offer_number.like(f"{prefix}%"),
        )
        .scalar()
    ) or 0
    seq = n_existing + 1
    return f"{prefix}{seq:02d}"


def create_offer_from_lv(
    db: Session,
    lv: LV,
    tenant: Tenant,
    pdf_format: OfferPdfFormat,
    user_id: str | None = None,
    notes: str | None = None,
) -> Offer:
    """Erzeugt eine neue Offer als Snapshot des LVs.

    Status startet bei DRAFT. valid_until bleibt None, wird beim Wechsel
    auf SENT gesetzt aus tenant.default_offer_validity_days.

    Args:
        db: Aktive Session, Caller committed.
        lv: Hydratiertes LV.
        tenant: Hydrated Tenant.
        pdf_format: Welches PDF-Layout beim Download generiert werden soll.
        user_id: User, der die Offer anlegt — fuer Audit-Trail.
        notes: Optionale interne Notiz beim Erstellen.

    Returns:
        Die neu erzeugte Offer (noch nicht committed).
    """
    if lv.tenant_id != tenant.id:
        raise OfferServiceError(
            "LV gehoert nicht zum Tenant — interner Fehler."
        )

    netto = Decimal(str(lv.angebotssumme_netto or 0))
    brutto = (netto * (Decimal("1") + USTR_RATE)).quantize(Decimal("0.01"))

    offer_number = generate_offer_number(db, tenant.id)

    offer = Offer(
        tenant_id=tenant.id,
        lv_id=lv.id,
        project_id=lv.project_id,
        offer_number=offer_number,
        status=OfferStatus.DRAFT.value,
        offer_date=datetime.now(UTC).date(),
        betrag_netto=netto,
        betrag_brutto=brutto,
        position_count=lv.positionen_gesamt or 0,
        pdf_format=pdf_format.value,
        internal_notes=notes,
    )
    db.add(offer)
    db.flush()  # ID fuer das Audit-Insert

    db.add(
        OfferStatusChange(
            offer_id=offer.id,
            old_status=None,
            new_status=OfferStatus.DRAFT.value,
            changed_by=user_id,
            reason="created",
        )
    )

    log.info(
        "offer_created",
        offer_id=offer.id,
        offer_number=offer_number,
        tenant_id=tenant.id,
        lv_id=lv.id,
        netto=str(netto),
        pdf_format=pdf_format.value,
    )
    return offer


def change_offer_status(
    db: Session,
    offer: Offer,
    tenant: Tenant,
    new_status: OfferStatus,
    user_id: str | None = None,
    reason: str | None = None,
    on_date: date | None = None,
) -> Offer:
    """Wechselt den Status einer Offer mit Audit-Trail.

    Setzt zusaetzlich:
    - sent_date + valid_until beim Wechsel auf SENT
      (valid_until = sent_date + tenant.default_offer_validity_days)
    - accepted_date / rejected_date bei den jeweiligen Endzustaenden

    Raises:
        InvalidOfferTransition: Bei nicht erlaubtem Wechsel.
    """
    old = offer.status
    new = new_status.value

    if old == new:
        # Idempotent — kein Audit-Eintrag, keine Aenderung.
        return offer

    allowed = _ALLOWED_TRANSITIONS.get(old, set())
    if new not in allowed:
        raise InvalidOfferTransition(
            f"Wechsel von '{old}' zu '{new}' nicht erlaubt."
        )

    today = on_date or datetime.now(UTC).date()
    offer.status = new

    if new == OfferStatus.SENT.value:
        offer.sent_date = today
        validity_days = tenant.default_offer_validity_days or 30
        offer.valid_until = today + timedelta(days=validity_days)
    elif new == OfferStatus.ACCEPTED.value:
        offer.accepted_date = today
    elif new == OfferStatus.REJECTED.value:
        offer.rejected_date = today

    db.add(
        OfferStatusChange(
            offer_id=offer.id,
            old_status=old,
            new_status=new,
            changed_by=user_id,
            reason=reason,
        )
    )

    log.info(
        "offer_status_changed",
        offer_id=offer.id,
        old=old,
        new=new,
        user_id=user_id,
    )
    return offer


def get_offer_pdf(offer: Offer, lv: LV, tenant: Tenant) -> bytes:
    """Generiert das PDF der Offer in dem zur Erstellung gewaehlten Format.

    Delegiert an die existing PDF-Services. Es wird KEIN Snapshot
    rekonstruiert — das aktuelle LV ist Quelle. Wenn das LV nach
    Versand veraendert wird, sollte fuer eine Korrektur eine neue
    Offer angelegt werden.
    """
    if offer.pdf_format == OfferPdfFormat.ORIGINAL_LV_FILLED.value:
        from app.services.lv_original_filled import generate_original_filled_pdf

        return generate_original_filled_pdf(lv)

    # Default / EIGENES_LAYOUT
    from app.services.lv_pdf_export import generate_angebot_pdf

    return generate_angebot_pdf(lv, tenant)
