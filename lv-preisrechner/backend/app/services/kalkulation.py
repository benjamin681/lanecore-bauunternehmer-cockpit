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
    fehlende_pflicht_materialien: list[str] = []
    angebotenes_fabrikat_parts: list[str] = []  # Sammelt Hersteller+Produkt aus Matches

    if rezept:
        for mb in rezept.materialien:
            match = find_best_match(
                db=db,
                tenant_id=tenant.id,
                price_list_id=price_list.id,
                dna_pattern=mb.dna_pattern,
            )
            if match.price_entry is None:
                # KEIN Fallback-Preis mehr (bewusste Entscheidung: keine Schein-Genauigkeit).
                # Stattdessen: Position als manuell-zu-pruefen markieren.
                if not getattr(mb, "optional", False):
                    fehlende_pflicht_materialien.append(mb.dna_pattern)
                    warnungen.append(f"Kein Preis in Preisliste: {mb.dna_pattern}")
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
            # Hauptmaterial fuer "Angebotenes Fabrikat" (erstes m2-Material bei Waenden/Decken)
            if mb.basis_einheit == "m²" and match.price_entry.hersteller:
                produkt = match.price_entry.produktname or ""
                herst = match.price_entry.hersteller or ""
                combo = f"{herst} {produkt}".strip()
                if combo and combo not in angebotenes_fabrikat_parts:
                    angebotenes_fabrikat_parts.append(combo)
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
        warnungen.append(f"Kein Rezept fuer System '{p.erkanntes_system}' - manuelle Pruefung noetig")
        fehlende_pflicht_materialien.append("kein_rezept")
        lohn_stunden = 0.0  # kein Pseudo-Lohn wenn kein Rezept

    # Spezialfälle
    if p.einheit.lower() in ("h", "std", "stunden"):
        # Regiestunde: EP = Stundensatz + Zuschläge
        lohn_stunden = 1.0
        material_ep = 0.0
        fehlende_pflicht_materialien = []  # Regie = gueltig ohne Material

    lohn_ep = lohn_stunden * tenant.stundensatz_eur

    # Zuschläge: BGK + AGK + W+G auf (Material + Lohn) kumulativ
    basis = material_ep + lohn_ep
    gesamt_zuschlag_prozent = (tenant.bgk_prozent + tenant.agk_prozent + tenant.wg_prozent) / 100.0
    zuschlaege_ep = basis * gesamt_zuschlag_prozent
    ep = round(basis + zuschlaege_ep, 2)
    gp = round(ep * p.menge, 2)

    # Wenn Pflicht-Materialien fehlen: Position als manuell zu pruefen markieren
    # UND EP auf 0 setzen (KEINE Schein-Zahl im Angebot!)
    manuell_pruefen = len(fehlende_pflicht_materialien) > 0
    if manuell_pruefen:
        # EP bleibt unvollstaendig - wir zeigen 0, NICHT einen Teil-EP der falsch sein koennte
        ep = 0.0
        gp = 0.0

    p.materialien = detailliste
    p.material_ep = round(material_ep, 2)
    p.lohn_stunden = round(lohn_stunden, 2)
    p.lohn_ep = round(lohn_ep, 2)
    p.zuschlaege_ep = round(zuschlaege_ep, 2)
    p.ep = ep
    p.gp = gp
    p.warnung = " | ".join(warnungen)[:1000]
    if manuell_pruefen:
        p.konfidenz = 0.0  # harte Kennzeichnung: manuell noetig
    elif warnungen:
        p.konfidenz = min(p.konfidenz, 0.6)

    # Angebotenes Fabrikat: erstes gematchtes Haupt-Material, sonst Leitfabrikat
    if not manuell_pruefen and angebotenes_fabrikat_parts:
        p.angebotenes_fabrikat = angebotenes_fabrikat_parts[0][:200]
    elif p.leit_fabrikat and not manuell_pruefen:
        # Wenn Kalkulation geklappt hat aber kein Hersteller aus Match:
        # Leitfabrikat als Default (Bieter bestaetigt gefordertes Fabrikat)
        p.angebotenes_fabrikat = p.leit_fabrikat[:200]


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

    summe_bindend = 0.0  # ohne Bedarf/Alternative
    summe_bedarf = 0.0
    summe_alternative = 0.0
    summe_gesamt = 0.0  # inkl. aller optionalen
    gematcht = 0
    unsicher = 0
    for p in lv.positions:
        _kalkuliere_position(db, tenant, pl, p)
        summe_gesamt += p.gp or 0.0
        # Optional-Positionen fliessen NICHT in die bindende Angebotssumme
        if p.is_bedarf:
            summe_bedarf += p.gp or 0.0
        elif p.is_alternative:
            summe_alternative += p.gp or 0.0
        else:
            summe_bindend += p.gp or 0.0
        if p.ep > 0 and not p.warnung:
            gematcht += 1
        if p.konfidenz < 0.85:
            unsicher += 1

    lv.angebotssumme_netto = round(summe_bindend, 2)
    lv.bedarfspositionen_summe = round(summe_bedarf, 2)
    lv.alternativpositionen_summe = round(summe_alternative, 2)
    lv.gesamtsumme_inklusive_optional = round(summe_gesamt, 2)
    lv.positionen_gematcht = gematcht
    lv.positionen_unsicher = unsicher
    lv.price_list_id = pl.id
    lv.status = "calculated"
    db.commit()
    db.refresh(lv)
    log.info(
        "lv_calculated",
        lv_id=lv.id,
        summe_netto=lv.angebotssumme_netto,
        summe_bedarf=lv.bedarfspositionen_summe,
        summe_alternative=lv.alternativpositionen_summe,
        summe_gesamt=lv.gesamtsumme_inklusive_optional,
        gematcht=gematcht,
        unsicher=unsicher,
    )
    return lv
