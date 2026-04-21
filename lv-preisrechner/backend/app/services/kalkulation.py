"""Kalkulation: Position → EP (Material + Lohn + Zuschläge).

Seit B+4.2 kann `tenant.use_new_pricing` den Preis-Lookup umschalten:
- Flag=False (Default): bestehende Legacy-Route ueber dna_matcher.find_best_match
  auf PriceList/PriceEntry.
- Flag=True: neuer Lookup-Service (app.services.price_lookup.lookup_price)
  mit 5-stufiger Fallback-Kaskade (Override -> SupplierPriceList -> Legacy
  -> Estimated -> not_found) inklusive Rabatt-Regeln.

Der Unterschied bleibt innerhalb von `_kalkuliere_position` gekapselt; alle
ausseren Funktionssignaturen bleiben unveraendert.
"""

from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from app.models.lv import LV
from app.models.position import Position
from app.models.price_list import PriceList
from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
    TenantPriceOverride,
)
from app.models.tenant import Tenant
from app.services.dna_matcher import find_best_match
from app.services.materialrezepte import MaterialBedarf, Rezept, resolve_rezept
from app.services.price_lookup import lookup_price
from app.services.price_resolution import (
    PriceResolution,
    from_legacy_match,
    from_lookup_result,
    summarize_sources,
)

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Helper: DNA-Pattern in lookup_price-Inputs zerlegen
# ---------------------------------------------------------------------------
def _parse_dna_pattern(pattern: str) -> dict[str, str]:
    parts = pattern.split("|")
    keys = ["hersteller", "kategorie", "produktname", "abmessungen", "variante"]
    out: dict[str, str] = {}
    for k, v in zip(keys, parts, strict=False):
        out[k] = v.strip()
    return out


def _resolve_material_via_lookup(
    *,
    db: Session,
    tenant_id: str,
    mb: MaterialBedarf,
) -> PriceResolution:
    """Neuer Pfad: nutzt price_lookup.lookup_price.

    Das DNA-Pattern wird auf die freie lookup_price-Signatur uebersetzt.
    Anschliessend wird aus dem gematchten SupplierPriceEntry manufacturer
    und product_name nachgereicht (fuer angebotenes_fabrikat).
    """
    parts = _parse_dna_pattern(mb.dna_pattern)
    product = " ".join(p for p in (parts.get("produktname"), parts.get("abmessungen"), parts.get("variante")) if p)
    lookup = lookup_price(
        db=db,
        tenant_id=tenant_id,
        material_name=product or parts.get("produktname", ""),
        unit=mb.basis_einheit,
        manufacturer=parts.get("hersteller") or None,
        category=parts.get("kategorie") or None,
    )
    resolution = from_lookup_result(lookup)

    # manufacturer & product_name aus dem Entry nachziehen (wenn Treffer)
    if lookup.entry_id and lookup.price_source in ("supplier_price", "estimated"):
        entry = db.get(SupplierPriceEntry, lookup.entry_id)
        if entry:
            resolution.manufacturer = entry.manufacturer or parts.get("hersteller") or None
            resolution.product_name = entry.product_name
    elif lookup.entry_id and lookup.price_source == "legacy_price":
        from app.models.price_entry import PriceEntry  # late import
        entry = db.get(PriceEntry, lookup.entry_id)
        if entry:
            resolution.manufacturer = entry.hersteller or parts.get("hersteller") or None
            resolution.product_name = entry.produktname
    # bei override & not_found: manufacturer bleibt wie aus dna-Pattern (kann None sein)
    if resolution.manufacturer is None and parts.get("hersteller"):
        resolution.manufacturer = parts.get("hersteller")

    return resolution


def _resolve_material_via_legacy(
    *,
    db: Session,
    tenant_id: str,
    price_list: PriceList,
    mb: MaterialBedarf,
) -> PriceResolution:
    """Alter Pfad: DNA-Matcher auf PriceEntry. Verhalten unveraendert seit B+4.2."""
    match = find_best_match(
        db=db,
        tenant_id=tenant_id,
        price_list_id=price_list.id,
        dna_pattern=mb.dna_pattern,
    )
    return from_legacy_match(match)


