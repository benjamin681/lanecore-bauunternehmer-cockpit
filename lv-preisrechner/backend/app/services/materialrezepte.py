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
    "W112": Rezept(
        system="W112",
        beschreibung="W112.de — Einfachstaenderwerk, zweilagig beplankt (1 Lage GKB je Seite, CW75)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.55,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 2.10, "m²"),
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW75|", 3.60, "lfm"),
            MaterialBedarf("|Profile|UW75|", 1.60, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CD60/27|", 2.00, "lfm"),
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
            MaterialBedarf("|Profile|CW50|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW50|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.03, "Stk", optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.25, "kg", optional=True),
        ],
    ),
    # --- Schachtwände -------------------------------------------------------
    "W625S": Rezept(
        system="W625S",
        beschreibung="Schachtwand einseitig beplankt F90, Fireboard",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.90,
        materialien=[
            MaterialBedarf("Knauf|Gipskarton|Fireboard|20mm|", 2.10, "m²"),
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.04, "Stk", optional=True),
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
            MaterialBedarf("|Profile|CD60|27|", 3.20, "lfm"),
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
            MaterialBedarf("|Profile|CD60|27|", 3.20, "lfm"),
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
            MaterialBedarf("|Profile|CD60|27|", 3.20, "lfm"),  # Tragprofil
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
            MaterialBedarf("|Profile|CW75|", 2.50, "lfm"),  # Tragprofile spannen frei
            MaterialBedarf("|Profile|UW75|", 1.00, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW100|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW100|", 0.80, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW100|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW100|", 0.80, "lfm", optional=True),
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
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm"),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", optional=True),
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
        system="Tueraussparung",
        beschreibung="Türaussparung mit Sturzprofil + UA-Verstärkung",
        zieleinheit="Stk",
        zeit_h_pro_einheit=1.5,  # 1-2h je nach Größe
        materialien=[
            # UA-Profile 50mm ca. 6 lfm (Sturz + 2 seitlich)
            # DNA muss Kategorie=Profile UND Produktname~UA haben (sonst matcht CW75 etc.)
            MaterialBedarf("|Profile|UA|50|", 6.0, "lfm"),
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
        system="Eckschiene",
        beschreibung="ALU/verzinkte Eckschiene",
        zieleinheit="lfm",
        zeit_h_pro_einheit=0.15,
        materialien=[
            # Auch ohne Match: Zuschlag + Lohn allein (~5-8 €/lfm realistisch)
            MaterialBedarf("||Eckschiene||", 1.05, "lfm"),
            MaterialBedarf("||Kantenschutz||", 1.05, "lfm"),
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
            MaterialBedarf("|Profile|CW50|", 2.50, "lfm"),
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
            MaterialBedarf("|Profile|CW50|", 2.50, "lfm"),
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
            MaterialBedarf("|Profile|CW50|", 2.00, "lfm"),
            MaterialBedarf("|Profile|UW50|", 0.40, "lfm", optional=True),
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
def resolve_rezept(
    erkanntes_system: str, feuerwiderstand: str, plattentyp: str
) -> Rezept | None:
    """Liefert das passendste Rezept für eine LV-Position."""
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
        "SCHACHTWAND": "W625S",
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
        return REZEPTE["W623"]
    if upper.startswith("W63"):
        return REZEPTE.get("W625S", REZEPTE["W623"])
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
