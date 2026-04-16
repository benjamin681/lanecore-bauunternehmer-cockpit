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


# ── Trockenbau Knowledge Base ────────────────────────────────────────────────
# Herstellergesicherte Daten aus Knauf, Rigips, Fermacell Systemblättern.
# Importiert aus app/knowledge/trockenbau_systeme.json

from app.knowledge import get_kb, get_system, get_material_pro_m2, get_verschnitt

def _kb_val(system_id: str, key: str, default: float) -> float:
    """Get a value from the knowledge base for a system, with fallback."""
    mat = get_material_pro_m2(system_id)
    return mat.get(key, default)

# Legacy constants kept as fallbacks
VERSCHNITT_PLATTEN = 1.10
VERSCHNITT_PROFILE = 1.05
VERSCHNITT_DAEMMUNG = 1.05
SCHRAUBEN_PRO_M2 = 25

# ── Differenzierte Arbeitszeitwerte (h/m²) nach System ──────────────────────
# Basierend auf Erfahrungswerten für Trockenbau-Montage inkl. Spachteln.
STUNDEN_PRO_M2 = {
    # Decken
    "D112": 0.4,  # Einfache Abhangdecke
    "D113": 0.5,  # Doppelt beplankt
    "D116": 0.7,  # Feuchtraum
    "HKD": 0.6,   # Heiz-Kühl-Decke
    # Wände
    "W112": 0.6,  # Standard einlagig
    "W115": 0.9,  # Doppelt beplankt
    "W116": 1.0,  # Feuchtraum doppelt
    "W118": 1.1,  # Brandschutz
}
DIREKTABHAENGER_PRO_M2 = 1.5    # Abhänger pro m² Decke
CD_PROFIL_LFM_PRO_M2 = 3.2     # CD 60/27 laufende Meter pro m² Decke (Achsabstand 31.5cm)
UD_PROFIL_LFM_PRO_M2 = 0.8     # UD Randprofil: Umfang / Fläche Näherung
CW_PROFIL_LFM_PRO_M2_WAND = 2.5  # CW pro m² Wand (Achsabstand 62.5cm)
UW_PROFIL_LFM_PRO_M2_WAND = 0.7  # UW Boden+Decke pro m² Wand
SPACHTEL_KG_PRO_M2 = 0.3       # Fugenspachtel kg pro m²
FUGENBAND_LFM_PRO_M2 = 1.5     # Bewehrungsstreifen lfm pro m²

# ── Anfahrtskosten-Pauschalen (ab Firmensitz Ulm) ───────────────────────────
ANFAHRT_PAUSCHAL: dict[str, float] = {
    "Ulm": 0,
    "Neu-Ulm": 0,
    "Dornstadt": 25,
    "Blaustein": 20,
    "Ehingen": 50,
    "Göppingen": 75,
    "Augsburg": 100,
    "Stuttgart": 120,
    "München": 180,
}
ANFAHRT_DEFAULT = 80  # EUR wenn Stadt nicht bekannt

# Plattengrößen (Standard)
GKB_M2_PRO_PLATTE = 3.0  # 1250 x 2000 mm = 2.5 m² (aber 1250x2500 = 3.125)
AQUAPANEL_M2_PRO_PLATTE = 1.5  # 900 x 1200 = 1.08 (aber größer verfügbar)


