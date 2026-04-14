"""Kalkulation Service — Automatische Materialliste + Preisvergleich.

Flow: Analyse-Ergebnis → Materialliste ableiten → Preise aus DB matchen → Kalkulation.
"""

import math
from dataclasses import dataclass, field
from uuid import UUID

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preisliste import Preisliste, Produkt

log = structlog.get_logger()


# ── Trockenbau-Materialregeln ────────────────────────────────────────────────
# Diese Regeln bilden ab, welche Materialien pro System benötigt werden.
# Verschnitt-Faktoren und Verbräuche basieren auf Knauf/Rigips-Richtwerten.

VERSCHNITT_PLATTEN = 1.10       # 10% Verschnitt
VERSCHNITT_PROFILE = 1.05       # 5% Verschnitt
VERSCHNITT_DAEMMUNG = 1.05      # 5% Verschnitt
SCHRAUBEN_PRO_M2 = 25           # Schnellbauschrauben pro m² Beplankung
DIREKTABHAENGER_PRO_M2 = 1.5    # Abhänger pro m² Decke
CD_PROFIL_LFM_PRO_M2 = 3.2     # CD 60/27 laufende Meter pro m² Decke (Achsabstand 31.5cm)
UD_PROFIL_LFM_PRO_M2 = 0.8     # UD Randprofil: Umfang / Fläche Näherung
CW_PROFIL_LFM_PRO_M2_WAND = 2.5  # CW pro m² Wand (Achsabstand 62.5cm)
UW_PROFIL_LFM_PRO_M2_WAND = 0.7  # UW Boden+Decke pro m² Wand
SPACHTEL_KG_PRO_M2 = 0.3       # Fugenspachtel kg pro m²
FUGENBAND_LFM_PRO_M2 = 1.5     # Bewehrungsstreifen lfm pro m²

# Plattengrößen (Standard)
GKB_M2_PRO_PLATTE = 3.0  # 1250 x 2000 mm = 2.5 m² (aber 1250x2500 = 3.125)
AQUAPANEL_M2_PRO_PLATTE = 1.5  # 900 x 1200 = 1.08 (aber größer verfügbar)


@dataclass
class MaterialPosition:
    """Eine Position in der Materialliste."""
    bezeichnung: str
    kategorie: str  # Profil, Platte, Befestigung, Spachtel, Daemmung, Zubehoer
    menge: float
    einheit: str  # Stk, lfm, m², kg, Pkg
    herkunft: str  # z.B. "Decke D112 Aufenthaltsraum 0.1.01"
    suchbegriffe: list[str] = field(default_factory=list)
    # Suchbegriffe für Preislisten-Match

    # Wird nach Preisvergleich gesetzt:
    bester_preis: float | None = None
    bester_anbieter: str | None = None
    alle_preise: list[dict] | None = None


@dataclass
class Kalkulation:
    """Komplette Kalkulation mit Materialliste und Preisen."""
    positionen: list[MaterialPosition] = field(default_factory=list)
    gesamt_netto: float = 0.0
    gesamt_mit_preisen: int = 0
    gesamt_ohne_preise: int = 0


