"""Materialrezepte: Pro System → Liste benötigter Materialien pro m² (oder Stk/lfm).

Diese Rezepte sind universal (aus Knauf-Systemwissen). Sie definieren WELCHE Materialien
benötigt werden, nicht zu welchem PREIS — der Preis kommt aus der Kundenpreisliste.

Jedes Rezept definiert auch typische Zeitansätze (h pro Einheit).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaterialBedarf:
    """Ein Material-Posten im Rezept."""

    # DNA-Pattern zum Matchen: offene Spezifikation, Matcher darf Platzhalter interpretieren.
    # Format: "Hersteller|Kategorie|Produktname|Abmessungen|Variante"
    # Leerer String = "egal"
    dna_pattern: str
    menge_pro_einheit: float   # z.B. 1.05 m² GKB pro m² W112
    basis_einheit: str          # "m²", "lfm", "Stk"
    # Fallback-Preis in €/Einheit falls Material nicht in Kundenpreisliste gefunden wird.
    # Typisch aus Branchen-Durchschnitt. Verhindert Unterkalkulation bei Lücken in
    # der Preisliste des Kunden.
    fallback_preis_eur: float = 0.0
    # Wenn True: kein "Kein Preis"-Warning wenn fehlt (z.B. UW-Profile oft nicht separat
    # in Preislisten weil im CW-Gesamtsystem inkludiert).
    optional: bool = False
    # B+4.13 Iteration 5b (2026-04-28): Hersteller-Mat-Nr fuer praezisen
    # Treffer in der Lieferanten-Preisliste. Wenn gesetzt, hat exakter
    # article_number-Match in supplier_price-Stage Vorrang vor Produktname-
    # Fuzzy-Match. Beispiele aus Knauf-Katalog Seite 240 (Schachtwand W628B,
    # bestaetigt durch Harun's Vater, Trockenbau Feichtenbeiner Ulm).
    mat_nr: str = ""


@dataclass
class Rezept:
    system: str                 # "W112", "W115", ...
    beschreibung: str
    zieleinheit: str            # Einheit der Wand: "m²" (typisch)
    zeit_h_pro_einheit: float   # Facharbeiter-Zeit pro m²
    materialien: list[MaterialBedarf]


# ---------------------------------------------------------------------------
# REZEPTE
# ---------------------------------------------------------------------------

REZEPTE: dict[str, Rezept] = {
    # --- Trennwände ---------------------------------------------------------
    # Hinweis: W112 hat Standard 2.10 m2/m2 GKB (= 1-lagig beidseitig, 1.05 m2
    # pro Seite x 2 Seiten). Beschreibung wurde 2026-04-20 auf die offizielle
    # Knauf-Formulierung "zweilagig beplankt" praezisiert (die "zwei Lagen"
    # beziehen sich auf beide Seiten, nicht auf Doppellagen pro Seite - das
    # waere W113).
    # KALIBRIERT 2026-04-28: Aktueller EP von ~62 EUR/m² (Salach-Innenwand
    # 100mm) wurde von Harun's Vater (Trockenbau Feichtenbeiner, Ulm) als
    # sehr guter Richtwert bestaetigt. Rezept also korrekt eingestellt —
    # bewusst keine Aenderungen an Mengen oder Zeitansatz. Falls in einer
    # spaeteren Iteration Knauf-Mat-Nrn fuer W112 vorliegen, koennen sie
    # analog zu W628B als mat_nr=... ergaenzt werden.
    "W112": Rezept(
        system="W112",
        beschreibung="W112.de — Einfachstaenderwerk, zweilagig beplankt (1 Lage GKB je Seite, CW75) [Praxis-kalibriert 2026-04-28]",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.55,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 2.10, "m²"),
            MaterialBedarf("|Profile|CW|75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.05, "Stk", optional=True),  # ~25 Stk/m²; Faktor 0.05 = 25/500
            MaterialBedarf("|Spachtel||Universal|", 0.40, "kg", optional=True),
        ],
    ),
    "W113": Rezept(
        # NEU 2026-04-20 (KNAUF_KORREKTUREN.md K-10): W113.de = Einfachstaenderwerk
        # DREILAGIG (1.5 Lagen je Seite oder 3 Lagen auf einer Seite je nach Variante).
        # Offizielles Material: 3 Lagen Gipsplatten gesamt, typischerweise zur
        # Hoeherbelastung / verstaerkten Schallschutz.
        # Vorher: W113 wurde via W11-Prefix auf W112 gemappt, was die dritte
        # Lage unterschlug.
        system="W113",
        beschreibung="W113.de — Einfachstaenderwerk, dreilagig beplankt (erhoehter Schallschutz / mechanische Anforderung)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.85,  # zwischen W112 (0.55) und W115 (0.75) mit mehr Material
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 3.15, "m²"),  # 3 Lagen gesamt (1.5 je Seite, oder 2+1)
            MaterialBedarf("|Profile|CW|75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.06, "Stk", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.03, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.55, "kg", optional=True),
        ],
    ),
    "W115": Rezept(
        system="W115",
        beschreibung="Schallschutz-Trennwand, 2-lagig GKB 12,5mm beidseitig",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.75,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 4.20, "m²"),
            MaterialBedarf("|Profile|CW|75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.06, "Stk", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.03, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", optional=True),
        ],
    ),
    "W116": Rezept(
        # KORREKTUR 2026-04-20 (KNAUF_KORREKTUREN.md K-9):
        # W116.de = Doppelstaenderwerk VERLASCHT (beide Profilreihen mechanisch
        # verbunden, Installationswand-Variante). "Entkoppelt" ist W115 — W116
        # ist das verlaschte Pendant.
        system="W116",
        beschreibung="W116.de — Doppelstaenderwerk verlascht (beide Reihen mechanisch verbunden, Installationswand-Variante)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.95,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 4.20, "m²"),
            MaterialBedarf("|Profile|CW|75|", 3.60, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 1.60, "lfm", optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.06, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.70, "kg", optional=True),
        ],
    ),
    "W118": Rezept(
        system="W118",
        beschreibung="Brandschutzwand F90, 2-lagig GKF",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.85,
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 4.20, "m²"),
            MaterialBedarf("|Profile|CW|75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.06, "Stk", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.03, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", optional=True),
        ],
    ),
    "W135": Rezept(
        # KORREKTUR 2026-04-20 (KNAUF_KORREKTUREN.md K-1): W135 ist offiziell eine
        # Brandwand (Sonderbauwand anstelle Brandwand), Einfachstaenderwerk
        # 2-lagig + Stahlblecheinlage je Seite, F90-A+mB.
        # Quelle: knauf.com/de-DE/.../w13-de-metallstaenderwaende-anstelle-von-brandwaenden
        # Vorheriges Label "Installationswand" war falsch — Installation-DS ist W116.
        system="W135",
        beschreibung="W135.de — Brandwand Einfachstaenderwerk 2-lagig + Stahlblecheinlage (F90-A+mB)",
        zieleinheit="m²",
        zeit_h_pro_einheit=1.10,  # wg. Stahlblech-Handling (wie vormals W135_Stahlblech)
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 4.20, "m²"),  # 2x beidseitig
            MaterialBedarf("|Profile|CW|75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Stahlblech|Einlage|0.5mm|", 2.00, "m²"),  # je Seite
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.06, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", optional=True),
        ],
    ),
    # --- Vorsatzschalen -----------------------------------------------------
    # BREAKING SEMANTIC CHANGE 2026-04-20 (KNAUF_KORREKTUREN.md K-2):
    # W623 und W625 waren im Projekt vertauscht. Offizielle Knauf-Definition:
    #   W623.de = mit CD 60/27, direkt befestigt
    #   W625.de = mit CW-Profil, einlagig beplankt (freistehend)
    # Quelle: knauf.com/de-DE/.../w61-de-vorsatzschalen
    # Rezepte wurden entsprechend getauscht.
    "W623": Rezept(
        system="W623",
        beschreibung="W623.de — Vorsatzschale direkt befestigt mit CD 60/27 (Direktabhaenger)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.45,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²"),
            MaterialBedarf("|Profile|CD|60/27|", 2.00, "lfm"),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.03, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.25, "kg", optional=True),
        ],
    ),
    "W625": Rezept(
        system="W625",
        beschreibung="W625.de — Vorsatzschale freistehend mit CW-Profil, einlagig beplankt",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.50,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²"),
            MaterialBedarf("|Profile|CW|50|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|50|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.03, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.25, "kg", optional=True),
        ],
    ),
    # --- Schachtwände (offizielle Knauf-Nomenklatur seit 2026-04-20) ----
    # KNAUF_KORREKTUREN.md K-12: Umbenennung auf offizielle W62X.de-Codes.
    # Die alten internen Namen (W625S, W626S, W631S, W632) werden via
    # resolve_rezept-Aliase weiterhin akzeptiert (Backward-Compatibility).
    # Offizielle Knauf-Familie W62.de (einseitig):
    #   W628A.de = freispannend bis 2m Schachtbreite (keine UK)
    #   W628B.de = CW-Einfachstaender
    #   W629.de  = CW-Doppelstaender
    #   W635.de  = UW-Doppelstaender
    # Quelle: knauf.com/de-DE/.../w62-de-schachtwaende
    "W628A": Rezept(
        # Vormals "W625S" im Projekt. Fachlich ist das einseitige Beplanken mit
        # Fireboard — der Knauf-W628A ist die freispannende Variante bis 2m
        # Schachtbreite (keine Zwischen-UK).
        system="W628A",
        beschreibung="W628A.de — Schachtwand einseitig freispannend (bis 2m Schachtbreite, ohne Unterkonstruktion, unbegrenzte Hoehe)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.90,
        materialien=[
            MaterialBedarf("Knauf|Gipskarton|Fireboard|20mm|", 2.10, "m²"),
            MaterialBedarf("|Profile|CW|75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.04, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", optional=True),
        ],
    ),
    "W628B": Rezept(
        # Knauf-W628B = Schachtwand einseitig mit CW-Einfachstaender (Standardfall
        # fuer Schachtbreiten > 2m).
        #
        # KALIBRIERT 2026-04-28: Komplettes Rezept ersetzt durch Knauf-Katalog
        # Seite 240 (Material-Liste pro m² W628B/CW75) PLUS Praxis-Bestaetigung
        # durch Harun's Vater (Trockenbau Feichtenbeiner, Ulm). Hersteller-
        # Mat-Nrn pro Eintrag ermoeglichen exakten Lookup in Knauf/Kemmler-
        # Preislisten (article_number-Match Vorrang vor Fuzzy).
        #
        # Standard-Plattentyp = GKB (Schachtwaende ohne Brandschutz-Anforderung).
        # Bei F30/F60/F90 in der Position wird automatisch auf GKF aufgewertet
        # (siehe _apply_plattentyp_override + _AUTO_FIRE_UPGRADE_WHITELIST).
        #
        # Lohn: 40 min/m² = 0.667 h/m² @ Stundensatz 60 EUR = 40 EUR/m² Lohn.
        system="W628B",
        beschreibung="W628B.de — Schachtwand einseitig mit CW-Einfachstaender (Knauf-Katalog S.240, kalibriert 2026-04-28)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.667,  # 40 min Montage/m²
        materialien=[
            # Unterkonstruktion
            # Manufacturer bewusst leer: Kemmler-Bestand fuehrt CW/UW-Profile
            # ohne Hersteller-Tag — DNA "Knauf|Profile|UW|75|" wuerde durch
            # die manufacturer-Filterung in price_lookup ALLE generischen
            # Kemmler-Eintraege ausschliessen.
            MaterialBedarf("|Profile|UW|75|", 0.7, "lfm", mat_nr="00003376"),
            MaterialBedarf("|Profile|CW|75|", 2.0, "lfm", mat_nr="00003261"),
            # Befestigung
            MaterialBedarf("|Beschlag|Drehstiftduebel|K6 35|", 0.7, "Stk", mat_nr="00003537", optional=True),
            MaterialBedarf("|Dichtung|Dichtungsband|70mm|", 1.2, "lfm", mat_nr="00003469", optional=True),
            # Daemmung — Knauf TP 115, 60mm (Knauf-spezifisches Produkt)
            MaterialBedarf("|Daemmung|TP 115|60mm|", 1.0, "m²", mat_nr="2304372"),
            # Beplankung — GKB als Default (12.5mm). Override auf GKF bei F-Rating.
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 2.0, "m²", mat_nr="00002892"),
            # Schrauben
            MaterialBedarf("|Schrauben|TN 3.5|3.5x25|", 7.0, "Stk", mat_nr="00003504", optional=True),
            MaterialBedarf("|Schrauben|TN 3.5|3.5x35|", 15.0, "Stk", mat_nr="00003505", optional=True),
            # Spachtel + Fugen — Uniflott und Kurt sind Knauf-typische Bezeichnungen
            MaterialBedarf("|Spachtel|Uniflott||", 0.4, "kg", mat_nr="00003114", optional=True),
            MaterialBedarf("|Trennstreifen|Trenn-Fix|65mm|", 0.9, "lfm", mat_nr="00057871", optional=True),
            MaterialBedarf("|Fugendeckstreifen|Kurt|75|", 0.9, "m", mat_nr="00099382", optional=True),
        ],
    ),
    "W629": Rezept(
        # Vormals "W631S" im Projekt. Knauf-W629 = CW-Doppelstaender (fuer hohe
        # Wandhoehen oder groessere Schachtbreiten bis ~5m).
        system="W629",
        beschreibung="W629.de — Schachtwand einseitig mit CW-Doppelstaender (grosse Schachtbreiten bis 5m)",
        zieleinheit="m²",
        zeit_h_pro_einheit=1.05,  # hoeherer Aufwand wg. Doppelstaender
        materialien=[
            MaterialBedarf("Knauf|Gipskarton|Fireboard|20mm|", 2.10, "m²"),
            MaterialBedarf("|Profile|CW|100|", 3.60, "lfm"),  # doppelte Profilreihe
            MaterialBedarf("|Profile|UW|100|", 1.60, "lfm", optional=True),
            MaterialBedarf("|Daemmung||80mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.06, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.65, "kg", optional=True),
        ],
    ),
    "W635": Rezept(
        # Vormals "W632" im Projekt. Knauf-W635 = UW-Doppelstaender (schlanker
        # Aufbau mit UW-Profilen statt CW fuer begrenzten Bauraum).
        system="W635",
        beschreibung="W635.de — Schachtwand einseitig mit UW-Doppelstaender (schlanker Aufbau)",
        zieleinheit="m²",
        zeit_h_pro_einheit=1.00,
        materialien=[
            MaterialBedarf("Knauf|Gipskarton|Fireboard|20mm|", 2.10, "m²"),
            MaterialBedarf("|Profile|UW|75|", 3.60, "lfm"),  # doppelte Reihe aus UW
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.05, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", optional=True),
        ],
    ),
    # --- Decken ------------------------------------------------------------
    # KORREKTUR 2026-04-20 (KNAUF_KORREKTUREN.md K-6): D112/D113 unterscheiden
    # sich offiziell NICHT nach Beplankungszahl, sondern nach UK-Art:
    #   D112.de = Metall-UK Standard (Grund- + Tragprofile, auf Abhaengern)
    #   D113.de = Metall-UK niveaugleich (niedrige Aufbauhoehe)
    # Beplankung (1- oder 2-lagig) ist ORTHOGONAL — kann aus plattentyp/
    # feuerwiderstand abgeleitet werden.
    # Materialmenge GKB bleibt bei 1.05 m2/m2 als Default (1-lagig);
    # fuer 2-lagig muss Kalkulation via feuerwiderstand=F90 o.ae. erkennen
    # und Menge verdoppeln (TODO in kalkulation.py fuer spaetere Runde).
    "D112": Rezept(
        system="D112",
        beschreibung="D112.de — Plattendecke mit Metall-UK (Grund- + Tragprofile CD60/27 auf Abhaengern, Standard)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.55,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²"),
            MaterialBedarf("|Profile|CD|60/27|", 3.20, "lfm"),
            MaterialBedarf("|Profile|UD|", 0.60, "lfm"),
            # Abhänger/Clip pauschal pro m² (häufig nicht in Preisliste — ggf. kein Match)
            MaterialBedarf("|Daemmung||40mm|", 0.60, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.35, "kg", optional=True),
        ],
    ),
    "D113": Rezept(
        system="D113",
        beschreibung="D113.de — Plattendecke mit Metall-UK niveaugleich (Grund- + Tragprofile gleichebene CD60/27, niedrige Aufbauhoehe)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.65,  # niveaugleich = schwieriger zu montieren als Standard-D112
        materialien=[
            # Beplankung 1-lagig als Default. Bei F90/F60 Anforderung verdoppelt die
            # Kalkulation (TODO: over feuerwiderstand-Feld).
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²"),
            MaterialBedarf("|Profile|CD|60/27|", 3.20, "lfm"),
            MaterialBedarf("|Profile|UD|", 0.60, "lfm"),
            MaterialBedarf("|Daemmung||40mm|", 0.60, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.35, "kg", optional=True),
        ],
    ),
    "D116": Rezept(
        # NEU 2026-04-20: D116.de war bisher nur als Knowledge-Datenpunkt, ohne
        # eigenes Rezept. Weitspannende Unterdecke mit UA 50 Grundprofilen.
        system="D116",
        beschreibung="D116.de — Plattendecke Metall-UK weitspannend (UA 50 Grundprofile + CD60/27 Tragprofile, grosse Abhaengeabstaende)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.60,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²"),
            MaterialBedarf("|Profile|UA|50|", 1.20, "lfm"),  # Grundprofil UA 50
            MaterialBedarf("|Profile|CD|60/27|", 3.20, "lfm"),  # Tragprofil
            MaterialBedarf("|Daemmung||40mm|", 0.60, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.35, "kg", optional=True),
        ],
    ),
    "D131": Rezept(
        # KORREKTUR/NEU 2026-04-20 (KNAUF_KORREKTUREN.md K-7): D131.de ist offiziell
        # eine freitragende Decke UNTER HOLZBALKENDECKE (nur an Waenden befestigt,
        # keine Abhaenger). Der bisherige Fallback "D131 -> D113" war zu generisch.
        # Quelle: knauf.com/de-DE/.../d13-de-freitragende-decken
        system="D131",
        beschreibung="D131.de — Freitragende Decke unter Holzbalkendecke (nur Wandbefestigung, kein Abhaenger)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.85,  # aufwendig wg. Wandbefestigung, Spannweite
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 2.10, "m²"),  # typisch 2-lagig GKF
            MaterialBedarf("|Profile|CW|75|", 2.50, "lfm"),  # Tragprofile spannen frei
            MaterialBedarf("|Profile|UW|75|", 1.00, "lfm", optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.55, "kg", optional=True),
        ],
    ),
    "OWA_MF": Rezept(
        system="OWA_MF",
        beschreibung="OWA-Mineralfaser-Rasterdecke (Einlegesystem, 625x625 oder 625x1250)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.45,  # realistischer als 0.35
        materialien=[
            # Rasterplatte (OWA Bolero/Sinfonia/ähnlich) — DNA breit lassen
            MaterialBedarf("OWA||||", 1.05, "m²"),
            # T-Profile: Hauptprofil 24mm ~3 lfm/m², Randprofil L 0.5 lfm/m²
            # Falls Kategorie "Profile" oder "Rasterdecke" vorhanden
            MaterialBedarf("||T-Profil||", 3.00, "lfm"),
            MaterialBedarf("||Randprofil||", 0.50, "lfm"),
            # Abhänger
            MaterialBedarf("||Schnellabhänger||", 1.20, "Stk"),
        ],
    ),
    "W131": Rezept(
        # KORREKTUR 2026-04-20 (KNAUF_KORREKTUREN.md K-4): W131 ist offiziell
        # Einfachstaenderwerk mit 2-3 Lagen GKF UND Stahlblecheinlage je Seite,
        # F90-A+mB (Sonderbauwand anstelle Brandwand). Stahlblech ist PFLICHT.
        # Quelle: knauf.com/de-DE/.../w13-de-metallstaenderwaende-anstelle-von-brandwaenden
        system="W131",
        beschreibung="W131.de — Brandwand Einfachstaenderwerk 2-lagig GKF + Stahlblecheinlage (F90-A+mB, bis 9m Wandhoehe)",
        zieleinheit="m²",
        zeit_h_pro_einheit=1.10,  # erhoeht wegen Stahlblech-Handling
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 4.20, "m²"),  # 2-lagig beidseitig
            MaterialBedarf("|Profile|CW|100|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|100|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Stahlblech|Einlage|0.5mm|", 2.00, "m²"),  # je Seite, Pflicht
            MaterialBedarf("|Daemmung||80mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.70, "kg", optional=True),
        ],
    ),
    # W135_Stahlblech entfernt (KNAUF_KORREKTUREN.md K-1, 2026-04-20):
    # Das war Duplikat - W135 ist selbst schon eine Brandwand mit Stahlblech.
    # Alte Codes "W135_Stahlblech" / "A+M" / "Einbruchhemmung" werden jetzt via
    # resolve_rezept-Alias auf W135 gemappt (siehe aliases-Dict weiter unten).
    "W133": Rezept(
        # NEU 2026-04-20 (KNAUF_KORREKTUREN.md K-5): W133 ist Einfachstaenderwerk
        # DREILAGIG + Stahlblech (nicht Doppelstaender, wie vorher in der Doku stand).
        # Bisher wurde W133 im resolve_rezept auf W131 gemappt - das liefert nur
        # 2 GKF-Lagen, zu wenig Material. Eigenes Rezept ist noetig.
        # Quelle: knauf.com/de-DE/.../w13-de-metallstaenderwaende-anstelle-von-brandwaenden
        system="W133",
        beschreibung="W133.de — Brandwand Einfachstaenderwerk 3-lagig GKF + Stahlblecheinlage (F90-A+mB)",
        zieleinheit="m²",
        zeit_h_pro_einheit=1.25,  # 3-lagig + Stahlblech = hoechster Aufwand
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 6.30, "m²"),  # 3x beidseitig = 6 m²/m²
            MaterialBedarf("|Profile|CW|100|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|100|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Stahlblech|Einlage|0.5mm|", 2.00, "m²"),
            MaterialBedarf("|Daemmung||80mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.85, "kg", optional=True),
        ],
    ),
    "Aquapanel": Rezept(
        system="Aquapanel",
        beschreibung="Nassraum-Aufbau Aquapanel Cement Board",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.80,
        materialien=[
            MaterialBedarf("|Aquapanel||12.5mm|", 1.05, "m²"),
            MaterialBedarf("|Profile|CW|75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW|75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", optional=True),
        ],
    ),
    # --- Zulagen / Einzelteile ---------------------------------------------
    "Zulage": Rezept(
        system="Zulage",
        beschreibung="Zulage (Türaussparung, Ecken, Anschluss)",
        zieleinheit="Stk",
        zeit_h_pro_einheit=0.8,
        materialien=[
            # Zulagen haben selten Hauptmaterial, nur Zeit + Kleinmaterial
        ],
    ),
    "Tueraussparung": Rezept(
        # KALIBRIERT 2026-04-28: Vorher 1.5h/Stk + 6 lfm UA50 ergab ~243 EUR/Stk
        # in Salach — von Harun's Vater als deutlich zu hoch markiert.
        # Praxis-Werte (Trockenbau Feichtenbeiner Ulm):
        #   - 30 min Montage = 0.5 h pro Tueraussparung
        #   - 2x UA-Verstaerkung (links + rechts, kurz pro Seite ~1m) = 2 lfm UA
        #   - 1x UW als Sturz = 1 lfm
        #   - Kleinmaterial-Anteil ist im Wandsystem-m²-Preis bereits drin
        #     (Harun rechnet pauschal so).
        # Erwarteter EP nach Kalibrierung: ~75-95 EUR/Stk.
        system="Tueraussparung",
        beschreibung="Tueroeffnung mit UA-Verstaerkung + UW-Sturz [Praxis-kalibriert 2026-04-28]",
        zieleinheit="Stk",
        zeit_h_pro_einheit=0.5,  # 30 min Montage je Aussparung
        materialien=[
            # UA75-Verstaerkung an beiden Seiten (kurze Stuecke pro Seite)
            MaterialBedarf("|Profile|UA|75|", 2.0, "lfm"),
            # UW75-Sturz (1 lfm pro Tueraussparung)
            MaterialBedarf("|Profile|UW|75|", 1.0, "lfm", optional=True),
        ],
    ),
    "WC_Trennwand": Rezept(
        system="WC_Trennwand",
        beschreibung="Vorgefertigte WC-Trennwand inkl. Tür (System-Paket)",
        zieleinheit="Stk",
        zeit_h_pro_einheit=3.0,  # 2-4h pro Anlage (anliefern, ausrichten, befestigen)
        materialien=[
            # WC-Trennwand als Komplett-System — Kategorie Bauelemente
            MaterialBedarf("|Bauelemente|WC-Trennwand||", 1.0, "Stk"),
        ],
    ),
    "Eckschiene": Rezept(
        # KALIBRIERT 2026-04-28: Vorher gab's zwei "alternative" MaterialBedarf-
        # Eintraege ("||Eckschiene||" und "||Kantenschutz||"), die beide nicht
        # auf den realen Kemmler-Bestand gematcht haben (product_name dort:
        # "Kemmler TR Kantenprofil 3502 ALU..."). Resultat: 0 EUR Material.
        # Jetzt: ein praeziser Eintrag mit Knauf-naher DNA + Kemmler-Mat-Nr.
        # effective_unit_price liegt bei 0.39768 EUR/m (BL=2500mm) bzw.
        # 0.3314 EUR/m (BL=3000mm) — der Fuzzy-Fallback auf "Kantenprofil"
        # trifft beide Varianten.
        system="Eckschiene",
        beschreibung="ALU-Kantenschiene (Kemmler TR 3502 als Standard) [kalibriert 2026-04-28]",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.15,
        materialien=[
            MaterialBedarf(
                "Kemmler|Trockenbauprofile|Kantenprofil||",
                1.05, "lfm",
                mat_nr="3575150107",
            ),
        ],
    ),
    "Fugenversiegelung": Rezept(
        system="Fugenversiegelung",
        beschreibung="Acryl-Versiegelung in Anschlussfuge",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.08,
        materialien=[
            MaterialBedarf("|Bauchemie|Acryl||", 0.05, "l"),
        ],
    ),
    "Aussparung": Rezept(
        system="Aussparung",
        beschreibung="Rechteckige Aussparung für Installation (Einmessen, Herstellen)",
        zieleinheit="Stk",
        zeit_h_pro_einheit=0.45,
        materialien=[],
    ),
    "Installationsloch": Rezept(
        system="Installationsloch",
        beschreibung="Bohrung für Sanitär-Durchbruch",
        zieleinheit="Stk",
        zeit_h_pro_einheit=0.15,
        materialien=[],
    ),
    "Deckenschuerze": Rezept(
        system="Deckenschuerze",
        beschreibung="Senkrechte Abschottung unter Decke, 2-lagig beidseitig",
        zieleinheit="m",
        zeit_h_pro_einheit=0.65,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.70, "m²"),
            MaterialBedarf("|Profile|CW|50|", 2.50, "lfm"),
            MaterialBedarf("|Daemmung||60mm|", 0.40, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.30, "kg", optional=True),
        ],
    ),
    "Regiestunde": Rezept(
        system="Regiestunde",
        beschreibung="Stundenlohnarbeit (Regie)",
        zieleinheit="h",
        zeit_h_pro_einheit=1.0,
        materialien=[],
    ),
    "Verkleidung": Rezept(
        system="Verkleidung",
        beschreibung="Stahlträger-/Installationsverkleidung (Abkofferung)",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.9,
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 1.20, "m²"),
            MaterialBedarf("|Profile|CW|50|", 2.50, "lfm"),
            MaterialBedarf("|Daemmung||40mm|", 0.60, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.40, "kg", optional=True),
        ],
    ),
    "Revisionsklappe": Rezept(
        system="Revisionsklappe",
        beschreibung="Revisionsklappe einbauen",
        zieleinheit="Stk",
        zeit_h_pro_einheit=0.6,
        materialien=[
            MaterialBedarf("|Revisionsklappen||400x400|", 1.0, "Stk"),
        ],
    ),
    # --- Spezial-Decken (Premium) -----------------------------------------
    "Streckmetalldecke": Rezept(
        system="Streckmetalldecke",
        beschreibung="Streckmetalldecke Lindner LMD ST 215 o.glw. rahmenlos",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.65,  # hoher Montageaufwand (Einhängesystem)
        materialien=[
            # Streckmetallplatte + Einhängeprofile: hoher Paketpreis
            # Ca. 95-130 EUR/m² Material -> fallback als Sicherheit
            MaterialBedarf("Lindner|Streckmetalldecke|LMD|215|", 1.0, "m²"),
            MaterialBedarf("|Profile|Tragprofil||", 2.0, "lfm", optional=True),
            MaterialBedarf("|Abhänger|Nonius||", 1.2, "Stk", optional=True),
        ],
    ),
    "Deckensegel": Rezept(
        system="Deckensegel",
        beschreibung="Akustik-Deckensegel (Strähle System 7300 o.glw.)",
        zieleinheit="Stk",
        zeit_h_pro_einheit=2.5,  # Lieferung, Ausrichtung, Abhängung
        materialien=[
            # Akustik-Segel komplett als Stk-Fabrikat (typ. 350-650 EUR je nach Größe)
            MaterialBedarf("Strähle|Deckensegel|System|7300|", 1.0, "Stk"),
            MaterialBedarf("|Abhänger|Seil||", 4.0, "Stk", optional=True),
        ],
    ),
    "Wandabsorber": Rezept(
        system="Wandabsorber",
        beschreibung="Akustik-Wandabsorber (DUR SONIC Quad o.glw.)",
        zieleinheit="Stk",
        zeit_h_pro_einheit=1.5,  # Anbohren, Wandbefestigung
        materialien=[
            # Absorber komplett (Tiefenabsorber, Stahlblech pulverbeschichtet)
            MaterialBedarf("DUR Lum|Wandabsorber|Quad||", 1.0, "Stk"),
            MaterialBedarf("|Befestigung|Wandanker||", 4.0, "Stk", optional=True),
        ],
    ),
    "Deckenschott": Rezept(
        system="Deckenschott",
        beschreibung="Deckenschott F90 (Brandschutzabschottung senkrecht von oben)",
        zieleinheit="lfm",
        zeit_h_pro_einheit=1.0,
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 2.40, "m²"),
            MaterialBedarf("|Profile|UA|75|", 2.20, "lfm"),
            MaterialBedarf("|Daemmung||60mm|", 0.60, "m²", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.50, "kg", optional=True),
        ],
    ),
    "Streckmetall_Zulage": Rezept(
        system="Streckmetall_Zulage",
        beschreibung="Akustikvlies-Zulage hinter Streckmetall-/Rasterdecken",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.05,
        materialien=[
            MaterialBedarf("|Akustikvlies||30mm|", 1.0, "m²"),
        ],
    ),
    "Wandanschluss": Rezept(
        system="Wandanschluss",
        beschreibung="Wandanschluss Rasterdecke/GK-Decke, Randprofil + Fuge",
        zieleinheit="m",  # häufig 'm' nicht 'lfm' im LV
        zeit_h_pro_einheit=0.1,
        materialien=[
            MaterialBedarf("|Profile|Randprofil||", 1.05, "lfm", optional=True),
        ],
    ),
    "Kabeldurchfuehrung_F90": Rezept(
        system="Kabeldurchfuehrung_F90",
        beschreibung="Einzelkabeldurchführung F90 in GK-Brandschutzdecke",
        zieleinheit="Stk",
        zeit_h_pro_einheit=0.5,
        materialien=[
            MaterialBedarf("|Brandschutz|Schottmanschette||", 1.0, "Stk"),
        ],
    ),
    "Deckensprung": Rezept(
        system="Deckensprung",
        beschreibung="Vertikaler Deckenversprung Rasterdecke (Stirnabschluss)",
        zieleinheit="m",
        zeit_h_pro_einheit=0.45,
        materialien=[
            MaterialBedarf("|Profile|UA|75|", 1.5, "lfm"),
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.0, "m²", optional=True),
        ],
    ),
    "Aufdopplung_geklebt": Rezept(
        system="Aufdopplung_geklebt",
        beschreibung="Aufdopplung GK-Platten geklebt (Ansetzbinder)",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.35,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 0.30, "m²"),
            MaterialBedarf("|Spachtel||Ansetzbinder|", 1.5, "kg", optional=True),
        ],
    ),
    "Verstaerkungsprofil": Rezept(
        system="Verstaerkungsprofil",
        beschreibung="Verstärkungsprofil QR / horizontale UA-Verstärkung",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.20,
        materialien=[
            MaterialBedarf("|Profile|UA|75|", 1.0, "lfm"),
        ],
    ),
    # ------------------------------------------------------------------
    # Spezial-Rezepte aus Stuttgart-Omega-LV-Diagnose (2026-04-20)
    # Alle Mengen als Annahme markiert — TODO in den Materialien.
    # ------------------------------------------------------------------
    "GK_Schwert": Rezept(
        system="GK_Schwert",
        # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
        beschreibung="Fassadenschwertanschluss Knauf TP 120 A o.glw. (Silentboard beidseitig, Schwertbreite <250mm, Dicke 47mm)",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.80,
        materialien=[
            # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
            MaterialBedarf("|Gipskarton|Silentboard|12.5mm|", 0.50, "m²"),
            MaterialBedarf("|Daemmung||20mm|", 0.20, "m²", optional=True),
            MaterialBedarf("|Profile|CW|50|", 2.00, "lfm"),
            MaterialBedarf("|Profile|UW|50|", 0.40, "lfm", optional=True),
            MaterialBedarf("|Profile|Eckschutzschiene||", 2.00, "lfm", optional=True),
            MaterialBedarf("|Spachtel||Uniflott|", 0.30, "kg", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 15.0, "Stk", optional=True),
        ],
    ),
    "Leibungsbekleidung": Rezept(
        system="Leibungsbekleidung",
        # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
        # TODO: Variante F90 (2-lagig) braucht 0.70 m²/lfm statt 0.35; hydrophobiert nutzt GKBI statt GKB
        beschreibung="Trockenputz-Leibungsbekleidung an Tür-/Fensteröffnungen (Default F0, 1-lagig, Wanddicke bis 300mm)",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.40,
        materialien=[
            # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 0.35, "m²"),
            MaterialBedarf("|Spachtel||Ansetzgips|", 0.50, "kg", optional=True),
            MaterialBedarf("|Spachtel||Uniflott|", 0.20, "kg", optional=True),
        ],
    ),
    "Freies_Wandende": Rezept(
        system="Freies_Wandende",
        # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
        beschreibung="Stirnabschluss einer Trockenbauwand (Wanddicke 125mm, Q2)",
        zieleinheit="m",
        zeit_h_pro_einheit=0.30,
        materialien=[
            # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
            MaterialBedarf("|Profile|UA|75|", 1.00, "lfm"),
            MaterialBedarf("|Profile|Anschlusswinkel||", 2.00, "Stk", optional=True),
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 0.15, "m²"),
            MaterialBedarf("|Spachtel||Uniflott|", 0.20, "kg", optional=True),
            MaterialBedarf("|Profile|Eckschutzschiene||", 2.00, "lfm", optional=True),
        ],
    ),
    "Stuetzenbekleidung": Rezept(
        system="Stuetzenbekleidung",
        # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
        # TODO: Entscheidung ob Stahlrohr-Lieferung Teil dieser Position oder separat (Metallbau-Gewerk)
        beschreibung="Stützenbekleidung — Quadratrohr 50x50x4mm als Tragwerk + GK-Bekleidung 4-seitig 12,5mm",
        zieleinheit="m",
        zeit_h_pro_einheit=0.60,
        materialien=[
            # TODO: Mengen gegen DIN 18181 / Knauf-Verarbeitungsrichtlinie verifizieren
            MaterialBedarf("|Stahl|Quadratrohr|50x50x4|", 1.00, "lfm", optional=True),
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 0.20, "m²"),
            MaterialBedarf("|Spachtel||Uniflott|", 0.10, "kg", optional=True),
        ],
    ),
}


# F-Klasse-Routing: Wenn Feuerwiderstand gesetzt, bevorzuge Brandschutz-Rezept.
def _resolve_rezept_raw(
    erkanntes_system: str, feuerwiderstand: str, plattentyp: str
) -> Rezept | None:
    """Liefert das passendste Rezept für eine LV-Position.

    Interner Kern-Lookup ohne Plattentyp-Override. Wird vom Wrapper
    ``resolve_rezept`` aufgerufen.
    """
    if not erkanntes_system:
        return None

    # Direktes Match
    if erkanntes_system in REZEPTE:
        return REZEPTE[erkanntes_system]

    upper = erkanntes_system.upper()

    # Synonyme / Aliase
    aliases = {
        "VS": "W625",
        "VORSATZSCHALE": "W625",  # Default: freistehend (W625.de) — siehe K-2 Korrektur
        "VORSATZSCHALE FREISTEHEND": "W625",
        "VORSATZSCHALE DIREKT": "W623",
        "VORSATZSCHALE DIREKT BEFESTIGT": "W623",
        "SCHACHTWAND": "W628A",  # Default: freispannende Variante (Knauf-offizielle Bez.)
        # Backward-Compat: interne S-Suffix-Codes (vor 2026-04-20) auf offizielle Namen
        "W625S": "W628A",
        "W626S": "W628B",
        "W631S": "W629",
        "W632": "W635",
        # Offizielle Knauf-Codes mit .de-Suffix
        "W628A.DE": "W628A",
        "W628B.DE": "W628B",
        "W629.DE": "W629",
        "W635.DE": "W635",
        # W135-Brandwand Backward-Compatibility (Alt-Codes K-1):
        "W135_STAHLBLECH": "W135",
        "STAHLBLECHEINLAGE": "W135",
        "EINBRUCHHEMMUNG": "W135",
        "A+M": "W135",
        "F60 A+M": "W135",
        # Brandwand-Hauptkategorien
        "BRANDWAND": "W131",
        "EINSCHALIGE BRANDWAND": "W131",
        "ZWEISCHALIGE BRANDWAND": "W133",  # intern "zweischalig" = 3-lagig per Knauf
        "SONDERBAUWAND": "W131",
        "OWA": "OWA_MF",
        "RASTERDECKE": "OWA_MF",
        "MF-RASTERDECKE": "OWA_MF",
        "MINERALFASER-RASTERDECKE": "OWA_MF",
        "ABHANGDECKE": "D112",
        "UNTERDECKE": "D112",
        "TUERAUSSPARUNG": "Tueraussparung",
        "TÜRAUSSPARUNG": "Tueraussparung",
        "DECKENSCHÜRZE": "Deckenschuerze",
        "DECKENSCHUERZE": "Deckenschuerze",
        "REGIE": "Regiestunde",
        "STUNDENLOHN": "Regiestunde",
        "INSTALLATIONSLOCH": "Installationsloch",
        "ABKOFFERUNG": "Verkleidung",
        "WC-TRENNWAND": "WC_Trennwand",
        "WC_TRENNWAND": "WC_Trennwand",
        "WC": "WC_Trennwand",
        "TRENNWAND-TÜRANLAGE": "WC_Trennwand",
        "SCHAMWAND": "WC_Trennwand",
        "WANDHAKEN": "Zulage",
        "WAND/TÜRSTOPPER": "Zulage",
        "TÜRSTOPPER": "Zulage",
        "DEHNUNGSFUGE": "Fugenversiegelung",
        "DEHNUNGS-BEWEGUNGSFUGE": "Fugenversiegelung",
        "BEWEGUNGSFUGE": "Fugenversiegelung",
        "DECKENAUSSCHNITT": "Installationsloch",
        "DECKENAUSSCHNITTE": "Installationsloch",
        # --- Stuttgart Omega LV Aliase ---
        "STRECKMETALLDECKE": "Streckmetalldecke",
        "STRECKMETALL": "Streckmetalldecke",
        "LMD": "Streckmetalldecke",
        "DECKENSEGEL": "Deckensegel",
        "AKUSTIKSEGEL": "Deckensegel",
        "WANDABSORBER": "Wandabsorber",
        "TIEFENABSORBER": "Wandabsorber",
        "AKUSTIKABSORBER": "Wandabsorber",
        "DECKENSCHOTT": "Deckenschott",
        "BRANDSCHOTT": "Deckenschott",
        "OWATECTA": "OWA_MF",
        "AKUSTIKVLIES": "Streckmetall_Zulage",
        "WANDANSCHLUSS": "Wandanschluss",
        "RANDFRIES": "Wandanschluss",
        "KABELDURCHFÜHRUNG": "Kabeldurchfuehrung_F90",
        "KABELDURCHFUEHRUNG": "Kabeldurchfuehrung_F90",
        "EINZELKABELDURCHFÜHRUNG": "Kabeldurchfuehrung_F90",
        "DECKENSPRUNG": "Deckensprung",
        "Z-PROFIL": "Verstaerkungsprofil",
        "VERSTÄRKUNGSPROFIL": "Verstaerkungsprofil",
        "VERSTÄRKUNGSPROFILE": "Verstaerkungsprofil",
        "UA-VERSTÄRKUNG": "Verstaerkungsprofil",
        "QR-PROFIL": "Verstaerkungsprofil",
        "AUFDOPPLUNG": "Aufdopplung_geklebt",
        "ZULAGE": "Zulage",
        "AQUAPANEEL": "Aquapanel",
        "AQUAPANEL-ZULAGE": "Aquapanel",
        "GKBI-ZULAGE": "Zulage",
        "Q3-ZULAGE": "Zulage",
        "Q3-SPACHTELUNG": "Zulage",
        "RIPPENDECKENHOHLRAUM": "Zulage",
        "RIPPENDECKE": "D113",  # Brandschutzdecke auf Rippen
        "WEITSPANNDECKE": "D113",
        "FREITRAGEND": "D113",
        # --- Stuttgart-Omega 2026-04-20 ---
        "GK-SCHWERT": "GK_Schwert",
        "GK_SCHWERT": "GK_Schwert",
        "SCHWERT": "GK_Schwert",
        "FASSADENSCHWERTANSCHLUSS": "GK_Schwert",
        "TP 120 A": "GK_Schwert",
        "TP120A": "GK_Schwert",
        "LEIBUNGSBEKLEIDUNG": "Leibungsbekleidung",
        "LEIBUNGSKLEIDUNG": "Leibungsbekleidung",
        "LEIBUNG": "Leibungsbekleidung",
        "TROCKENPUTZ": "Leibungsbekleidung",
        "FREIES WANDENDE": "Freies_Wandende",
        "FREIES_WANDENDE": "Freies_Wandende",
        "FREIESWANDENDE": "Freies_Wandende",
        "STIRNABSCHLUSS": "Freies_Wandende",
        "FREIES ENDE": "Freies_Wandende",
        "STUETZENBEKLEIDUNG": "Stuetzenbekleidung",
        "STÜTZENBEKLEIDUNG": "Stuetzenbekleidung",
        "QUADRATROHR": "Stuetzenbekleidung",
        "STAHLBEKLEIDUNG": "Stuetzenbekleidung",
    }
    if upper in aliases:
        return REZEPTE.get(aliases[upper])

    # Prefix-Heuristiken
    if upper.startswith("W11"):
        if feuerwiderstand in ("F90", "F120", "F180"):
            return REZEPTE["W118"]
        # Explizites Mapping der W11-Familie
        if upper in ("W112", "W113", "W115", "W116"):
            return REZEPTE[upper]
        # W111 (1-lagig), W114, W117 etc. fallen auf W112 zurueck
        return REZEPTE["W112"]
    if upper.startswith("W13"):
        # Explizites Mapping der W13-Familie (alle Brandwand-Sonderbauwaende mit Stahlblech)
        if upper in ("W131", "W133", "W135"):
            return REZEPTE[upper]
        # W132, W134, etc. - Fallback auf W131
        return REZEPTE["W131"]
    if upper.startswith("W14"):
        return REZEPTE["W115"]  # Schallschutz-Varianten
    if upper.startswith("W62"):
        # W621-W627: Vorsatzschalen (W61-Familie-Aufbau, historische W62x-Codes)
        # W628+: Schachtwaende laut offizieller Knauf-Klassifikation
        if upper in ("W623", "W625", "W626"):
            return REZEPTE[upper]
        if upper in ("W628A", "W628B"):
            return REZEPTE[upper]
        # W628 (ohne Suffix) → Default auf W628A (freispannend, haeufigster Fall)
        if upper == "W628":
            return REZEPTE["W628A"]
        if upper == "W629":
            return REZEPTE["W629"]
        # Fallback fuer undefinierte W62-Codes: Vorsatzschale W625 (freistehend)
        return REZEPTE["W625"]
    if upper.startswith("W63"):
        # W63X sind alle Schachtwand-Varianten (W635 = UW-Doppelstaender).
        if upper == "W635":
            return REZEPTE["W635"]
        # Fallback: W628A (freispannende Schachtwand)
        return REZEPTE.get("W628A", REZEPTE["W625"])
    if upper.startswith("D11"):
        # Explizites Mapping der D11-Familie
        if upper in ("D112", "D113", "D116"):
            return REZEPTE[upper]
        # D111 (Holz-UK), D114, D115 fallen auf D112 zurueck
        return REZEPTE["D112"]
    if upper.startswith("D13"):
        # D131 hat jetzt eigenes Rezept (Freitragende Decke unter Holzbalkendecke)
        if upper in ("D131",):
            return REZEPTE["D131"]
        return REZEPTE["D131"]  # Auch D132 etc. als freitragend behandeln
    if "OWA" in upper or "RASTER" in upper:
        return REZEPTE["OWA_MF"]
    if "AQUAPANEL" in upper:
        return REZEPTE["Aquapanel"]
    return None


# ---------------------------------------------------------------------------
# 2026-04-24: Plattentyp-Override fuer Nicht-Brandschutz-Schachtwaende
# ---------------------------------------------------------------------------
# Hintergrund: Die W62X-Schachtwand-Rezepte sind per Knauf-Standard mit
# Fireboard (17,90 EUR/m²) ausgelegt, weil Schachtwaende oft Brand-
# abschnittsgrenzen sind. In der Ulm-Praxis (Trockenbau Feichtenbeiner)
# sind ca. 80 % der Schachtwaende aber reine Installationsschaechte ohne
# Brandschutz-Auflage, beplankt mit normaler GKB/GKBi.
#
# Der Override greift GENAU dann:
# - System ist in _OVERRIDE_WHITELIST (nur einfache Schachtwand
#   W628A/W628B, kein Doppelstaender W629 und keine Sonderform W635 —
#   die bleiben aus Sicherheitsgruenden bei Fireboard).
# - LV-Position hat plattentyp explizit gesetzt auf GKB/GKBi/GKF/GKFi/
#   Diamant (also nicht leer und nicht "Fireboard").
# - LV-Position hat keinen Brandschutz-Feuerwiderstand (F30/F60/F90/
#   F120/F180, EI30/EI60/EI90/EI120).
# Sonst bleibt Fireboard unveraendert.
_PLATTENTYP_TO_DNA = {
    "GKB":     "|Gipskarton|GKB|12.5mm|",
    "GKF":     "|Gipskarton|GKF|12.5mm|",
    "GKBI":    "|Gipskarton|GKBI|12.5mm|",
    "GKFI":    "|Gipskarton|GKFI|12.5mm|",
    "DIAMANT": "|Gipskarton|Diamant|12.5mm|",
}
_FIRE_RATINGS = {
    "F30", "F60", "F90", "F120", "F180",
    "EI30", "EI60", "EI90", "EI120",
}
# Whitelist fuer plattentyp-explicit-override (urspruenglich Fireboard -> GKB).
_OVERRIDE_WHITELIST = {"W628A", "W628B"}
# B+4.13 Iteration 5b (2026-04-28): Auto-Fire-Upgrade-Whitelist.
# Bei diesen Systemen wird die GKB-Beplankung automatisch zu GKF aufgewertet,
# sobald die Position einen Feuerwiderstand (F30+) traegt — die kalibrierten
# W628B-Rezepte haben jetzt GKB als Default fuer die Praxis (Trockenbau
# Feichtenbeiner: 80% der Schachtwaende ohne Brandschutz-Spec).
_AUTO_FIRE_UPGRADE_WHITELIST = {"W628B"}

# Patterns die bei einem Plattentyp-Override ersetzt werden sollen.
_PLATTE_PATTERNS = ("Gipskarton", "Fireboard")


def _apply_plattentyp_override(
    rezept: Rezept, plattentyp: str, feuerwiderstand: str
) -> Rezept:
    """Tauscht die Beplankungs-DNA aus, je nach Position-Metadaten.

    Modi:
    1. plattentyp_explicit (GKB/GKF/...) UND keine Fire-Rating
       → Beplankung in _OVERRIDE_WHITELIST-Systemen wird auf den expliziten
         Plattentyp gemappt.
    2. fire-rating gesetzt (F30+) UND System in _AUTO_FIRE_UPGRADE_WHITELIST
       UND Default-Beplankung ist GKB
       → automatisches Upgrade GKB → GKF (Knauf-Vorgabe fuer F-rated
         Schachtwaende).

    Die existierende Mat-Nr wird NICHT durch den Override veraendert
    (Knauf-Mat-Nrn 00002892 sind bei GKB und GKF vergleichbar im Kemmler-
    Bestand; bei abweichendem Mat-Nr-Bedarf liefert der Fuzzy-Fallback im
    Lookup den richtigen Treffer).
    """
    pt = (plattentyp or "").strip().upper()
    fr = (feuerwiderstand or "").strip().upper()

    target_dna: str | None = None

    # Modus 1: plattentyp_explicit ohne F-Rating
    if (
        rezept.system in _OVERRIDE_WHITELIST
        and pt not in ("", "FIREBOARD")
        and pt in _PLATTENTYP_TO_DNA
        and fr not in _FIRE_RATINGS
    ):
        target_dna = _PLATTENTYP_TO_DNA[pt]
        why = f"plattentyp-override: {pt}"
    # Modus 2: Auto-Fire-Upgrade bei W628B
    elif (
        rezept.system in _AUTO_FIRE_UPGRADE_WHITELIST
        and fr in _FIRE_RATINGS
        and pt not in _PLATTENTYP_TO_DNA  # nicht uebersteuern wenn pt explizit
    ):
        target_dna = _PLATTENTYP_TO_DNA["GKF"]
        why = f"auto-fire-upgrade: GKB->GKF wegen {fr}"
    else:
        return rezept

    materialien_new: list[MaterialBedarf] = []
    changed = False
    for mb in rezept.materialien:
        is_platte = any(pat in mb.dna_pattern for pat in _PLATTE_PATTERNS)
        if is_platte:
            materialien_new.append(
                MaterialBedarf(
                    dna_pattern=target_dna,
                    menge_pro_einheit=mb.menge_pro_einheit,
                    basis_einheit=mb.basis_einheit,
                    fallback_preis_eur=mb.fallback_preis_eur,
                    optional=mb.optional,
                    mat_nr=mb.mat_nr,
                )
            )
            changed = True
        else:
            materialien_new.append(mb)
    if not changed:
        return rezept
    return Rezept(
        system=rezept.system,
        beschreibung=rezept.beschreibung + f" [{why}]",
        zieleinheit=rezept.zieleinheit,
        zeit_h_pro_einheit=rezept.zeit_h_pro_einheit,
        materialien=materialien_new,
    )


def resolve_rezept(
    erkanntes_system: str, feuerwiderstand: str, plattentyp: str
) -> Rezept | None:
    """Rezept-Lookup + plattentyp-Override.

    Delegiert erst an ``_resolve_rezept_raw`` (Kern-Lookup, unveraendert).
    Wendet danach ``_apply_plattentyp_override`` an, das bei nicht-
    brandschutz Schachtwaenden die Fireboard-Platte durch die vom LV
    geforderte Standard-Gipskartonplatte ersetzt.
    """
    rezept = _resolve_rezept_raw(erkanntes_system, feuerwiderstand, plattentyp)
    if rezept is None:
        return None
    return _apply_plattentyp_override(rezept, plattentyp, feuerwiderstand)