# ---------------------------------------------------------------------------
# Kern: eine Position kalkulieren
# ---------------------------------------------------------------------------
def _kalkuliere_position(
    db: Session,
    tenant: Tenant,
    price_list: PriceList | None,
    p: Position,
) -> None:
    """Berechnet EP und GP für eine einzelne Position.

    Ob Legacy- oder Neu-Pfad pro Material genutzt wird, entscheidet
    tenant.use_new_pricing. Die Signatur bleibt gegenueber B+4.1
    unveraendert.
    """
    rezept: Rezept | None = resolve_rezept(p.erkanntes_system, p.feuerwiderstand, p.plattentyp)

    material_ep = 0.0
    detailliste: list[dict] = []
    warnungen: list[str] = []
    fehlende_pflicht_materialien: list[str] = []
    angebotenes_fabrikat_parts: list[str] = []
    resolutions: list[PriceResolution] = []

    use_new = bool(getattr(tenant, "use_new_pricing", False))

    if rezept:
        for mb in rezept.materialien:
            if use_new:
                res = _resolve_material_via_lookup(
                    db=db, tenant_id=tenant.id, mb=mb
                )
            else:
                # Legacy-Pfad erfordert eine PriceList
                assert price_list is not None, "Legacy-Pfad ohne PriceList ist nicht erlaubt"
                res = _resolve_material_via_legacy(
                    db=db, tenant_id=tenant.id, price_list=price_list, mb=mb
                )
            resolutions.append(res)

            if res.price is None:
                if not getattr(mb, "optional", False):
                    fehlende_pflicht_materialien.append(mb.dna_pattern)
                    warnungen.append(f"Kein Preis: {mb.dna_pattern}")
                detailliste.append(
                    {
                        "dna_pattern": mb.dna_pattern,
                        "menge": mb.menge_pro_einheit,
                        "einheit": mb.basis_einheit,
                        "preis": 0.0,
                        "gp": 0.0,
                        "warnung": res.source_description,
                        # additive B+4.2-Felder:
                        "price_source": res.source,
                        "source_description": res.source_description,
                        "applied_discount_percent": (
                            float(res.applied_discount_percent)
                            if res.applied_discount_percent is not None
                            else None
                        ),
                        "needs_review": res.needs_review,
                        "match_confidence": round(res.confidence, 3),
                    }
                )
                continue

            preis_pro_basis = float(res.price)
            teilpreis = mb.menge_pro_einheit * preis_pro_basis
            material_ep += teilpreis

            # Hauptmaterial fuer "Angebotenes Fabrikat" (erstes m2-Material)
            if mb.basis_einheit == "m²" and res.manufacturer:
                produkt = res.product_name or ""
                combo = f"{res.manufacturer} {produkt}".strip()
                if combo and combo not in angebotenes_fabrikat_parts:
                    angebotenes_fabrikat_parts.append(combo)

            entry_dna = res.details.get("dna", "") if res.details else ""
            detailliste.append(
                {
                    # Legacy-Keys bleiben erhalten (PDF-Filler, bestehende UI):
                    "dna": entry_dna,
                    "menge": mb.menge_pro_einheit,
                    "einheit": mb.basis_einheit,
                    "preis_einheit": preis_pro_basis,
                    "gp": round(teilpreis, 2),
                    "match_konfidenz": round(res.confidence, 2),
                    # Additive B+4.2-Felder:
                    "price_source": res.source,
                    "source_description": res.source_description,
                    "applied_discount_percent": (
                        float(res.applied_discount_percent)
                        if res.applied_discount_percent is not None
                        else None
                    ),
                    "needs_review": res.needs_review,
                    "match_confidence": round(res.confidence, 3),
                }
            )

        lohn_stunden = rezept.zeit_h_pro_einheit
    else:
        warnungen.append(f"Kein Rezept fuer System '{p.erkanntes_system}' - manuelle Pruefung noetig")
        fehlende_pflicht_materialien.append("kein_rezept")
        lohn_stunden = 0.0

    # Spezialfaelle (Regiestunde)
    if p.einheit.lower() in ("h", "std", "stunden"):
        lohn_stunden = 1.0
        material_ep = 0.0
        fehlende_pflicht_materialien = []

    lohn_ep = lohn_stunden * tenant.stundensatz_eur
    basis = material_ep + lohn_ep
    gesamt_zuschlag_prozent = (tenant.bgk_prozent + tenant.agk_prozent + tenant.wg_prozent) / 100.0
    zuschlaege_ep = basis * gesamt_zuschlag_prozent
    ep = round(basis + zuschlaege_ep, 2)
    gp = round(ep * p.menge, 2)

    manuell_pruefen = len(fehlende_pflicht_materialien) > 0
    if manuell_pruefen:
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
        p.konfidenz = 0.0
    elif warnungen:
        p.konfidenz = min(p.konfidenz, 0.6)

    # Angebotenes Fabrikat (Hersteller, NICHT Lieferant)
    if not manuell_pruefen and angebotenes_fabrikat_parts:
        p.angebotenes_fabrikat = angebotenes_fabrikat_parts[0][:200]
    elif p.leit_fabrikat and not manuell_pruefen:
        p.angebotenes_fabrikat = p.leit_fabrikat[:200]

    # B+4.2: aggregierte Preis-Herkunft auf Positions-Ebene
    p.needs_price_review = any(r.needs_review for r in resolutions) if resolutions else False
    p.price_source_summary = summarize_sources(resolutions)