def materialliste_aus_analyse(analyse_result: dict) -> list[MaterialPosition]:
    """Leitet aus einem Analyse-Ergebnis die benötigten Materialien ab."""
    positionen: list[MaterialPosition] = []

    # ── Decken verarbeiten ──
    decken = analyse_result.get("decken", [])
    for d in decken:
        if d.get("entfaellt"):
            continue

        flaeche = d.get("flaeche_m2") or 0
        if flaeche <= 0:
            continue

        raum = d.get("raum", "Unbekannt")
        raum_nr = d.get("raum_nr", "")
        system = d.get("system", "")
        beplankung = d.get("beplankung", "GKB 12.5mm")
        profil = d.get("profil", "CD 60/27")
        herkunft = f"Decke {system} {raum} {raum_nr}".strip()

        # 1. CD-Profile
        cd_lfm = math.ceil(flaeche * CD_PROFIL_LFM_PRO_M2 * VERSCHNITT_PROFILE * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung=f"{profil} Tragprofil",
            kategorie="CD-Profil",
            menge=cd_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["CD 60/27", "CD-Profil", "CD60", "Tragprofil"],
        ))

        # 2. UD-Randprofil
        ud_lfm = math.ceil(flaeche * UD_PROFIL_LFM_PRO_M2 * VERSCHNITT_PROFILE * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung="UD 28/27 Randprofil",
            kategorie="UD-Profil",
            menge=ud_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["UD 28/27", "UD-Profil", "UD28", "Randprofil"],
        ))

        # 3. Beplankung
        if "aquapanel" in (beplankung or "").lower() or "aquapanel" in (d.get("typ") or "").lower():
            platten_m2 = math.ceil(flaeche * VERSCHNITT_PLATTEN * 10) / 10
            positionen.append(MaterialPosition(
                bezeichnung="Knauf Aquapanel Indoor",
                kategorie="GK-Platte",
                menge=platten_m2,
                einheit="m²",
                herkunft=herkunft,
                suchbegriffe=["Aquapanel", "Aquapanel Indoor", "Zementplatte"],
            ))
        else:
            platten_m2 = math.ceil(flaeche * VERSCHNITT_PLATTEN * 10) / 10
            platte_typ = "GKB" if "gkb" in (beplankung or "").lower() or not beplankung else beplankung
            positionen.append(MaterialPosition(
                bezeichnung=f"{platte_typ} Gipskartonplatte",
                kategorie="GK-Platte",
                menge=platten_m2,
                einheit="m²",
                herkunft=herkunft,
                suchbegriffe=["GKB", "Gipskarton", "Knauf", "12.5", "Diamant", platte_typ],
            ))

        # 4. Direktabhänger
        abhaenger_stk = math.ceil(flaeche * DIREKTABHAENGER_PRO_M2)
        positionen.append(MaterialPosition(
            bezeichnung="Direktabhänger",
            kategorie="Zubehoer",
            menge=abhaenger_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Direktabhänger", "Abhänger", "Nonius", "Federbügel"],
        ))

        # 5. Schnellbauschrauben
        schrauben_stk = math.ceil(flaeche * SCHRAUBEN_PRO_M2)
        positionen.append(MaterialPosition(
            bezeichnung="Schnellbauschrauben TN 3.5x25",
            kategorie="Befestigung",
            menge=schrauben_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Schnellbauschraube", "TN 3.5", "TN3.5x25", "Gipsplattenschraube"],
        ))

        # 6. Spachtel + Fugenband
        spachtel_kg = math.ceil(flaeche * SPACHTEL_KG_PRO_M2 * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung="Fugenspachtel (Uniflott o.ä.)",
            kategorie="Spachtel",
            menge=spachtel_kg,
            einheit="kg",
            herkunft=herkunft,
            suchbegriffe=["Uniflott", "Fugenspachtel", "Spachtelmasse", "Fugenfüller"],
        ))

        fugenband_lfm = math.ceil(flaeche * FUGENBAND_LFM_PRO_M2 * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung="Bewehrungsstreifen / Fugenband",
            kategorie="Band",
            menge=fugenband_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["Bewehrungsstreifen", "Fugenband", "Kurt", "Papierband"],
        ))

    # ── Wände verarbeiten ──
    waende = analyse_result.get("waende", [])
    for w in waende:
        laenge = w.get("laenge_m") or 0
        hoehe = w.get("hoehe_m") or 0
        flaeche = w.get("flaeche_m2") or (laenge * hoehe)
        if flaeche <= 0:
            continue

        typ = w.get("typ", "W112")
        herkunft = f"Wand {typ} ({laenge:.1f}m x {hoehe:.1f}m)"

        # Anzahl Beplankungslagen
        lagen = 2 if typ in ("W115", "W116", "W118") else 1
        # Beidseitig
        seiten = 2

        # 1. CW-Ständer
        cw_lfm = math.ceil(flaeche * CW_PROFIL_LFM_PRO_M2_WAND * VERSCHNITT_PROFILE * 10) / 10
        cw_breite = "75" if "112" in typ else "100" if "115" in typ else "100"
        positionen.append(MaterialPosition(
            bezeichnung=f"CW {cw_breite} Ständerprofil",
            kategorie="CW-Profil",
            menge=cw_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=[f"CW {cw_breite}", f"CW{cw_breite}", "CW-Profil", "Ständerprofil"],
        ))

        # 2. UW Boden/Decke
        uw_lfm = math.ceil(flaeche * UW_PROFIL_LFM_PRO_M2_WAND * VERSCHNITT_PROFILE * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung=f"UW {cw_breite} Anschlussprofil",
            kategorie="UW-Profil",
            menge=uw_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=[f"UW {cw_breite}", f"UW{cw_breite}", "UW-Profil", "Anschlussprofil"],
        ))

        # 3. Beplankung (beidseitig, ggf. mehrlagig)
        platten_m2 = math.ceil(flaeche * seiten * lagen * VERSCHNITT_PLATTEN * 10) / 10
        platte_typ = "GKF" if typ in ("W118",) else "GKB"
        positionen.append(MaterialPosition(
            bezeichnung=f"{platte_typ} 12.5mm Platte",
            kategorie="GK-Platte",
            menge=platten_m2,
            einheit="m²",
            herkunft=herkunft,
            suchbegriffe=[platte_typ, "Gipskarton", "12.5", "Platte"],
        ))

        # 4. Dämmung
        daemmung_m2 = math.ceil(flaeche * VERSCHNITT_DAEMMUNG * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung="Mineralwolle Trennwand",
            kategorie="Daemmung",
            menge=daemmung_m2,
            einheit="m²",
            herkunft=herkunft,
            suchbegriffe=["Mineralwolle", "Steinwolle", "Dämmung", "Trennwand", "Isover", "Rockwool"],
        ))

        # 5. Schrauben
        schrauben_stk = math.ceil(flaeche * seiten * lagen * SCHRAUBEN_PRO_M2)
        positionen.append(MaterialPosition(
            bezeichnung="Schnellbauschrauben TN 3.5x25",
            kategorie="Befestigung",
            menge=schrauben_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Schnellbauschraube", "TN 3.5", "TN3.5x25"],
        ))

    return positionen


