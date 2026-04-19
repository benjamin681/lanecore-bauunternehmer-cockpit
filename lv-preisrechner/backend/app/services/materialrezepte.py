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
    "W112": Rezept(
        system="W112",
        beschreibung="Einfache Metallständerwand, 1-lagig GKB 12,5mm beidseitig, CW75",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.55,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 2.10, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.05, "Stk", fallback_preis_eur=0.02, optional=True),  # ~25 Stk/m²; Faktor 0.05 = 25/500
            MaterialBedarf("|Spachtel||Universal|", 0.40, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "W115": Rezept(
        system="W115",
        beschreibung="Schallschutz-Trennwand, 2-lagig GKB 12,5mm beidseitig",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.75,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 4.20, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.06, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.03, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "W116": Rezept(
        system="W116",
        beschreibung="Doppelständerwand (akustisch entkoppelt), 2-lagig",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.95,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 4.20, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CW75|", 3.60, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW75|", 1.60, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.06, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.70, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "W118": Rezept(
        system="W118",
        beschreibung="Brandschutzwand F90, 2-lagig GKF",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.85,
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 4.20, "m²", fallback_preis_eur=4.20),
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.06, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.03, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "W135": Rezept(
        system="W135",
        beschreibung="Installationswand, 2-lagig, verbreiterter Hohlraum",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.95,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 4.20, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CW100|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW100|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||80mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.06, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    # --- Vorsatzschalen -----------------------------------------------------
    "W623": Rezept(
        system="W623",
        beschreibung="Vorsatzschale freistehend, 1-lagig GKB/GKF, CW50/75",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.50,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CW50|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW50|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.03, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.25, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "W625": Rezept(
        system="W625",
        beschreibung="Vorsatzschale direkt befestigt (Direktabhänger), 1-lagig",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.45,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CD60/27|", 2.00, "lfm"),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x25|", 0.03, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.25, "kg", fallback_preis_eur=2.20, optional=True),
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
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Schrauben||3.5x45|", 0.04, "Stk", fallback_preis_eur=0.02, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    # --- Decken ------------------------------------------------------------
    "D112": Rezept(
        system="D112",
        beschreibung="Abgehängte GK-Decke 1-lagig GKB 12,5mm, CD60/27 auf Direktabhänger",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.55,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.05, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CD60|27|", 3.20, "lfm", fallback_preis_eur=2.30),
            MaterialBedarf("|Profile|UD|", 0.60, "lfm"),
            # Abhänger/Clip pauschal pro m² (häufig nicht in Preisliste — ggf. kein Match)
            MaterialBedarf("|Daemmung||40mm|", 0.60, "m²", fallback_preis_eur=4.50, optional=True),  # oft nur teilweise
            MaterialBedarf("|Spachtel||Universal|", 0.35, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "D113": Rezept(
        system="D113",
        beschreibung="Abgehängte GK-Decke 2-lagig GKB/GKF 12,5mm (Brandschutz oder Schallschutz)",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.80,
        materialien=[
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 2.10, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CD60|27|", 3.20, "lfm", fallback_preis_eur=2.30),
            MaterialBedarf("|Profile|UD|", 0.60, "lfm"),
            MaterialBedarf("|Daemmung||40mm|", 0.60, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.50, "kg", fallback_preis_eur=2.20, optional=True),
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
        system="W131",
        beschreibung="Brandwand F90 / F120, 2-lagig GKF, breitere UK",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.95,
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 4.20, "m²", fallback_preis_eur=4.20),
            MaterialBedarf("|Profile|CW100|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW100|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||80mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.70, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "W135_Stahlblech": Rezept(
        system="W135_Stahlblech",
        beschreibung="Installationswand F60 A+M mit Stahlblecheinlage (Einbruchhemmung)",
        zieleinheit="m²",
        zeit_h_pro_einheit=1.10,
        materialien=[
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 4.20, "m²", fallback_preis_eur=4.20),
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||60mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
            # Stahlblecheinlage meist nicht in Preisliste → kommt als separate Position
            MaterialBedarf("|Spachtel||Universal|", 0.60, "kg", fallback_preis_eur=2.20, optional=True),
        ],
    ),
    "Aquapanel": Rezept(
        system="Aquapanel",
        beschreibung="Nassraum-Aufbau Aquapanel Cement Board",
        zieleinheit="m²",
        zeit_h_pro_einheit=0.80,
        materialien=[
            MaterialBedarf("|Aquapanel||12.5mm|", 1.05, "m²"),
            MaterialBedarf("|Profile|CW75|", 1.80, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Profile|UW75|", 0.80, "lfm", fallback_preis_eur=2.50, optional=True),
            MaterialBedarf("|Daemmung||40mm|", 1.00, "m²", fallback_preis_eur=4.50, optional=True),
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
            MaterialBedarf("|Profile|UA|50|", 6.0, "lfm", fallback_preis_eur=5.50),
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
            MaterialBedarf("|Gipskarton|GKB|12.5mm|", 1.70, "m²", fallback_preis_eur=3.50),
            MaterialBedarf("|Profile|CW50|", 2.50, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Daemmung||60mm|", 0.40, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.30, "kg", fallback_preis_eur=2.20, optional=True),
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
            MaterialBedarf("|Gipskarton|GKF|12.5mm|", 1.20, "m²", fallback_preis_eur=4.20),
            MaterialBedarf("|Profile|CW50|", 2.50, "lfm", fallback_preis_eur=3.20),
            MaterialBedarf("|Daemmung||40mm|", 0.60, "m²", fallback_preis_eur=4.50, optional=True),
            MaterialBedarf("|Spachtel||Universal|", 0.40, "kg", fallback_preis_eur=2.20, optional=True),
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
        "VS": "W623",
        "VORSATZSCHALE": "W623",
        "SCHACHTWAND": "W625S",
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
    }
    if upper in aliases:
        return REZEPTE.get(aliases[upper])

    # Prefix-Heuristiken
    if upper.startswith("W11"):
        if feuerwiderstand in ("F90", "F120", "F180"):
            return REZEPTE["W118"]
        if upper in ("W115", "W116"):
            return REZEPTE[upper]
        return REZEPTE["W112"]
    if upper.startswith("W13"):
        return REZEPTE["W131"]
    if upper.startswith("W14"):
        return REZEPTE["W115"]  # Schallschutz-Varianten
    if upper.startswith("W62"):
        return REZEPTE["W623"]
    if upper.startswith("W63"):
        return REZEPTE.get("W625S", REZEPTE["W623"])
    if upper.startswith("D11"):
        return REZEPTE["D112"]
    if upper.startswith("D13"):
        return REZEPTE["D113"]
    if "OWA" in upper or "RASTER" in upper:
        return REZEPTE["OWA_MF"]
    if "AQUAPANEL" in upper:
        return REZEPTE["Aquapanel"]
    return None