def _anfahrtskosten_fuer_adresse(adresse: str | None) -> float | None:
    """Bestimmt Anfahrtskosten-Pauschale anhand der Projekt-Adresse.

    Durchsucht die Adresse nach bekannten Stadtnamen.
    Returns None wenn keine Adresse gesetzt.
    """
    if not adresse:
        return None
    adresse_lower = adresse.lower()
    for stadt, kosten in ANFAHRT_PAUSCHAL.items():
        if stadt.lower() in adresse_lower:
            return kosten
    return ANFAHRT_DEFAULT


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

    # Verschnitt-Info (gesetzt nach apply_verschnitt)
    verschnitt_prozent: float | None = None  # z.B. 12.0 für 12%

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

    # ── Raum-Flächen-Lookup für Decken ohne eigene Fläche ──
    raum_flaechen: dict[str, float] = {}
    for r in analyse_result.get("raeume", []):
        nr = r.get("raum_nr")
        if nr and r.get("flaeche_m2"):
            raum_flaechen[nr] = r["flaeche_m2"]

    # ── Decken verarbeiten ──
    decken = analyse_result.get("decken", [])
    for d in decken:
        if d.get("entfaellt"):
            continue

        flaeche = d.get("flaeche_m2") or 0
        # Fallback: Fläche aus zugehörigem Raum ableiten
        if flaeche <= 0 and d.get("raum_nr"):
            flaeche = raum_flaechen.get(d["raum_nr"], 0)
        # Fallback 2: Wenn raum_nr "diverse" ist, Summe aller Räume mit passendem Deckentyp
        if flaeche <= 0 and d.get("raum_nr") == "diverse":
            deckentyp = d.get("typ", "").lower()
            for r in analyse_result.get("raeume", []):
                r_decke = (r.get("deckentyp") or "").lower()
                if r.get("flaeche_m2") and (
                    "gk" in r_decke or "abhang" in r_decke or deckentyp[:10] in r_decke
                ):
                    flaeche += r["flaeche_m2"]
        if flaeche <= 0:
            continue

        raum = d.get("raum", "Unbekannt")
        raum_nr = d.get("raum_nr", "")
        system = d.get("system", "")
        beplankung = d.get("beplankung", "GKB 12.5mm")
        profil = d.get("profil", "CD 60/27")
        herkunft = f"Decke {system} {raum} {raum_nr}".strip()

        # Detect system ID from plan data (D112, D113 etc.)
        sys_id = "D112"  # default
        if system:
            for sid in ["D113", "D112"]:
                if sid.lower() in system.lower():
                    sys_id = sid
                    break

        # Get KB values for this system
        kb_mat = get_material_pro_m2(sys_id)

        # 1. CD-Profile (KB: 3.2 lfm/m² for D112, 4.2 for D113)
        cd_lfm = math.ceil(flaeche * kb_mat.get("cd_profil_lfm", CD_PROFIL_LFM_PRO_M2) * VERSCHNITT_PROFILE * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung=f"{profil} Tragprofil",
            kategorie="CD-Profil",
            menge=cd_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["CD 60/27", "CD-Profil", "CD60", "Tragprofil"],
        ))

        # 2. UD-Randprofil (KB: 0.4 lfm/m²)
        ud_lfm = math.ceil(flaeche * kb_mat.get("ud_profil_lfm", UD_PROFIL_LFM_PRO_M2) * VERSCHNITT_PROFILE * 10) / 10
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

        # 4. Direktabhänger (KB: 1.3 Stk/m²)
        abhaenger_stk = math.ceil(flaeche * kb_mat.get("abhaenger_stk", DIREKTABHAENGER_PRO_M2))
        positionen.append(MaterialPosition(
            bezeichnung="Direktabhänger",
            kategorie="Zubehoer",
            menge=abhaenger_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Direktabhänger", "Abhänger", "Nonius", "Federbügel"],
        ))

        # 5. Schnellbauschrauben (KB: 23 Stk/m² for D112)
        schrauben_stk = math.ceil(flaeche * kb_mat.get("schrauben_stk", SCHRAUBEN_PRO_M2))
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

        # 8. Kreuzverbinder (D112 Kreuzrost)
        kreuzverbinder_stk = math.ceil(flaeche * kb_mat.get("kreuzverbinder_stk", 2.3))
        positionen.append(MaterialPosition(
            bezeichnung="Kreuzverbinder CD 60/27",
            kategorie="Zubehoer",
            menge=kreuzverbinder_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Kreuzverbinder", "CD 60/27 Kreuz", "Kreuzstück"],
        ))

        # 9. Längsverbinder (bei Räumen > 4m)
        laengsverbinder_stk = math.ceil(flaeche * kb_mat.get("laengsverbinder_stk", 0.6))
        if laengsverbinder_stk > 0:
            positionen.append(MaterialPosition(
                bezeichnung="Längsverbinder CD 60/27",
                kategorie="Zubehoer",
                menge=laengsverbinder_stk,
                einheit="Stk",
                herkunft=herkunft,
                suchbegriffe=["Längsverbinder", "CD Verbinder", "Profilverbinder"],
            ))

        # 10. Dübel/Anker für Abhänger an Rohdecke
        duebel_stk = abhaenger_stk  # 1 Dübel pro Abhängepunkt
        positionen.append(MaterialPosition(
            bezeichnung="Schlagdübel 6x40 (Deckenbefestigung)",
            kategorie="Befestigung",
            menge=duebel_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Schlagdübel", "Deckendübel", "Metalldübel", "Anker 6x40"],
        ))

        # 11. PE-Dichtungsband auf UD-Profil
        pe_band_lfm = ud_lfm  # gleiche Länge wie UD-Profil
        positionen.append(MaterialPosition(
            bezeichnung="PE-Dichtungsband (auf UD-Profil)",
            kategorie="Dichtung",
            menge=pe_band_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["Dichtungsband", "PE-Band", "Anschlussdichtung", "Trennstreifen"],
        ))

    # ── Öffnungen (Türen/Fenster) einlesen und nach Wand-ID gruppieren ──
    oeffnungen = analyse_result.get("oeffnungen", [])
    oeffnungen_by_wand: dict[str, list[dict]] = {}
    for o in oeffnungen:
        wand_id = o.get("wand_id") or ""
        if wand_id:
            oeffnungen_by_wand.setdefault(wand_id, []).append(o)

    # ── Wände verarbeiten ──
    waende = analyse_result.get("waende", [])
    for w in waende:
        laenge = w.get("laenge_m") or 0
        hoehe = w.get("hoehe_m") or 0
        flaeche = w.get("flaeche_m2") or (laenge * hoehe)
        if flaeche <= 0:
            continue

        typ = w.get("typ", "W112")
        wand_id = w.get("id", "")
        herkunft = f"Wand {typ} ({laenge:.1f}m x {hoehe:.1f}m)"

        # ── Öffnungsabzüge nach VOB-Regel ──
        # VOB/C DIN 18340: Öffnungen < 2,5 m² werden bei der Beplankung
        # NICHT abgezogen (Verschnitt). Bei der Dämmung werden alle
        # Öffnungen immer abgezogen.
        wand_oeffnungen = oeffnungen_by_wand.get(wand_id, [])
        abzug_beplankung = 0.0  # Fläche, die von Beplankung abgezogen wird
        abzug_daemmung = 0.0    # Fläche, die von Dämmung abgezogen wird
        hat_tueren = False

        for o in wand_oeffnungen:
            o_breite = o.get("breite_m") or 0
            o_hoehe = o.get("hoehe_m") or 0
            o_flaeche = o_breite * o_hoehe
            o_typ = (o.get("typ") or "").lower()

            if "tuer" in o_typ or "tür" in o_typ:
                hat_tueren = True

            # Dämmung: Öffnungen werden IMMER abgezogen
            abzug_daemmung += o_flaeche

            # Beplankung: Nur Öffnungen >= 2,5 m² abziehen (VOB-Regel)
            if o_flaeche >= 2.5:
                abzug_beplankung += o_flaeche

        # Effektive Flächen nach Abzug
        flaeche_beplankung = max(flaeche - abzug_beplankung, 0)
        flaeche_daemmung = max(flaeche - abzug_daemmung, 0)

        # Anzahl Beplankungslagen
        lagen = 2 if typ in ("W115", "W116", "W118") else 1
        # Beidseitig
        seiten = 2

        # 1. CW-Ständer (Profile basieren auf Bruttofläche, nicht abgezogen)
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

        # 2. UW Boden/Decke (Profile basieren auf Bruttofläche)
        uw_lfm = math.ceil(flaeche * UW_PROFIL_LFM_PRO_M2_WAND * VERSCHNITT_PROFILE * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung=f"UW {cw_breite} Anschlussprofil",
            kategorie="UW-Profil",
            menge=uw_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=[f"UW {cw_breite}", f"UW{cw_breite}", "UW-Profil", "Anschlussprofil"],
        ))

        # 3. Beplankung (beidseitig, ggf. mehrlagig — mit Öffnungsabzug)
        platten_m2 = math.ceil(flaeche_beplankung * seiten * lagen * VERSCHNITT_PLATTEN * 10) / 10
        platte_typ = "GKF" if typ in ("W118",) else "GKB"
        positionen.append(MaterialPosition(
            bezeichnung=f"{platte_typ} 12.5mm Platte",
            kategorie="GK-Platte",
            menge=platten_m2,
            einheit="m²",
            herkunft=herkunft,
            suchbegriffe=[platte_typ, "Gipskarton", "12.5", "Platte"],
        ))

        # 4. Dämmung (alle Öffnungen abgezogen)
        daemmung_m2 = math.ceil(flaeche_daemmung * VERSCHNITT_DAEMMUNG * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung="Mineralwolle Trennwand",
            kategorie="Daemmung",
            menge=daemmung_m2,
            einheit="m²",
            herkunft=herkunft,
            suchbegriffe=["Mineralwolle", "Steinwolle", "Dämmung", "Trennwand", "Isover", "Rockwool"],
        ))

        # 5. Schrauben (basierend auf Beplankungsfläche)
        schrauben_stk = math.ceil(flaeche_beplankung * seiten * lagen * SCHRAUBEN_PRO_M2)
        positionen.append(MaterialPosition(
            bezeichnung="Schnellbauschrauben TN 3.5x25",
            kategorie="Befestigung",
            menge=schrauben_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Schnellbauschraube", "TN 3.5", "TN3.5x25"],
        ))

        # 6. Spachtel für Wände
        kb_mat_wand = get_material_pro_m2(typ) if typ else {}
        wand_spachtel_kg = math.ceil(flaeche * kb_mat_wand.get("spachtel_kg", 0.5) * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung="Fugenspachtel Wand (Uniflott o.ä.)",
            kategorie="Spachtel",
            menge=wand_spachtel_kg,
            einheit="kg",
            herkunft=herkunft,
            suchbegriffe=["Uniflott", "Fugenspachtel", "Spachtelmasse", "Fugenfüller"],
        ))

        # 7. Fugenband für Wände
        wand_fugenband_lfm = math.ceil(flaeche * kb_mat_wand.get("fugenband_lfm", 1.5) * 10) / 10
        positionen.append(MaterialPosition(
            bezeichnung="Bewehrungsstreifen Wand",
            kategorie="Band",
            menge=wand_fugenband_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["Bewehrungsstreifen", "Fugenband", "Kurt", "Papierband"],
        ))

        # 8. PE-Dichtungsband auf UW-Profilen (normativ MUSS)
        pe_band_wand_lfm = math.ceil(uw_lfm * 10) / 10  # gleiche Länge wie UW
        positionen.append(MaterialPosition(
            bezeichnung="PE-Dichtungsband (auf UW-Profil)",
            kategorie="Dichtung",
            menge=pe_band_wand_lfm,
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["Dichtungsband", "PE-Band", "Anschlussdichtung"],
        ))

        # 9. Dübel für UW-Profil-Befestigung (3 Stk/lfm)
        duebel_uw_stk = math.ceil(uw_lfm * 3)
        positionen.append(MaterialPosition(
            bezeichnung="Schlagdübel 6x40 (UW-Befestigung)",
            kategorie="Befestigung",
            menge=duebel_uw_stk,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Schlagdübel", "Dübel", "Metalldübel", "Anker"],
        ))

        # 10. Türzargen-Bekleidung (Zusatzposition wenn Türen vorhanden)
        if hat_tueren:
            tuer_count = sum(
                1 for o in wand_oeffnungen
                if "tuer" in (o.get("typ") or "").lower()
                or "tür" in (o.get("typ") or "").lower()
            )
            positionen.append(MaterialPosition(
                bezeichnung="Türzargen-Bekleidung",
                kategorie="Zubehoer",
                menge=tuer_count,
                einheit="Stk",
                herkunft=herkunft,
                suchbegriffe=["Türzarge", "Zargenbekleidung", "Zarge", "Umfassungszarge"],
            ))

    # ── Türöffnungen: UA-Profile + Zubehör ──
    oeffnungen = analyse_result.get("oeffnungen", [])
    for o in oeffnungen:
        if not isinstance(o, dict):
            continue
        typ = (o.get("typ") or "").lower()
        if "tür" not in typ and "door" not in typ and "tuer" not in typ:
            continue

        hoehe = o.get("hoehe_m") or 2.135  # Standard-Türhöhe
        breite = o.get("breite_m") or 0.885  # Standard-Türbreite
        wand_name = o.get("wand", "Trennwand")
        herkunft = f"Tür in {wand_name} ({breite:.2f}x{hoehe:.2f}m)"

        # UA-Aussteifungsprofile (2 Stk pro Tür, Länge = Raumhöhe ca. 2.75m)
        ua_laenge = hoehe + 0.10  # etwas länger als Türhöhe
        positionen.append(MaterialPosition(
            bezeichnung="UA-Aussteifungsprofil 75",
            kategorie="UA-Profil",
            menge=round(ua_laenge * 2, 1),  # 2 Stück pro Tür
            einheit="lfm",
            herkunft=herkunft,
            suchbegriffe=["UA-Profil", "Aussteifungsprofil", "UA 75", "Türpfosten"],
        ))

        # Türpfosten-Steckwinkel (4 pro Tür: 2 oben + 2 unten)
        positionen.append(MaterialPosition(
            bezeichnung="Steckwinkel für UA-Profil",
            kategorie="Zubehoer",
            menge=4,
            einheit="Stk",
            herkunft=herkunft,
            suchbegriffe=["Steckwinkel", "UA Winkel", "Türpfostenwinkel"],
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


# ── Differenzierte Verschnitt-Faktoren nach Material ─────────────────────────
# Angewendet NACH Aggregation, VOR Preisvergleich.
# Basiert auf Praxis-Erfahrungswerten für Trockenbau.
VERSCHNITT_FAKTOREN: dict[str, float] = {
    "GKB": 1.12,                # 12% Verschnitt auf Gipskartonplatten
    "GKF": 1.12,                # 12% auf Feuerschutzplatten
    "Aquapanel": 1.15,          # 15% auf Aquapanel (teuer, mehr Verschnitt)
    "CD 60/27": 1.05,           # 5% auf Tragprofile
    "UD 28/27": 1.05,           # 5% auf Randprofile
    "CW": 1.05,                 # 5% auf Ständerprofile
    "UW": 1.05,                 # 5% auf U-Profile
    "Schnellbauschrauben": 1.10,  # 10% Schrauben (fallen runter, verbiegen)
    "Direktabhänger": 1.05,     # 5%
    "Fugenspachtel": 1.10,      # 10%
    "Bewehrungsstreifen": 1.05, # 5%
}


def apply_verschnitt(positionen: list[MaterialPosition]) -> list[MaterialPosition]:
    """Wendet differenzierte Verschnitt-Faktoren auf aggregierte Positionen an.

    Prüft ob die Bezeichnung einer Position einen der Schlüssel aus
    VERSCHNITT_FAKTOREN enthält. Falls ja, wird die Menge multipliziert
    und verschnitt_prozent gesetzt.
    """
    for pos in positionen:
        bez_lower = pos.bezeichnung.lower()
        for key, faktor in VERSCHNITT_FAKTOREN.items():
            if key.lower() in bez_lower:
                prozent = round((faktor - 1.0) * 100)
                pos.menge = round(pos.menge * faktor, 1)
                pos.verschnitt_prozent = prozent
                log.debug(
                    "verschnitt_applied",
                    bezeichnung=pos.bezeichnung,
                    faktor=faktor,
                    prozent=prozent,
                )
                break  # Nur der erste Treffer zählt
    return positionen


# ── Produkt-Aliase für besseren Preislisten-Match ────────────────────────────
PRODUKT_ALIASE: dict[str, list[str]] = {
    "GKB": ["Gipskarton", "Gipskartonplatte", "Knauf Diamant", "Rigips"],
    "GKF": ["Gipskarton Feuerschutz", "GKFi", "Fireboard", "Feuerschutzplatte"],
    "CD 60/27": ["CD-Profil", "Tragprofil", "CD60", "C-Profil"],
    "UD 28/27": ["UD-Profil", "Randprofil", "UD28", "U-Profil"],
    "CW 75": ["CW-Profil", "Ständerprofil", "CW75"],
    "UW 75": ["UW-Profil", "UW75", "Anschlussprofil"],
    "Uniflott": ["Fugenspachtel", "Spachtelmasse", "Fugenfüller"],
    "Aquapanel": ["Aquapanel Indoor", "Zementplatte", "Aquapanel Outdoor"],
    "Schnellbauschrauben": ["TN 3.5x25", "Gipsplattenschraube", "TN3.5", "Schnellbauschraube"],
    "Direktabhänger": ["Abhänger", "Nonius", "Federbügel"],
    "Bewehrungsstreifen": ["Fugenband", "Kurt", "Papierband"],
}


def _expand_suchbegriffe(suchbegriffe: list[str]) -> list[str]:
    """Erweitert Suchbegriffe um alle bekannten Aliase.

    Wenn ein Suchbegriff einen Schlüssel aus PRODUKT_ALIASE enthält (oder
    umgekehrt), werden alle zugehörigen Aliase hinzugefügt.
    """
    expanded = set(suchbegriffe)
    for term in suchbegriffe:
        term_lower = term.lower()
        for key, aliases in PRODUKT_ALIASE.items():
            # Check if term matches the key or any alias
            key_lower = key.lower()
            if key_lower in term_lower or term_lower in key_lower:
                expanded.add(key)
                expanded.update(aliases)
            else:
                for alias in aliases:
                    if alias.lower() in term_lower or term_lower in alias.lower():
                        expanded.add(key)
                        expanded.update(aliases)
                        break
    return list(expanded)


async def _has_pg_trgm(db: AsyncSession) -> bool:
    """Check if pg_trgm extension is available."""
    try:
        result = await db.execute(
            select(func.count()).select_from(
                select(func.literal_column("1"))
                .where(func.literal_column("extname") == "pg_trgm")
                .select_from(func.literal_column("pg_extension"))
                .subquery()
            )
        )
        return False  # Safe fallback — actual check below
    except Exception:
        return False


async def preise_matchen(
    positionen: list[MaterialPosition],
    db: AsyncSession,
) -> list[MaterialPosition]:
    """Matcht jede Position gegen die Produkte aller Preislisten.

    Improvements over naive approach:
    - Single batched query with OR across all search terms
    - pg_trgm trigram similarity if available, fallback to ILIKE
    - Unit normalization: Pkg → per-piece price when menge_pro_einheit is set
    - Scoring: exact category match gets priority
    """
    from sqlalchemy import or_, text, literal_column

    # Check pg_trgm availability once
    use_trigram = False
    try:
        await db.execute(text("SELECT similarity('test', 'test')"))
        use_trigram = True
    except Exception:
        await db.rollback()

    for pos in positionen:
        if not pos.suchbegriffe:
            continue

        # Expand search terms with known product aliases
        search_terms = _expand_suchbegriffe(pos.suchbegriffe)

        # Build ONE query that ORs all search terms
        if use_trigram:
            # Trigram similarity: find products where ANY search term is similar
            similarity_conditions = []
            for term in search_terms:
                # Use a collision-safe bind param name
                param_name = f"term_{abs(hash(term)) & 0xFFFF}_{len(term)}"
                similarity_conditions.append(
                    text(f"similarity(produkte.bezeichnung, :{param_name}) > 0.15")
                    .bindparams(**{param_name: term})
                )
                # Also include ILIKE for exact substring matches
                similarity_conditions.append(
                    Produkt.bezeichnung.ilike(f"%{term}%")
                )
            filter_expr = or_(*similarity_conditions)
        else:
            # Fallback: ILIKE with all terms ORed
            ilike_conditions = [
                Produkt.bezeichnung.ilike(f"%{term}%")
                for term in search_terms
            ]
            filter_expr = or_(*ilike_conditions)

        result = await db.execute(
            select(Produkt, Preisliste.anbieter)
            .join(Preisliste)
            .where(
                Preisliste.status == "completed",
                Produkt.verfuegbar == True,
                filter_expr,
            )
            .order_by(Produkt.preis_netto.asc())
            .limit(30)
        )

        alle = []
        seen = set()
        for produkt, anbieter in result.all():
            dedup_key = f"{anbieter}|{produkt.bezeichnung}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            preis = float(produkt.preis_netto)

            # Unit normalization: convert package prices to per-piece/per-unit
            # for better comparison across suppliers with different packaging.
            einheit_normalized = produkt.einheit or ""
            mpe = float(produkt.menge_pro_einheit) if produkt.menge_pro_einheit else 0

            if (
                einheit_normalized.lower() in ("pkg", "paket", "bund", "ve")
                and mpe > 0
            ):
                preis = round(preis / mpe, 4)
                # Determine target unit: if the position expects m², keep m²;
                # otherwise default to Stk.
                if pos.einheit == "m²" and einheit_normalized.lower() in ("pkg", "paket"):
                    einheit_normalized = "m²"
                else:
                    einheit_normalized = "Stk"

            # Scoring: exact category match gets priority (lower score = better)
            score = preis  # base score is price
            if produkt.kategorie and produkt.kategorie == pos.kategorie:
                score *= 0.9  # 10% bonus for exact category match

            alle.append({
                "anbieter": anbieter,
                "bezeichnung": produkt.bezeichnung,
                "preis_netto": preis,
                "einheit": einheit_normalized,
                "artikel_nr": produkt.artikel_nr,
                "_score": score,
            })

        # Sort by score (category-adjusted price)
        alle.sort(key=lambda a: a["_score"])

        best_price = None
        best_anbieter = None
        if alle:
            best_price = alle[0]["preis_netto"]
            best_anbieter = alle[0]["anbieter"]

        # Remove internal _score before exposing
        for a in alle:
            a.pop("_score", None)

        pos.bester_preis = best_price
        pos.bester_anbieter = best_anbieter
        pos.alle_preise = alle[:5]  # Top 5

    return positionen


async def erstelle_kalkulation(
    analyse_result: dict,
    db: AsyncSession,
    custom_params: dict | None = None,
    projekt_adresse: str | None = None,
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

    projekt_adresse: optional project address for automatic Anfahrtskosten
    """
    params = custom_params or {}

    # --- Enrich: Decken-Flächen aus Raum-Daten ergänzen wenn fehlend ---
    raeume = analyse_result.get("raeume", [])
    raum_flaeche_map = {}
    for r in raeume:
        key = r.get("raum_nr") or r.get("bezeichnung", "")
        if key and r.get("flaeche_m2"):
            raum_flaeche_map[key] = r["flaeche_m2"]
    for d in analyse_result.get("decken", []):
        if not d.get("flaeche_m2"):
            # Try to match by raum_nr or raum name
            raum_nr = d.get("raum_nr") or ""
            raum_name = d.get("raum") or ""
            flaeche = raum_flaeche_map.get(raum_nr) or raum_flaeche_map.get(raum_name)
            if flaeche:
                d["flaeche_m2"] = flaeche
                log.info("decke_flaeche_from_raum", raum=raum_name, raum_nr=raum_nr, flaeche=flaeche)

    # --- Bug fix: early return when no elements exist ---
    has_decken = any(
        (d.get("flaeche_m2") or 0) > 0 and not d.get("entfaellt")
        for d in analyse_result.get("decken", [])
    )
    has_waende = any(
        (w.get("flaeche_m2") or (w.get("laenge_m", 0) * w.get("hoehe_m", 0))) > 0
        for w in analyse_result.get("waende", [])
    )
    # Also check if we have rooms with areas (can derive from those)
    has_raeume_with_area = any(
        (r.get("flaeche_m2") or 0) > 0 for r in raeume
    )
    if not has_decken and not has_waende and not has_raeume_with_area:
        return {
            "positionen": [],
            "gesamt_netto": 0.0,
            "positionen_mit_preis": 0,
            "positionen_ohne_preis": 0,
            "positionen_gesamt": 0,
            "bestellliste": [],
            "kundenangebot": {},
            "keine_elemente": True,
            "hinweis": (
                "Keine kalkulierbaren Bauelemente vorhanden. "
                "Die Analyse hat keine Wände oder Decken mit gültigen Maßen erkannt."
            ),
        }

    # 1. Materialien ableiten
    positionen = materialliste_aus_analyse(analyse_result)
    log.info("materialliste_generiert", einzelpositionen=len(positionen))

    # 2. Aggregieren (gleiche Materialien zusammenfassen)
    aggregiert = aggregiere_positionen(positionen)
    log.info("materialliste_aggregiert", positionen=len(aggregiert))

    # 2b. Verschnitt-Faktoren anwenden (NACH Aggregation, VOR Preisvergleich)
    aggregiert = apply_verschnitt(aggregiert)
    log.info("verschnitt_applied", positionen_mit_verschnitt=sum(
        1 for p in aggregiert if p.verschnitt_prozent is not None
    ))

    # 2c. Apply mengen_overrides if provided (AFTER verschnitt, so user overrides win)
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

        pos_dict: dict = {
            "bezeichnung": pos.bezeichnung,
            "kategorie": pos.kategorie,
            "menge": pos.menge,
            "einheit": pos.einheit,
            "einzelpreis": pos.bester_preis,
            "gesamtpreis": gesamtpreis,
            "anbieter": pos.bester_anbieter,
            "alternativen": pos.alle_preise or [],
            "herkunft": pos.herkunft[:200],
        }
        if pos.verschnitt_prozent is not None:
            pos_dict["verschnitt_prozent"] = pos.verschnitt_prozent
            pos_dict["verschnitt_hinweis"] = f"inkl. {pos.verschnitt_prozent:.0f}% Verschnitt"
        result_positionen.append(pos_dict)

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

    # Automatische Anfahrtskosten hinzufuegen wenn Adresse bekannt
    # und nicht bereits manuell in zusatzkosten enthalten
    has_anfahrt = any(
        "anfahrt" in (z.get("bezeichnung") or "").lower()
        for z in zusatzkosten
    )
    if not has_anfahrt and projekt_adresse:
        anfahrt_betrag = _anfahrtskosten_fuer_adresse(projekt_adresse)
        if anfahrt_betrag is not None and anfahrt_betrag > 0:
            zusatzkosten = [
                {"bezeichnung": "Anfahrtskosten", "betrag": anfahrt_betrag},
                *zusatzkosten,
            ]

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

    # Lohnstunden: differenziert nach System-Typ (STUNDEN_PRO_M2 Lookup)
    # Decken: system-spezifische h/m², Fallback auf custom_params oder Pauschale
    decken_stunden = 0.0
    for d in analyse_result.get("decken", []):
        if d.get("entfaellt"):
            continue
        fl = d.get("flaeche_m2") or 0
        sys_key = (d.get("system") or "").upper().strip()
        h_pro_m2 = STUNDEN_PRO_M2.get(sys_key, stunden_pro_m2_decke)
        decken_stunden += fl * h_pro_m2

    # Wände: typ-spezifische h/m², Fallback auf custom_params oder Pauschale
    wand_stunden = 0.0
    for w in analyse_result.get("waende", []):
        fl = w.get("flaeche_m2") or (w.get("laenge_m", 0) * w.get("hoehe_m", 0))
        typ_key = (w.get("typ") or "").upper().strip()
        h_pro_m2 = STUNDEN_PRO_M2.get(typ_key, stunden_pro_m2_wand)
        wand_stunden += fl * h_pro_m2

    gesamt_stunden = round(decken_stunden + wand_stunden, 1)
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

    # Anfahrtskosten separat ausweisen
    anfahrtskosten_betrag = 0.0
    for z in zusatzkosten:
        if "anfahrt" in (z.get("bezeichnung") or "").lower():
            anfahrtskosten_betrag += z.get("betrag", 0)

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
        "anfahrtskosten": round(anfahrtskosten_betrag, 2),
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


async def erstelle_projekt_kalkulation(
    projekt_id: UUID,
    db: AsyncSession,
    custom_params: dict | None = None,
) -> dict:
    """Aggregierte Kalkulation über alle abgeschlossenen Analysen eines Projekts.

    1. Fetches all completed AnalyseErgebnisse for the project
    2. Merges all raeume, waende, decken, oeffnungen across analyses
    3. Calls erstelle_kalkulation() with the merged data
    4. Returns same structure but with additional analysen_count field
    """
    from app.models.analyse_job import AnalyseJob
    from app.models.analyse_ergebnis import AnalyseErgebnis
    from app.models.projekt import Projekt
    from sqlalchemy.orm import selectinload

    # Fetch project address for Anfahrtskosten
    projekt_result = await db.execute(
        select(Projekt).where(Projekt.id == projekt_id)
    )
    projekt = projekt_result.scalar_one_or_none()
    projekt_adresse = projekt.adresse if projekt else None

    # Fetch all completed analyse jobs for this project
    result = await db.execute(
        select(AnalyseJob)
        .options(selectinload(AnalyseJob.ergebnis))
        .where(
            AnalyseJob.projekt_id == projekt_id,
            AnalyseJob.status == "completed",
        )
        .order_by(AnalyseJob.created_at.asc())
    )
    jobs = result.scalars().all()

    completed_jobs = [j for j in jobs if j.ergebnis is not None]
    if not completed_jobs:
        return {
            "positionen": [],
            "gesamt_netto": 0.0,
            "positionen_mit_preis": 0,
            "positionen_ohne_preis": 0,
            "positionen_gesamt": 0,
            "bestellliste": [],
            "kundenangebot": {},
            "analysen_count": 0,
            "keine_elemente": True,
            "hinweis": "Keine abgeschlossenen Analysen mit Bauelementen vorhanden.",
        }

    # Merge all analyse results into one combined dict
    merged: dict = {
        "raeume": [],
        "waende": [],
        "decken": [],
        "oeffnungen": [],
        "details": [],
    }
    for job in completed_jobs:
        erg = job.ergebnis
        merged["raeume"].extend(erg.raeume or [])
        merged["waende"].extend(erg.waende or [])
        merged["decken"].extend(erg.decken or [])
        merged["oeffnungen"].extend(erg.oeffnungen or [])
        merged["details"].extend(erg.details or [])

    log.info(
        "projekt_kalkulation_merged",
        projekt_id=str(projekt_id),
        analysen=len(completed_jobs),
        raeume=len(merged["raeume"]),
        waende=len(merged["waende"]),
        decken=len(merged["decken"]),
    )

    # Run the standard kalkulation on merged data
    kalkulation = await erstelle_kalkulation(
        merged, db, custom_params=custom_params, projekt_adresse=projekt_adresse,
    )
    kalkulation["analysen_count"] = len(completed_jobs)

    return kalkulation