def aggregiere_positionen(positionen: list[MaterialPosition]) -> list[MaterialPosition]:
    """Fasst identische Materialien zusammen (gleiche Bezeichnung + Einheit)."""
    agg: dict[str, MaterialPosition] = {}

    for pos in positionen:
        key = f"{pos.bezeichnung}|{pos.einheit}"
        if key in agg:
            agg[key].menge += pos.menge
            agg[key].herkunft += f"; {pos.herkunft}"
        else:
            # Copy
            agg[key] = MaterialPosition(
                bezeichnung=pos.bezeichnung,
                kategorie=pos.kategorie,
                menge=pos.menge,
                einheit=pos.einheit,
                herkunft=pos.herkunft,
                suchbegriffe=pos.suchbegriffe.copy(),
            )

    # Runden
    for pos in agg.values():
        pos.menge = round(pos.menge, 1)

    return sorted(agg.values(), key=lambda p: p.kategorie)


async def preise_matchen(
    positionen: list[MaterialPosition],
    db: AsyncSession,
) -> list[MaterialPosition]:
    """Matcht jede Position gegen die Produkte aller Preislisten."""
    for pos in positionen:
        best_price = None
        best_anbieter = None
        alle = []

        for suchbegriff in pos.suchbegriffe:
            # Fuzzy-Suche: ILIKE
            result = await db.execute(
                select(Produkt, Preisliste.anbieter)
                .join(Preisliste)
                .where(
                    Preisliste.status == "completed",
                    Produkt.verfuegbar == True,
                    Produkt.bezeichnung.ilike(f"%{suchbegriff}%"),
                )
                .order_by(Produkt.preis_netto.asc())
                .limit(10)
            )

            for produkt, anbieter in result.all():
                preis = float(produkt.preis_netto)
                alle.append({
                    "anbieter": anbieter,
                    "bezeichnung": produkt.bezeichnung,
                    "preis_netto": preis,
                    "einheit": produkt.einheit,
                    "artikel_nr": produkt.artikel_nr,
                })

                if best_price is None or preis < best_price:
                    best_price = preis
                    best_anbieter = anbieter

        # Deduplizieren nach Anbieter+Bezeichnung
        seen = set()
        unique_alle = []
        for a in alle:
            key = f"{a['anbieter']}|{a['bezeichnung']}"
            if key not in seen:
                seen.add(key)
                unique_alle.append(a)

        pos.bester_preis = best_price
        pos.bester_anbieter = best_anbieter
        pos.alle_preise = unique_alle[:5]  # Top 5

    return positionen


