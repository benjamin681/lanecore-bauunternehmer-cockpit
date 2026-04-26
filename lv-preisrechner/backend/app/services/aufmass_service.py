"""Aufmaß-Service (B+4.12 Iteration 4).

Business-Logik fuer das Erfassen und Abschliessen eines Aufmaßes
sowie das Erstellen eines Final-Offers auf Basis der gemessenen
Mengen.

Wichtige Invarianten:
- Aufmaß kann nur aus einem ACCEPTED Offer entstehen.
- Edits sind nur in Status IN_PROGRESS erlaubt.
- Nach FINALIZE ist das Aufmaß read-only.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.aufmass import Aufmass, AufmassPosition, AufmassStatus
from app.models.lv import LV
from app.models.offer import Offer, OfferPdfFormat, OfferStatus
from app.models.tenant import Tenant

log = structlog.get_logger(__name__)

# 19% UStr — gleiche Konstante wie offer_service, lokal definiert um
# Zirkular-Import zu vermeiden.
USTR_RATE = Decimal("0.19")


class AufmassServiceError(RuntimeError):
    """Business-Fehler im Aufmaß-Service."""


class AufmassNotEditable(AufmassServiceError):
    """Aufmaß ist im Status finalized/cancelled — keine Edits."""


def generate_aufmass_number(
    db: Session, tenant_id: str, today=None
) -> str:
    """Generiert M-yymmdd-NN eindeutig pro Tenant pro Tag."""
    today = today or datetime.now(UTC).date()
    yymmdd = today.strftime("%y%m%d")
    prefix = f"M-{yymmdd}-"
    n_existing = (
        db.query(func.count(Aufmass.id))
        .filter(
            Aufmass.tenant_id == tenant_id,
            Aufmass.aufmass_number.like(f"{prefix}%"),
        )
        .scalar()
    ) or 0
    return f"{prefix}{n_existing + 1:02d}"


def create_aufmass_from_offer(
    db: Session,
    offer: Offer,
    lv: LV,
    notes: str | None = None,
) -> Aufmass:
    """Erzeugt Aufmaß aus accepted Offer.

    - Status muss ACCEPTED sein, sonst AufmassServiceError.
    - Tenant-Konsistenz wird im Caller (Router) gepruefft.
    - Pro LV-Position wird eine AufmassPosition als Snapshot angelegt.
    - gemessene_menge initial == lv_menge -> Differenz beim Anlegen = 0.
    """
    if offer.status != OfferStatus.ACCEPTED.value:
        raise AufmassServiceError(
            f"Aufmaß kann nur aus accepted Offer entstehen "
            f"(aktueller Status: {offer.status})"
        )
    if offer.lv_id != lv.id:
        raise AufmassServiceError("Offer gehoert nicht zum LV.")

    aufmass = Aufmass(
        tenant_id=offer.tenant_id,
        lv_id=lv.id,
        source_offer_id=offer.id,
        aufmass_number=generate_aufmass_number(db, offer.tenant_id),
        status=AufmassStatus.IN_PROGRESS.value,
        internal_notes=notes,
    )
    db.add(aufmass)
    db.flush()  # ID fuer Position-FKs

    for p in lv.positions:
        lv_menge = Decimal(str(p.menge or 0))
        ep = Decimal(str(p.ep or 0))
        gp = (lv_menge * ep).quantize(Decimal("0.01"))
        db.add(
            AufmassPosition(
                aufmass_id=aufmass.id,
                lv_position_id=p.id,
                oz=p.oz or "",
                kurztext=p.kurztext or p.titel or "",
                einheit=p.einheit or "",
                lv_menge=lv_menge,
                ep=ep,
                gemessene_menge=lv_menge,  # initial gleich, vom User editierbar
                gp_lv_snapshot=gp,
                gp_aufmass=gp,
            )
        )

    log.info(
        "aufmass_created",
        aufmass_id=aufmass.id,
        aufmass_number=aufmass.aufmass_number,
        offer_id=offer.id,
        lv_id=lv.id,
        position_count=len(lv.positions),
    )
    return aufmass


def update_position_menge(
    db: Session,
    aufmass: Aufmass,
    pos: AufmassPosition,
    *,
    new_menge: float | None = None,
    notes: str | None = None,
) -> AufmassPosition:
    """Aktualisiert gemessene_menge und/oder Notiz, recomputed gp_aufmass.

    Raises:
        AufmassNotEditable: Wenn Aufmaß bereits finalized.
    """
    if aufmass.status != AufmassStatus.IN_PROGRESS.value:
        raise AufmassNotEditable(
            f"Aufmaß ist {aufmass.status} — Edits nicht moeglich."
        )
    if pos.aufmass_id != aufmass.id:
        raise AufmassServiceError("Position gehoert nicht zu diesem Aufmaß.")

    if new_menge is not None:
        menge = Decimal(str(new_menge))
        ep = Decimal(str(pos.ep or 0))
        pos.gemessene_menge = menge
        pos.gp_aufmass = (menge * ep).quantize(Decimal("0.01"))

    if notes is not None:
        # leere Strings als None speichern
        pos.notes = notes if notes.strip() else None

    return pos


def finalize_aufmass(
    db: Session,
    aufmass: Aufmass,
    user_id: str | None = None,
) -> Aufmass:
    """Setzt Aufmaß auf finalized — danach read-only."""
    if aufmass.status == AufmassStatus.FINALIZED.value:
        return aufmass  # idempotent
    if aufmass.status != AufmassStatus.IN_PROGRESS.value:
        raise AufmassServiceError(
            f"Aufmaß ist {aufmass.status} — finalize nicht moeglich."
        )

    aufmass.status = AufmassStatus.FINALIZED.value
    aufmass.finalized_at = datetime.now(UTC)
    aufmass.finalized_by = user_id

    log.info("aufmass_finalized", aufmass_id=aufmass.id, user_id=user_id)
    return aufmass


def cancel_aufmass(db: Session, aufmass: Aufmass) -> Aufmass:
    """Setzt Aufmaß auf cancelled."""
    if aufmass.status == AufmassStatus.CANCELLED.value:
        return aufmass
    if aufmass.status == AufmassStatus.FINALIZED.value:
        raise AufmassServiceError("Finalized Aufmaß kann nicht cancelled werden.")
    aufmass.status = AufmassStatus.CANCELLED.value
    return aufmass


def get_aufmass_summary(aufmass: Aufmass) -> dict:
    """Berechnet Differenz-Aggregat: gesamt + pro Hauptgruppe.

    Hauptgruppe wird als erste OZ-Komponente extrahiert ("59" aus "59.10.0010").

    Returns:
        {
          "lv_total_netto": float,
          "aufmass_total_netto": float,
          "diff_netto": float,
          "diff_brutto": float,
          "diff_pct": float | None,
          "position_count": int,
          "by_group": [
            {"group": "59", "lv_netto": ..., "aufmass_netto": ...,
             "diff_netto": ..., "position_count": ...},
            ...
          ]
        }
    """
    lv_total = Decimal("0")
    aufmass_total = Decimal("0")
    by_group: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "lv_netto": Decimal("0"),
            "aufmass_netto": Decimal("0"),
            "position_count": 0,
        }
    )

    for p in aufmass.positions:
        lv_g = Decimal(str(p.gp_lv_snapshot or 0))
        au_g = Decimal(str(p.gp_aufmass or 0))
        lv_total += lv_g
        aufmass_total += au_g

        group = (p.oz or "").split(".")[0] or "—"
        by_group[group]["lv_netto"] += lv_g
        by_group[group]["aufmass_netto"] += au_g
        by_group[group]["position_count"] += 1  # type: ignore[operator]

    diff = aufmass_total - lv_total
    diff_brutto = (diff * (Decimal("1") + USTR_RATE)).quantize(Decimal("0.01"))
    diff_pct = float(diff / lv_total * 100) if lv_total > 0 else None

    groups_sorted = sorted(by_group.keys(), key=lambda x: (x == "—", x))
    return {
        "lv_total_netto": float(lv_total.quantize(Decimal("0.01"))),
        "aufmass_total_netto": float(aufmass_total.quantize(Decimal("0.01"))),
        "diff_netto": float(diff.quantize(Decimal("0.01"))),
        "diff_brutto": float(diff_brutto),
        "diff_pct": diff_pct,
        "position_count": len(aufmass.positions),
        "by_group": [
            {
                "group": g,
                "lv_netto": float(
                    by_group[g]["lv_netto"].quantize(Decimal("0.01"))  # type: ignore[union-attr]
                ),
                "aufmass_netto": float(
                    by_group[g]["aufmass_netto"].quantize(Decimal("0.01"))  # type: ignore[union-attr]
                ),
                "diff_netto": float(
                    (
                        by_group[g]["aufmass_netto"]  # type: ignore[operator]
                        - by_group[g]["lv_netto"]
                    ).quantize(Decimal("0.01"))
                ),
                "position_count": by_group[g]["position_count"],
            }
            for g in groups_sorted
        ],
    }


def create_final_offer_from_aufmass(
    db: Session,
    aufmass: Aufmass,
    tenant: Tenant,
    user_id: str | None = None,
) -> Offer:
    """Erzeugt einen neuen Offer mit pdf_format=AUFMASS_BASIERT.

    Snapshot der gemessenen Mengen wird via offer.aufmass_id verlinkt;
    die PDF-Generierung leitet daraus die Mengen ab.

    Voraussetzung: Aufmaß ist FINALIZED.
    """
    # Lokaler Import um Zirkular-Imports zwischen offer_service <-> aufmass_service zu vermeiden.
    from app.services.offer_service import generate_offer_number

    if aufmass.status != AufmassStatus.FINALIZED.value:
        raise AufmassServiceError(
            f"Final-Offer benoetigt finalized Aufmaß "
            f"(aktuell: {aufmass.status})"
        )

    summary = get_aufmass_summary(aufmass)
    netto = Decimal(str(summary["aufmass_total_netto"]))
    brutto = (netto * (Decimal("1") + USTR_RATE)).quantize(Decimal("0.01"))

    offer_number = generate_offer_number(db, tenant.id)

    # project_id vom LV uebernehmen
    lv = db.get(LV, aufmass.lv_id)

    offer = Offer(
        tenant_id=tenant.id,
        lv_id=aufmass.lv_id,
        project_id=lv.project_id if lv else None,
        offer_number=offer_number,
        status=OfferStatus.DRAFT.value,
        offer_date=datetime.now(UTC).date(),
        betrag_netto=netto,
        betrag_brutto=brutto,
        position_count=summary["position_count"],
        pdf_format=OfferPdfFormat.AUFMASS_BASIERT.value,
        internal_notes=(
            f"Final-Offer auf Basis Aufmaß {aufmass.aufmass_number}. "
            f"Differenz zum LV: {summary['diff_netto']:+.2f} EUR netto."
        ),
        aufmass_id=aufmass.id,
    )
    db.add(offer)
    db.flush()

    # Audit-Trail-Erstinitialisierung wie bei offer_service
    from app.models.offer import OfferStatusChange

    db.add(
        OfferStatusChange(
            offer_id=offer.id,
            old_status=None,
            new_status=OfferStatus.DRAFT.value,
            changed_by=user_id,
            reason=f"final_offer_from_aufmass:{aufmass.aufmass_number}",
        )
    )

    log.info(
        "final_offer_created_from_aufmass",
        offer_id=offer.id,
        offer_number=offer_number,
        aufmass_id=aufmass.id,
        netto=str(netto),
        diff_to_lv=summary["diff_netto"],
    )
    return offer
