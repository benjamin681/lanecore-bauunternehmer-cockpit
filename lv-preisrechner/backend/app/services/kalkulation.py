"""Kalkulation: Position → EP (Material + Lohn + Zuschläge)."""

from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from app.models.lv import LV
from app.models.position import Position
from app.models.price_list import PriceList
from app.models.tenant import Tenant
from app.services.dna_matcher import find_best_match
from app.services.materialrezepte import Rezept, resolve_rezept

log = structlog.get_logger()


def _kalkuliere_position(
    db: Session,
    tenant: Tenant,
    price_list: PriceList,
    p: Position,
) -> None:
    """Berechnet EP und GP für eine einzelne Position."""
    rezept: Rezept | None = resolve_rezept(p.erkanntes_system, p.feuerwiderstand, p.plattentyp)

    material_ep = 0.0
    detailliste: list[dict] = []
    warnungen: list[str] = []

    if rezept:
        for mb in rezept.materialien:
            match = find_best_match(
                db=db,
                tenant_id=tenant.id,
                price_list_id=price_list.id,
                dna_pattern=mb.dna_pattern,
            )
            if match.price_entry is None:
                # Fallback: wenn optional (fallback_preis_eur gesetzt) Standard-Preis verwenden
                # Vermeidet 0€-Materialien die zu Unter-Kalkulation führen
                fallback_preis = getattr(mb, "fallback_preis_eur", None)
                if fallback_preis and fallback_preis > 0:
                    teilpreis = mb.menge_pro_einheit * fallback_preis
                    material_ep += teilpreis
                    detailliste.append(
                        {
                            "dna_pattern": mb.dna_pattern,
                            "menge": mb.menge_pro_einheit,
                            "einheit": mb.basis_einheit,
                            "preis_einheit": fallback_preis,
                            "gp": round(teilpreis, 2),
                            "quelle": "fallback",
                        }
                    )
                    continue
                # Nur bei optional=False warnen (sonst Rauschen)
                if not getattr(mb, "optional", False):
                    warnungen.append(f"Kein Preis: {mb.dna_pattern}")
                detailliste.append(
                    {
                        "dna_pattern": mb.dna_pattern,
                        "menge": mb.menge_pro_einheit,
                        "einheit": mb.basis_einheit,
                        "preis": 0.0,
                        "gp": 0.0,
                        "warnung": match.begruendung,
                    }
                )
                continue
            teilpreis = mb.menge_pro_einheit * match.preis_pro_basis
            material_ep += teilpreis
            detailliste.append(
                {
                    "dna": match.price_entry.dna,
                    "menge": mb.menge_pro_einheit,
                    "einheit": mb.basis_einheit,
                    "preis_einheit": match.preis_pro_basis,
                    "gp": round(teilpreis, 2),
                    "match_konfidenz": round(match.konfidenz, 2),
                }
            )

        lohn_stunden = rezept.zeit_h_pro_einheit
    else:
        warnungen.append(f"Kein Rezept für System '{p.erkanntes_system}'")
        lohn_stunden = 0.5 if p.einheit in ("Stk", "psch") else 0.3

    # Spezialfälle
    if p.einheit.lower() in ("h", "std", "stunden"):
        # Regiestunde: EP = Stundensatz + Zuschläge
        lohn_stunden = 1.0
        material_ep = 0.0

    lohn_ep = lohn_stunden * tenant.stundensatz_eur

    # Zuschläge: BGK + AGK + W+G auf (Material + Lohn) kumulativ
    basis = material_ep + lohn_ep
    gesamt_zuschlag_prozent = (tenant.bgk_prozent + tenant.agk_prozent + tenant.wg_prozent) / 100.0
    zuschlaege_ep = basis * gesamt_zuschlag_prozent
    ep = round(basis + zuschlaege_ep, 2)
    gp = round(ep * p.menge, 2)

    p.materialien = detailliste
    p.material_ep = round(material_ep, 2)
    p.lohn_stunden = round(lohn_stunden, 2)
    p.lohn_ep = round(lohn_ep, 2)
    p.zuschlaege_ep = round(zuschlaege_ep, 2)
    p.ep = ep
    p.gp = gp
    p.warnung = " | ".join(warnungen)[:1000]
    if warnungen:
        p.konfidenz = min(p.konfidenz, 0.6)


def kalkuliere_lv(db: Session, lv_id: str, tenant_id: str) -> LV:
    """Kalkuliert ein komplettes LV."""
    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == tenant_id).first()
    if not lv:
        raise ValueError("LV nicht gefunden")

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise ValueError("Tenant nicht gefunden")

    # Aktive Preisliste
    pl = (
        db.query(PriceList)
        .filter(
            PriceList.tenant_id == tenant_id,
            PriceList.aktiv.is_(True),
        )
        .first()
    )
    if not pl:
        raise ValueError(
            "Keine aktive Preisliste. Bitte zuerst eine Preisliste hochladen und aktivieren."
        )

    summe = 0.0
    gematcht = 0
    unsicher = 0
    for p in lv.positions:
        _kalkuliere_position(db, tenant, pl, p)
        summe += p.gp
        if p.ep > 0 and not p.warnung:
            gematcht += 1
        if p.konfidenz < 0.85:
            unsicher += 1

    lv.angebotssumme_netto = round(summe, 2)
    lv.positionen_gematcht = gematcht
    lv.positionen_unsicher = unsicher
    lv.price_list_id = pl.id
    lv.status = "calculated"
    db.commit()
    db.refresh(lv)
    log.info(
        "lv_calculated",
        lv_id=lv.id,
        summe=lv.angebotssumme_netto,
        gematcht=gematcht,
        unsicher=unsicher,
    )
    return lv