async def erstelle_kalkulation(
    analyse_result: dict,
    db: AsyncSession,
    custom_params: dict | None = None,
) -> dict:
    """Kompletter Flow: Analyse -> Materialliste -> Preisvergleich -> Kalkulation.

    custom_params can override:
      - material_aufschlag_prozent (float, e.g. 15 for 15%)
      - stundensatz_eigen (float, EUR/h)
      - stundensatz_sub (float, EUR/h)
      - stunden_pro_m2_decke (float)
      - stunden_pro_m2_wand (float)
      - anteil_eigenleistung (float, 0.0-1.0)
      - zusatzkosten (list[dict] with bezeichnung + betrag)
      - mengen_overrides (dict[str, float] key=bezeichnung, value=new menge)
    """
    params = custom_params or {}

    # 1. Materialien ableiten
    positionen = materialliste_aus_analyse(analyse_result)
    log.info("materialliste_generiert", einzelpositionen=len(positionen))

    # 2. Aggregieren (gleiche Materialien zusammenfassen)
    aggregiert = aggregiere_positionen(positionen)
    log.info("materialliste_aggregiert", positionen=len(aggregiert))

    # 2b. Apply mengen_overrides if provided
    mengen_overrides = params.get("mengen_overrides")
    if mengen_overrides:
        for pos in aggregiert:
            if pos.bezeichnung in mengen_overrides:
                pos.menge = round(mengen_overrides[pos.bezeichnung], 1)

    # 3. Preise matchen
    aggregiert = await preise_matchen(aggregiert, db)

    # 4. Kalkulation zusammenstellen
    gesamt_netto = 0.0
    mit_preisen = 0
    ohne_preise = 0

    result_positionen = []
    for pos in aggregiert:
        gesamtpreis = None
        if pos.bester_preis is not None:
            gesamtpreis = round(pos.bester_preis * pos.menge, 2)
            gesamt_netto += gesamtpreis
            mit_preisen += 1
        else:
            ohne_preise += 1

        result_positionen.append({
            "bezeichnung": pos.bezeichnung,
            "kategorie": pos.kategorie,
            "menge": pos.menge,
            "einheit": pos.einheit,
            "einzelpreis": pos.bester_preis,
            "gesamtpreis": gesamtpreis,
            "anbieter": pos.bester_anbieter,
            "alternativen": pos.alle_preise or [],
            "herkunft": pos.herkunft[:200],
        })

    # 5. Bestellliste: nach Lieferant gruppiert
    bestellliste: dict[str, list[dict]] = {}
    for pos in result_positionen:
        anbieter = pos.get("anbieter") or "Kein Anbieter"
        if anbieter not in bestellliste:
            bestellliste[anbieter] = []
        bestellliste[anbieter].append({
            "bezeichnung": pos["bezeichnung"],
            "kategorie": pos["kategorie"],
            "menge": pos["menge"],
            "einheit": pos["einheit"],
            "einzelpreis": pos["einzelpreis"],
            "gesamtpreis": pos["gesamtpreis"],
        })

    bestellliste_result = []
    for anbieter, items in bestellliste.items():
        summe = sum(i["gesamtpreis"] or 0 for i in items)
        bestellliste_result.append({
            "anbieter": anbieter,
            "positionen": items,
            "anzahl_positionen": len(items),
            "summe_netto": round(summe, 2),
        })
    bestellliste_result.sort(key=lambda b: b["summe_netto"], reverse=True)

    # 6. Kundenangebot: Einkaufspreis + Aufschlag
    # Use custom params or defaults
    aufschlag_material = (params.get("material_aufschlag_prozent", 15) or 15) / 100
    stundensatz_eigen = params.get("stundensatz_eigen", 45.0) or 45.0
    stundensatz_sub = params.get("stundensatz_sub", 35.0) or 35.0
    stunden_pro_m2_decke = params.get("stunden_pro_m2_decke", 0.5) or 0.5
    stunden_pro_m2_wand = params.get("stunden_pro_m2_wand", 0.8) or 0.8
    anteil_eigenleistung = params.get("anteil_eigenleistung", 0.3) or 0.3
    zusatzkosten = params.get("zusatzkosten", []) or []

    # Gesamt-Flaechen berechnen
    gesamt_deckenflaeche = sum(
        (d.get("flaeche_m2") or 0)
        for d in analyse_result.get("decken", [])
        if not d.get("entfaellt")
    )
    gesamt_wandflaeche = sum(
        (w.get("flaeche_m2") or (w.get("laenge_m", 0) * w.get("hoehe_m", 0)))
        for w in analyse_result.get("waende", [])
    )

    # Lohnstunden: split between own and sub based on anteil_eigenleistung
    gesamt_stunden = round(
        gesamt_deckenflaeche * stunden_pro_m2_decke +
        gesamt_wandflaeche * stunden_pro_m2_wand, 1
    )
    stunden_eigen = round(gesamt_stunden * anteil_eigenleistung, 1)
    stunden_sub = round(gesamt_stunden * (1 - anteil_eigenleistung), 1)

    lohnkosten_eigen = round(stunden_eigen * stundensatz_eigen, 2)
    lohnkosten_sub = round(stunden_sub * stundensatz_sub, 2)
    lohnkosten = round(lohnkosten_eigen + lohnkosten_sub, 2)

    # Blended hourly rate for display
    stundensatz_blended = round(
        (stundensatz_eigen * anteil_eigenleistung +
         stundensatz_sub * (1 - anteil_eigenleistung)),
        2,
    )

    material_einkauf = round(gesamt_netto, 2)
    material_aufschlag = round(gesamt_netto * aufschlag_material, 2)
    material_verkauf = round(material_einkauf + material_aufschlag, 2)

    # Zusatzkosten summieren
    zusatzkosten_summe = round(sum(z.get("betrag", 0) for z in zusatzkosten), 2)

    angebot_netto = round(material_verkauf + lohnkosten + zusatzkosten_summe, 2)
    mwst = round(angebot_netto * 0.19, 2)
    angebot_brutto = round(angebot_netto + mwst, 2)

    kundenangebot = {
        "material_einkauf": material_einkauf,
        "material_aufschlag_prozent": round(aufschlag_material * 100, 1),
        "material_aufschlag_eur": material_aufschlag,
        "material_verkauf": material_verkauf,
        "lohnstunden": gesamt_stunden,
        "stundensatz": stundensatz_blended,
        "stundensatz_eigen": stundensatz_eigen,
        "stundensatz_sub": stundensatz_sub,
        "stunden_eigen": stunden_eigen,
        "stunden_sub": stunden_sub,
        "lohnkosten_eigen": lohnkosten_eigen,
        "lohnkosten_sub": lohnkosten_sub,
        "lohnkosten": lohnkosten,
        "anteil_eigenleistung": anteil_eigenleistung,
        "stunden_pro_m2_decke": stunden_pro_m2_decke,
        "stunden_pro_m2_wand": stunden_pro_m2_wand,
        "zusatzkosten": zusatzkosten,
        "zusatzkosten_summe": zusatzkosten_summe,
        "angebot_netto": angebot_netto,
        "mwst_prozent": 19,
        "mwst_eur": mwst,
        "angebot_brutto": angebot_brutto,
        "deckenflaeche_m2": round(gesamt_deckenflaeche, 1),
        "wandflaeche_m2": round(gesamt_wandflaeche, 1),
    }

    return {
        "positionen": result_positionen,
        "gesamt_netto": round(gesamt_netto, 2),
        "positionen_mit_preis": mit_preisen,
        "positionen_ohne_preis": ohne_preise,
        "positionen_gesamt": len(result_positionen),
        "bestellliste": bestellliste_result,
        "kundenangebot": kundenangebot,
    }