# ---------------------------------------------------------------------------
# Top-Level: LV kalkulieren
# ---------------------------------------------------------------------------
def _has_new_pricing_data(db: Session, tenant_id: str) -> bool:
    """Variante A-plus: aktive SupplierPriceList ODER mindestens ein Override."""
    has_list = (
        db.query(SupplierPriceList.id)
        .filter(
            SupplierPriceList.tenant_id == tenant_id,
            SupplierPriceList.is_active.is_(True),
            SupplierPriceList.status != PricelistStatus.ARCHIVED.value,
        )
        .first()
        is not None
    )
    if has_list:
        return True
    has_override = (
        db.query(TenantPriceOverride.id)
        .filter(TenantPriceOverride.tenant_id == tenant_id)
        .first()
        is not None
    )
    return has_override


def kalkuliere_lv(db: Session, lv_id: str, tenant_id: str) -> LV:
    """Kalkuliert ein komplettes LV."""
    lv = db.query(LV).filter(LV.id == lv_id, LV.tenant_id == tenant_id).first()
    if not lv:
        raise ValueError("LV nicht gefunden")

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise ValueError("Tenant nicht gefunden")

    use_new = bool(getattr(tenant, "use_new_pricing", False))

    pl: PriceList | None = None
    if use_new:
        # Variante A-plus: SupplierPriceList ODER Override-Daten
        if not _has_new_pricing_data(db, tenant_id):
            raise ValueError(
                "Keine Preisdaten verfuegbar. Bitte zuerst eine Lieferanten-"
                "Preisliste hochladen oder Preis-Overrides anlegen."
            )
    else:
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

    summe_bindend = 0.0
    summe_bedarf = 0.0
    summe_alternative = 0.0
    summe_gesamt = 0.0
    gematcht = 0
    unsicher = 0
    for p in lv.positions:
        _kalkuliere_position(db, tenant, pl, p)
        summe_gesamt += p.gp or 0.0
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
    # LV.price_list_id ist NOT NULL (Legacy-Schema). Im neuen Pfad ohne
    # Legacy-Liste setzen wir den leeren String als Platzhalter; die echte
    # Preisquelle steht pro Material im materialien-JSON.
    lv.price_list_id = pl.id if pl else ""
    lv.status = "calculated"
    db.commit()
    db.refresh(lv)
    log.info(
        "lv_calculated",
        lv_id=lv.id,
        use_new_pricing=use_new,
        summe_netto=lv.angebotssumme_netto,
        summe_bedarf=lv.bedarfspositionen_summe,
        summe_alternative=lv.alternativpositionen_summe,
        summe_gesamt=lv.gesamtsumme_inklusive_optional,
        gematcht=gematcht,
        unsicher=unsicher,
    )
    return lv
