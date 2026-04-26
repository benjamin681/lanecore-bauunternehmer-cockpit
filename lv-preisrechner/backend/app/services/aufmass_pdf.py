"""Aufmaß-basiertes Angebots-PDF (B+4.12).

Wrapper um :func:`generate_angebot_pdf`, der die Positionen mit den
gemessenen Mengen aus einem finalized Aufmaß ueberlagert.

Es wird kein neues PDF-Layout entwickelt — der Anbieter sieht das
gleiche Angebots-Layout wie zuvor, nur mit den Aufmaß-Mengen und
einer Hinweiszeile "(auf Basis Aufmaß X)" im Header.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.models.aufmass import Aufmass
from app.models.lv import LV
from app.models.tenant import Tenant
from app.services.lv_pdf_export import generate_angebot_pdf


def generate_aufmass_offer_pdf(
    aufmass: Aufmass, lv: LV, tenant: Tenant
) -> bytes:
    """Erzeugt das Angebots-PDF auf Basis der Aufmaß-Mengen.

    Voraussetzungen:
    - Aufmaß ist hydratiert mit positions
    - LV ist hydratiert (fuer projekt_name, auftraggeber, angebotsnr)
    """
    # Index lv-position_id -> AufmassPosition
    by_lv_pos: dict[str, "Aufmass"] = {p.lv_position_id: p for p in aufmass.positions}

    shadow_positions = []
    aufmass_total = 0.0
    for orig in lv.positions:
        au = by_lv_pos.get(orig.id)
        if au is None:
            # Position existierte zum Aufmaß-Zeitpunkt nicht (Edge Case bei spaeteren
            # LV-Aenderungen). Fallback: original mengen.
            shadow_positions.append(orig)
            aufmass_total += float(orig.gp or 0)
            continue
        # Build shadow that quacks like Position
        shadow = SimpleNamespace(
            id=orig.id,
            reihenfolge=orig.reihenfolge,
            oz=orig.oz,
            titel=orig.titel,
            kurztext=orig.kurztext,
            langtext=orig.langtext,
            menge=float(au.gemessene_menge),
            einheit=orig.einheit,
            erkanntes_system=orig.erkanntes_system,
            feuerwiderstand=orig.feuerwiderstand,
            plattentyp=orig.plattentyp,
            material_ep=orig.material_ep,
            lohn_stunden=orig.lohn_stunden,
            lohn_ep=orig.lohn_ep,
            zuschlaege_ep=orig.zuschlaege_ep,
            ep=float(au.ep),
            gp=float(au.gp_aufmass),
            angebotenes_fabrikat=orig.angebotenes_fabrikat,
            leit_fabrikat=orig.leit_fabrikat,
            is_bedarf=getattr(orig, "is_bedarf", False),
            is_alternative=getattr(orig, "is_alternative", False),
            is_unsicher=getattr(orig, "is_unsicher", False),
            preisquelle=getattr(orig, "preisquelle", ""),
            materialien=getattr(orig, "materialien", []),
        )
        shadow_positions.append(shadow)
        aufmass_total += float(au.gp_aufmass)

    # Shadow LV mit ueberlagerten Werten
    shadow_lv = SimpleNamespace(
        id=lv.id,
        tenant_id=lv.tenant_id,
        projekt_name=f"{lv.projekt_name} (Aufmaß {aufmass.aufmass_number})",
        auftraggeber=lv.auftraggeber,
        original_dateiname=lv.original_dateiname,
        original_pdf_bytes=lv.original_pdf_bytes,
        status=lv.status,
        positionen_gesamt=len(shadow_positions),
        positionen_gematcht=lv.positionen_gematcht,
        positionen_unsicher=lv.positionen_unsicher,
        angebotssumme_netto=aufmass_total,
        bedarfspositionen_summe=lv.bedarfspositionen_summe,
        alternativpositionen_summe=lv.alternativpositionen_summe,
        gesamtsumme_inklusive_optional=aufmass_total,
        price_list_id=getattr(lv, "price_list_id", ""),
        project_id=getattr(lv, "project_id", None),
        created_at=lv.created_at,
        updated_at=lv.updated_at,
        positions=shadow_positions,
    )

    return generate_angebot_pdf(shadow_lv, tenant)  # type: ignore[arg-type]
