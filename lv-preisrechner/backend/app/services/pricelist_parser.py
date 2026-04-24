"""Parser für Lieferanten-Preislisten (Sub-Block B+2).

Scope heute: Nur Kemmler-Format. Andere Lieferanten folgen bei Bedarf.

Architektur — Zwei-Phasen-Parsing:
1. pdfplumber (schnell, lokal): Layout-Info als Context für Phase 2
2. Claude Vision (präzise, API): Inhalts-Extraktion pro Batch

Der Parser wird via Background-Task aus pricelist_parse_worker.py aufgerufen.
Status-Übergänge: PENDING_PARSE -> PARSING -> PARSED / ERROR.

Die Einheiten-Intelligenz ist in diesem Modul isoliert (reines Python,
ohne Claude-API), damit sie unabhängig testbar ist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Typen
# ---------------------------------------------------------------------------
SupplierFormat = Literal["kemmler"]  # noqa: Y026 — erweitert sich spaeter


@dataclass
class ParseResult:
    """Ergebnis eines kompletten Parse-Laufs."""

    pricelist_id: str
    total_entries: int = 0
    parsed_entries: int = 0
    skipped_entries: int = 0
    avg_confidence: float = 0.0
    needs_review_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_entries == 0:
            return 0.0
        return self.parsed_entries / self.total_entries


@dataclass
class UnitInfo:
    """Normalisierte Einheiten-Information fuer einen Preis-Eintrag."""

    unit: str                               # Original-Einheit wie im Parser gelesen
    effective_unit: str                     # Normalisierte "Echt-Einheit" fuer Matching
    price_per_effective_unit: float         # Normalisierter Preis
    package_size: float | None = None       # z.B. 25.0 bei "25 kg/Sack"
    package_unit: str | None = None         # z.B. "kg" bei "25 kg/Sack"
    pieces_per_package: int | None = None   # z.B. 8 bei "8 St./Bd."
    confidence: float = 1.0                 # 0..1
    needs_review: bool = False
    note: str = ""                          # Freitext-Hinweis fuer Reviewer
    review_reason: str | None = None        # Normierter Grund (s. _REVIEW_REASONS)


# Normierte review_reason-Werte. Damit kann das UI gezielt filtern und dem
# User sagen was zu tun ist.
#
# - bundgroesse_fehlt: Produktname impliziert Gebinde (z.B. BL=XYZmm bei einem
#   Profil) aber keine Stueckzahl ("N St./Bd.") gefunden. Wahrscheinlich
#   Bundpreis gespeichert als lfm-Preis.
# - bundpreis_vs_einzelpreis_unklar: R2-Fall — Bundangabe UND Laengenangabe
#   gefunden, aber €/m kann sich auf Einzelstange oder Bund beziehen.
# - preis_ausserhalb_korridor: Plausibilitaets-Check schlaegt fehl
#   (s. _PLAUSIBILITY_CORRIDORS in _build_entry).
# - einheit_nicht_erkannt: Fallback-Fall — keine der R1-R5-Regeln matcht.
REVIEW_REASON_BUNDGROESSE_FEHLT = "bundgroesse_fehlt"
REVIEW_REASON_BUNDPREIS_UNKLAR = "bundpreis_vs_einzelpreis_unklar"
REVIEW_REASON_PREIS_AUSSERHALB_KORRIDOR = "preis_ausserhalb_korridor"
REVIEW_REASON_EINHEIT_NICHT_ERKANNT = "einheit_nicht_erkannt"


# Erlaubte Waehrungs-Codes. Der LLM-Parse kann in Randfaellen Varianten
# wie "EURO", "Euro", "€/Sack", " EUR " liefern. Die DB-Spalte ist
# varchar(10) nach Migration f8a2b3e91d04, aber wir normalisieren
# trotzdem hier auf ISO-4217-Whitelist — abweichende Rohwerte landen
# in attributes["raw_currency"] zur Nachvollziehbarkeit.
CURRENCY_WHITELIST = ("EUR", "USD", "CHF", "GBP")
CURRENCY_DEFAULT = "EUR"


def _normalize_currency(raw_value: object) -> tuple[str, str | None]:
    """Normalisiert Claude-Currency-Output auf ISO-4217-Whitelist.

    Returns (normalized_currency, raw_for_debug).
    raw_for_debug ist None wenn der Wert sauber auf die Whitelist
    mappt (strip + upper reicht), sonst der Original-String.
    """
    if raw_value is None:
        return CURRENCY_DEFAULT, None
    raw_str = str(raw_value).strip()
    if not raw_str:
        return CURRENCY_DEFAULT, None
    upper = raw_str.upper()
    if upper in CURRENCY_WHITELIST:
        # nur raw festhalten wenn Groß-/Klein- oder Whitespace-Reibung
        return upper, (raw_str if raw_str != upper else None)
    return CURRENCY_DEFAULT, raw_str


# ---------------------------------------------------------------------------
# Format-Erkennung
# ---------------------------------------------------------------------------
_KEMMLER_FILENAME_HINTS = ("kemmler", "ausbau-", "a-liste", "a+-liste", "a_liste")

# B+4.3-Entscheidung: Preislisten unbekannter Haendler sollen nicht hart
# scheitern. Wir nutzen den Kemmler-Prompt als "generischer deutscher
# Preislisten-Prompt". Das ist ein pragmatischer Zwischenschritt, bis ein
# echter lieferanten-agnostischer Prompt existiert.
UNSUPPORTED_FORMAT_FALLBACK: "SupplierFormat" = "kemmler"

# Pricelist-Parsing braucht mehr Output-Budget als der Default (16k),
# weil Multi-Image-Batches komplexe JSON-Strukturen liefern (pages + entries +
# attributes pro Zeile). Live-Messung auf Kemmler (Batch 5): Claude
# schneidet bei 16k mitten im JSON ab. 32k laesst bequeme Marge auch fuer
# dichte Seiten mit ~40 Entries.
_PRICELIST_MAX_TOKENS = 32_000


def _detect_format(
    file_path: Path | str,
    *,
    supplier_hint: str | None = None,
    first_page_text: str | None = None,
) -> SupplierFormat | None:
    """Erkennt das Preislisten-Format anhand von Dateiname + optionalem Text.

    Heute dediziert unterstuetzt: Kemmler.

    Fuer andere Haendler (Woelpert, Hornbach, …) geben wir
    UNSUPPORTED_FORMAT_FALLBACK zurueck — aktuell der Kemmler-Prompt als
    generischer Start. Der Prompt ist so formuliert, dass er bei deutschen
    Preislisten allgemein funktioniert (Produktname / Einheit / Preis).
    Ein echter haendler-agnostischer Prompt kommt in einer spaeteren Runde.
    """
    fn = str(file_path).lower()
    hint = (supplier_hint or "").lower()

    # Expliziter supplier_hint hat Vorrang
    if "kemmler" in hint:
        return "kemmler"

    # Dateiname-basierte Hints
    if any(h in fn for h in _KEMMLER_FILENAME_HINTS):
        return "kemmler"

    # Text-basierte Erkennung (Header auf erster Seite)
    if first_page_text:
        text_lower = first_page_text.lower()
        if "kemmler" in text_lower:
            return "kemmler"

    # B+4.3: Fallback statt None — wir versuchen, auch unbekannte Formate
    # zu parsen (siehe Modul-Docstring).
    return UNSUPPORTED_FORMAT_FALLBACK


# ---------------------------------------------------------------------------
# Einheiten-Intelligenz
# ---------------------------------------------------------------------------
# Regex: "X kg/Sack", "25kg/sack", "12,5 l/Eimer" etc.
_PACKAGE_UNIT_RE = re.compile(
    r"(?P<size>\d+(?:[,\.]\d+)?)\s*"
    r"(?P<pkg_unit>kg|g|l|ml|m²|qm|m2|m|lfm|stk|st)\s*/\s*"
    r"(?P<pkg_kind>sack|eimer|beutel|flasche|kanister|rolle|dose|gebinde)",
    re.IGNORECASE,
)

# Regex: "8 St./Bd.", "10 Stk./Bund", "16 St/Bd" etc.
_PIECES_PER_BUNDLE_RE = re.compile(
    r"(?P<pieces>\d+)\s*(?:st|stk)\.?\s*/\s*(?:bd|bund|pak|paket)\.?",
    re.IGNORECASE,
)

# Regex: "BL=2600 mm", "BL 3000mm", "L = 3.00 m" (Bundellaenge)
_BUNDLE_LENGTH_RE = re.compile(
    r"\b(?:bl|l)\s*=?\s*(?P<len>\d+(?:[,\.]\d+)?)\s*(?P<unit>mm|cm|m)\b",
    re.IGNORECASE,
)

# Regex: Rollen-Groesse "1100 mm x 50 m/Ro", "1.1 x 50m"
_ROLL_SIZE_RE = re.compile(
    r"(?P<width>\d+(?:[,\.]\d+)?)\s*(?P<wu>mm|cm|m)\s*[x×]\s*"
    r"(?P<length>\d+(?:[,\.]\d+)?)\s*(?P<lu>mm|cm|m)",
    re.IGNORECASE,
)

# Regex: Plattenformat "2000x1250x12,5 mm"
_PLATE_SIZE_RE = re.compile(
    r"(?P<w>\d+)\s*[x×]\s*(?P<h>\d+)\s*(?:[x×]\s*\d+(?:[,\.]\d+)?)?\s*mm",
    re.IGNORECASE,
)

# Regex: Profil-Typ-Erkennung (Trockenbau).
# Matcht CW/UW/UA/CD/UD als eigenstaendiges Token (Wortgrenze davor und
# entweder Zahl/Dimension/Leerzeichen danach), damit z.B. "UA" in
# "Aufbau" oder "Quadrat" nicht falsch matcht.
_PROFILE_TYPE_RE = re.compile(
    r"\b(?:CW|UW|UA|CD|UD)\b[\s\-]*\d",
    re.IGNORECASE,
)


def _to_float(s: str) -> float:
    """'12,5' -> 12.5 ; '3.00' -> 3.0."""
    return float(s.replace(",", "."))


def _to_meters(value: float, unit: str) -> float:
    unit_l = unit.lower()
    if unit_l == "mm":
        return value / 1000.0
    if unit_l == "cm":
        return value / 100.0
    return value


# Abkuerzungs-Mapping fuer haendler-uebliche Kurzformen (Kemmler & Co.).
# Schluessel: Kurzform im Produkt-/Unit-Text (lowercase, ohne Trennzeichen),
# Wert: Langform (Canonical).
# Nur EINDEUTIGE Kurzformen. Mehrdeutige (z.B. /P. = Paket vs. Packung,
# /B. = Bund vs. Batterie) werden NICHT automatisch aufgeloest, damit das
# Review-Signal erhalten bleibt.
_UNIT_ABBREVIATIONS: dict[str, str] = {
    "sa.": "Sack",
    "s.": "Sack",         # In Kemmler-Daten so beobachtet: "25 kg/S."
    "rol.": "Rolle",
    "rol": "Rolle",
    "pak.": "Paket",
    "eim.": "Eimer",
    "ktn.": "Karton",
    "geb.": "Gebinde",
    "bd.": "Bund",
    "ku.": "Kuebel",
    "fl.": "Flasche",
    "kartu.": "Kartusche",
}

# Gezielt NICHT mapped (mehrdeutig; bleibt im Fallback-Pfad = needs_review):
#   p.  (Paket vs. Packung vs. Palette)
#   b.  (Bund vs. Beutel)
#   st. (Stueck vs. Stange) — wird bereits separat oben behandelt


def _expand_unit_abbreviations(text: str) -> str:
    """Ersetzt bekannte Einheiten-Abkuerzungen durch Langformen.

    Matcht nur am "/"-Trenner (z.B. "25 kg/Sa." -> "25 kg/Sack"), nicht
    generell im Text, um False-Positives wie "S.1" (Seite 1) zu vermeiden.

    Gibt den unveraenderten Text zurueck, wenn keine Abkuerzung passt.
    """
    if not text:
        return text
    # Wir ersetzen "/<abbrev>" case-insensitive. Dictionary nach Laenge sortiert
    # (laengste zuerst), damit "rol." vor "rol" matcht.
    for abbrev in sorted(_UNIT_ABBREVIATIONS.keys(), key=len, reverse=True):
        replacement = _UNIT_ABBREVIATIONS[abbrev]
        # Wort-Grenze rechts: Punkt ist in Regex ein Sonderzeichen; manuelles
        # Pattern: "/" + Abkuerzung, gefolgt von Ende/Whitespace/Komma.
        pattern = re.compile(
            r"/" + re.escape(abbrev) + r"(?=$|[\s,;)])",
            flags=re.IGNORECASE,
        )
        text = pattern.sub("/" + replacement, text)
    return text


def _normalize_unit(
    raw_unit: str,
    *,
    product_name: str = "",
    price: float = 0.0,
) -> UnitInfo:
    """Ermittelt effektive Einheit + normalisierten Preis aus roher Einheit.

    Fuenf Regeln (aus B+2-Spec):
      R1: "X kg/Sack" & Co.       -> package_size, effective_unit=pkg_unit
      R2: "N St./Bd." mit BL      -> UNKLAR, needs_review=True
      R3: "X l/Eimer"             -> analog R1
      R4: Plattenware €/m²        -> direkt
      R5: Rollen WxL              -> m² berechnen

    Fallback: effective_unit=raw_unit, needs_review=True, confidence<0.7.

    Vor der Regel-Engine werden gaengige Abkuerzungen expandiert
    (z.B. "€/Sa." -> "€/Sack") — sowohl in raw_unit als auch im
    product_name (weil R1 die Gebinde-Angabe "25 kg/Sa." dort liest).
    """
    raw_unit = _expand_unit_abbreviations(raw_unit)
    product_name = _expand_unit_abbreviations(product_name)

    raw = raw_unit.strip()
    raw_lower = raw.lower()
    combined = f"{product_name} {raw_unit}"

    # --- R4: Plattenware mit direktem €/m² (EINFACHER Pfad zuerst) -------
    if raw_lower in ("€/m²", "eur/m²", "€/qm", "eur/qm", "m²", "qm"):
        # Haeufiger Fall: Gipskartonplatte 2000x1250x12,5mm, 3.00 €/m² -> direkt
        return UnitInfo(
            unit=raw,
            effective_unit="m²",
            price_per_effective_unit=price,
            confidence=1.0,
        )
    if raw_lower in ("€/m", "eur/m", "€/lfm", "eur/lfm", "m", "lfm"):
        # Spezial-Check: laufende Meter bei Profilen mit "N St./Bd."
        bundle_match = _PIECES_PER_BUNDLE_RE.search(combined)
        length_match = _BUNDLE_LENGTH_RE.search(combined)
        if bundle_match and length_match:
            # R2: Bundpreis — unklar, markiere zum Review.
            return UnitInfo(
                unit=raw,
                effective_unit="lfm",
                price_per_effective_unit=price,
                pieces_per_package=int(bundle_match.group("pieces")),
                package_size=_to_meters(
                    _to_float(length_match.group("len")), length_match.group("unit")
                ),
                package_unit="m",
                confidence=0.55,
                needs_review=True,
                note=(
                    "Bundpreis vs. Einzelpreis unklar — "
                    "der €/m koennte sich auf eine Einzelstange oder den Bund beziehen."
                ),
                review_reason=REVIEW_REASON_BUNDPREIS_UNKLAR,
            )
        # P3 (B+4.3.x): Bundgroesse fehlt — BL=XYZmm im Produktname, aber
        # keine "N St./Bd."-Angabe. Das ist der Kern-Bug bei den Kemmler
        # UA-Profilen: "UA 48x40x2 BL=3000mm" mit €/m 318,80 sieht fuer
        # den Parser wie klarer lfm-Preis aus, ist aber tatsaechlich ein
        # Bundpreis (6 St./Bd. stand nicht im PDF).
        #
        # Wir triggern NUR wenn length_match greift — das ist der starke
        # Hinweis auf Gebinde. Profil-Typ allein (CW/UW/UA) ohne BL wuerde
        # zu viele false positives schalten (normaler lfm-Preis fuer
        # Einzelstangen ist legitim).
        if length_match:
            return UnitInfo(
                unit=raw,
                effective_unit="lfm",
                price_per_effective_unit=price,
                package_size=_to_meters(
                    _to_float(length_match.group("len")),
                    length_match.group("unit"),
                ),
                package_unit="m",
                confidence=0.4,
                needs_review=True,
                note=(
                    "Bundgroesse fehlt — Produkttext enthaelt BL=XYZmm, aber "
                    "keine 'N St./Bd.'-Angabe gefunden. Der €/m-Preis koennte "
                    "in Wahrheit ein Bundpreis sein."
                ),
                review_reason=REVIEW_REASON_BUNDGROESSE_FEHLT,
            )
        # Sonst: klarer lfm-Preis
        return UnitInfo(
            unit=raw,
            effective_unit="lfm",
            price_per_effective_unit=price,
            confidence=0.95,
        )
    if raw_lower in ("€/stk", "eur/stk", "stk", "stk.", "€/st", "st."):
        return UnitInfo(
            unit=raw,
            effective_unit="Stk",
            price_per_effective_unit=price,
            confidence=1.0,
        )
    if raw_lower in ("€/kg", "eur/kg", "kg"):
        return UnitInfo(
            unit=raw,
            effective_unit="kg",
            price_per_effective_unit=price,
            confidence=1.0,
        )

    # --- R1 / R3: Gebinde-Einheit wie "25 kg/Sack" oder "12,5 l/Eimer" -----
    m = _PACKAGE_UNIT_RE.search(combined)
    if m:
        size = _to_float(m.group("size"))
        pkg_unit = m.group("pkg_unit").lower()
        pkg_kind = m.group("pkg_kind").lower()
        # Wenn der Preis pro Gebinde angegeben ist (z.B. "47,50 €/Eimer"),
        # rechnen wir auf pkg_unit runter.
        if (
            pkg_kind in raw_lower
            or raw_lower == f"€/{pkg_kind}"
            or raw_lower == f"eur/{pkg_kind}"
        ):
            if size > 0:
                return UnitInfo(
                    unit=raw,
                    effective_unit=pkg_unit,
                    price_per_effective_unit=round(price / size, 4),
                    package_size=size,
                    package_unit=pkg_unit,
                    confidence=0.95,
                )

    # --- R5: Rollen mit WxL-Angabe + €/m² (kein Direktmatch oben) ---
    if "rolle" in raw_lower or "/ro" in raw_lower or "/rolle" in raw_lower:
        roll_match = _ROLL_SIZE_RE.search(combined)
        if roll_match:
            w = _to_meters(_to_float(roll_match.group("width")), roll_match.group("wu"))
            l = _to_meters(_to_float(roll_match.group("length")), roll_match.group("lu"))
            area = w * l
            if area > 0:
                return UnitInfo(
                    unit=raw,
                    effective_unit="m²",
                    price_per_effective_unit=round(price / area, 4),
                    package_size=area,
                    package_unit="m²",
                    confidence=0.90,
                )

    # --- Fallback: unklar, Review noetig -----------------------------------
    return UnitInfo(
        unit=raw,
        effective_unit=raw or "unknown",
        price_per_effective_unit=price,
        confidence=0.3,
        needs_review=True,
        note=f"Einheit '{raw_unit}' nicht automatisch erkannt. Manuelle Pruefung noetig.",
        review_reason=REVIEW_REASON_EINHEIT_NICHT_ERKANNT,
    )


def _extract_price_per_effective_unit(
    raw_unit: str,
    price: float,
    *,
    product_name: str = "",
) -> float:
    """Convenience-Wrapper: nur den normalisierten Preis zurueck."""
    info = _normalize_unit(raw_unit, product_name=product_name, price=price)
    return info.price_per_effective_unit


# ---------------------------------------------------------------------------
# P1 (B+4.3.x): Plausibilitaets-Korridore
# ---------------------------------------------------------------------------
# Jede Regel: (name, product_name_pattern, effective_unit_set, min_price, max_price)
#
# Matching-Strategie:
# - Produktname-Pattern (nicht category-String, da Kategorien haendler-
#   spezifisch und inkonsistent sind).
# - effective_unit-Set muss nach _normalize_unit matchen.
# - Erste passende Regel gewinnt. Reihenfolge: spezifisch → allgemein.
#
# Wenn Preis ausserhalb: parser_confidence=0.3, needs_review=True,
# review_reason="preis_ausserhalb_korridor". Preis wird TROTZDEM uebernommen
# (nicht verworfen) — die Entscheidung liegt beim Reviewer.
_PLAUSIBILITY_CORRIDORS: list[tuple[str, re.Pattern, set[str], float, float]] = [
    # Brandschutzplatten Fireboard/Diamant (zuerst, weil spezifischer als GKB)
    (
        "brandschutzplatte",
        re.compile(r"\b(fireboard|diamant)\b", re.IGNORECASE),
        {"m²", "m2", "qm"},
        10.0,
        30.0,
    ),
    # Gipsfaserplatten GKF/GKFi (vor GKB, damit GKF nicht als GKB matcht)
    (
        "gipsfaserplatte",
        re.compile(
            r"\b(GKFI?|Gipsfaser(?:platte)?|Fermacell\s+Powerpanel)\b",
            re.IGNORECASE,
        ),
        {"m²", "m2", "qm"},
        4.0,
        20.0,
    ),
    # Gipskartonplatten GKB/GKBI (Standard + impraegniert, kein GKF!)
    (
        "gipskartonplatte",
        re.compile(
            r"\b(GKB(?:I|i)?|Gipskartonplatte|Gipskarton[\-\s]?Bauplatte|"
            r"Bauplatte\s+GKB|HRAK)\b",
            re.IGNORECASE,
        ),
        {"m²", "m2", "qm"},
        2.0,
        12.0,
    ),
    # Profile CW/UW/UA/CD/UD
    (
        "profil",
        re.compile(
            r"\b(CW|UW|UA|CD|UD)\b[\s\-]*\d|"
            r"\b(CW|UW|UA|CD|UD)[\s\-]?Profil\b",
            re.IGNORECASE,
        ),
        {"lfm", "m"},
        1.0,
        30.0,
    ),
    # Daemmung (Mineralwolle, Steinwolle, Glaswolle)
    (
        "daemmung",
        re.compile(
            r"\b(Mineralwolle|Steinwolle|Glaswolle|Rockwool|Isover|Ursa|"
            r"Klemmfilz|Trennwandplatte|Daemmplatte)\b",
            re.IGNORECASE,
        ),
        {"m²", "m2", "qm"},
        2.0,
        15.0,
    ),
    # Putze / Moertel (pro kg nach Sack-Normalisierung)
    (
        "putz_moertel",
        re.compile(
            r"\b(Putz|Moertel|M\u00f6rtel|Ansetzbinder|Ansetzgips|Uniflott|"
            r"Fugenfueller|Fugenf\u00fcller|Rotband|Goldband|MP75|Finish)\b",
            re.IGNORECASE,
        ),
        {"kg"},
        0.5,
        3.0,
    ),
    # Schrauben (pro Stk nach Paket-Normalisierung)
    # 5-50 EUR/1000 Stk -> 0.005-0.05 EUR/Stk
    (
        "schraube",
        re.compile(
            r"\b(Schraube|Schnellbauschraube|Trockenbauschraube|TN|TB|"
            r"Spaxschraube|Holzschraube)\b",
            re.IGNORECASE,
        ),
        {"Stk", "stk"},
        0.005,
        0.05,
    ),
    # Klebebaender (Anputz, Trennband, Kantenband)
    (
        "klebeband",
        re.compile(
            r"\b(Klebeband|Anputzdichtband|Trennband|Kantenschutz(?:band)?|"
            r"Fugendichtband|Dichtungsband|Fugenband|Anschlussband)\b",
            re.IGNORECASE,
        ),
        {"lfm", "m", "Rolle"},
        0.5,
        5.0,
    ),
]


def _check_price_corridor(
    product_name: str, effective_unit: str, price_per_unit: float
) -> tuple[bool, str | None]:
    """Prueft ob der Preis in einem bekannten Produkt-Korridor liegt.

    Returns:
        (in_corridor, corridor_name)
          - (True,  "profil"):        Regel matcht UND Preis im Korridor.
          - (False, "profil"):        Regel matcht UND Preis ausserhalb.
          - (True,  None):            Keine Regel matcht (unbekannte Kategorie,
                                      kein Korridor-Check durchgefuehrt).
    """
    for name, pattern, units, lo, hi in _PLAUSIBILITY_CORRIDORS:
        if not pattern.search(product_name):
            continue
        if effective_unit not in units:
            continue
        # Regel matcht — pruefe Korridor.
        if lo <= price_per_unit <= hi:
            return True, name
        return False, name
    # Keine Regel hat gematcht.
    return True, None


# ---------------------------------------------------------------------------
# Haupt-Parser-Klasse (Claude Vision Integration)
# ---------------------------------------------------------------------------
class PricelistParser:
    """Parser fuer eine einzelne SupplierPriceList.

    Pipeline pro parse()-Call:
    1. Lade PDF-Bytes vom source_file_path (oder DB, falls bytes-Spalte existiert).
    2. PDF -> Images (Renderung via pymupdf in pdf_to_page_images).
    3. Batch-weise an Claude Vision senden mit Kemmler-System-Prompt.
    4. Pro Raw-Entry: _normalize_unit() anwenden.
    5. SupplierPriceEntry in DB anlegen.

    Der Parser ist stateless (die Status-Uebergaenge PENDING_PARSE -> PARSING ->
    PARSED/ERROR macht der Worker in pricelist_parse_worker.py).
    """

    def __init__(self, *, db, claude_client=None, batch_size: int = 3):
        self.db = db
        # claude_client optional injectable fuer Tests (Mock). Default: globaler
        # claude-Singleton aus claude_client.py.
        if claude_client is None:
            from app.services.claude_client import claude as default_client

            self._claude = default_client
        else:
            self._claude = claude_client
        self._batch_size = max(1, batch_size)

    def parse(self, pricelist_id: str) -> ParseResult:
        """Parst die Preisliste komplett. Rueckgabe: ParseResult mit Statistiken.

        Schreibt die Entries direkt in die DB (SupplierPriceEntry).
        Wirft Exception bei kritischen Fehlern (Datei nicht da, Format unbekannt,
        DB-Commit schlaegt fehl). Kleinere Fehler landen in result.errors.
        """
        from app.models.pricing import SupplierPriceEntry, SupplierPriceList
        from app.services.pdf_utils import pdf_to_page_images

        pricelist = self.db.get(SupplierPriceList, pricelist_id)
        if pricelist is None:
            raise ValueError(f"SupplierPriceList {pricelist_id} nicht gefunden")

        result = ParseResult(pricelist_id=pricelist_id)

        # 1. PDF-Bytes laden
        path = Path(pricelist.source_file_path)
        if not path.exists():
            raise FileNotFoundError(f"source_file_path fehlt: {path}")
        pdf_bytes = path.read_bytes()

        # 2. Format-Detection
        fmt = _detect_format(
            path,
            supplier_hint=pricelist.supplier_name,
        )
        if fmt != "kemmler":
            raise ValueError(
                f"Format '{fmt}' noch nicht unterstuetzt. Aktuell nur 'kemmler'."
            )

        # 3. PDF -> Images (Production-Pipeline)
        images = pdf_to_page_images(pdf_bytes, dpi=200, max_pages=80)
        log.info(
            "pricelist_parse_start",
            pricelist_id=pricelist_id,
            pages=len(images),
            batch_size=self._batch_size,
        )

        # 4. Batch-weise durch Claude Vision.
        # B+4.3: Prompt-Auswahl per Feature-Flag. Default ist der neue
        # generische Prompt (Code-Aufloesung H/T/Z/E, Rabatt, Plausibilitaet).
        # Bei Regression: Settings.use_generic_prompt=False.
        from app.core.config import settings as _settings
        if getattr(_settings, "use_generic_prompt", True):
            from app.prompts.generic_parser_prompt import SYSTEM_PROMPT
        else:
            from app.prompts.kemmler_parser_prompt import SYSTEM_PROMPT

        confidences: list[float] = []
        for start in range(0, len(images), self._batch_size):
            batch = images[start : start + self._batch_size]
            batch_idx = start // self._batch_size + 1
            page_range = f"{start + 1}-{start + len(batch)}"
            try:
                parsed, _model = self._claude.extract_json(
                    system=SYSTEM_PROMPT,
                    images=batch,
                    max_tokens=_PRICELIST_MAX_TOKENS,
                )
            except Exception as exc:
                msg = f"Batch {batch_idx} ({page_range}) fehlgeschlagen: {exc}"
                log.warning("pricelist_batch_failed", batch=batch_idx, error=str(exc))
                result.errors.append(msg)
                continue

            # Claude kann ein einzelnes Objekt {"page":..., "entries":[]} oder
            # eine Liste von Seiten zurueckgeben. Beides tolerieren.
            # Wichtig: source_page-Info vom Wrapper an jeden Entry durchreichen,
            # damit Reviewer spaeter zur Original-PDF-Seite springen koennen.
            page_entries_pairs: list[tuple[int | None, dict]] = []
            if isinstance(parsed, dict):
                if "pages" in parsed and isinstance(parsed["pages"], list):
                    for pg in parsed["pages"]:
                        if not isinstance(pg, dict):
                            continue
                        pg_num = pg.get("page")
                        for e in pg.get("entries", []):
                            if isinstance(e, dict):
                                page_entries_pairs.append((pg_num, e))
                elif "entries" in parsed and isinstance(parsed["entries"], list):
                    # Single-Page-Wrapper: {"page": N, "entries": [...]}
                    pg_num = parsed.get("page")
                    for e in parsed["entries"]:
                        if isinstance(e, dict):
                            page_entries_pairs.append((pg_num, e))
            elif isinstance(parsed, list):
                for pg in parsed:
                    if not isinstance(pg, dict):
                        continue
                    pg_num = pg.get("page")
                    for e in pg.get("entries", []):
                        if isinstance(e, dict):
                            page_entries_pairs.append((pg_num, e))

            for pg_num, raw in page_entries_pairs:
                # page vom Wrapper > source_page im Entry > None
                if pg_num is not None and raw.get("source_page") is None:
                    raw = {**raw, "source_page": pg_num}
                try:
                    entry = self._build_entry(pricelist, raw)
                except Exception as exc:
                    result.skipped_entries += 1
                    log.warning(
                        "pricelist_entry_skipped", error=str(exc), raw=str(raw)[:200]
                    )
                    continue
                self.db.add(entry)
                result.parsed_entries += 1
                result.total_entries += 1
                confidences.append(entry.parser_confidence)
                if entry.needs_review:
                    result.needs_review_count += 1

        if confidences:
            result.avg_confidence = sum(confidences) / len(confidences)

        # 5. B+4.2.7: Gebinde-Backfill fuer die gerade geparsten Entries.
        # Setzt effective_unit + price_per_effective_unit auf Entries, die
        # der Parser zwar normiert hat, deren Bundle-Preis aber noch als
        # Gesamt-Preis stehenbleibt (CW-Profil 167,40 EUR fuer 8 Stangen).
        from app.services.package_resolver import backfill_effective_units
        from app.models.pricing import SupplierPriceEntry
        self.db.flush()  # sicherstellen, dass die Entries in der Session sind
        entries_in_pricelist = (
            self.db.query(SupplierPriceEntry)
            .filter(SupplierPriceEntry.pricelist_id == pricelist_id)
            .all()
        )
        backfilled = backfill_effective_units(entries_in_pricelist)
        if backfilled:
            log.info(
                "pricelist_backfill_applied",
                pricelist_id=pricelist_id,
                entries_updated=backfilled,
            )

        # 6. Summen aufs Pricelist-Model zurueckschreiben
        pricelist.entries_total = result.parsed_entries
        pricelist.entries_reviewed = 0  # wird im Review-Flow spaeter erhoeht
        self.db.commit()

        log.info(
            "pricelist_parse_done",
            pricelist_id=pricelist_id,
            total=result.parsed_entries,
            skipped=result.skipped_entries,
            needs_review=result.needs_review_count,
            avg_confidence=round(result.avg_confidence, 3),
        )
        return result

    def _build_entry(self, pricelist, raw: dict):
        """Validiert Raw-Claude-Output + Unit-Normalisierung -> SupplierPriceEntry."""
        from app.models.pricing import SupplierPriceEntry

        product_name = (raw.get("product_name") or "").strip()
        if not product_name:
            raise ValueError("product_name fehlt")

        price_raw = raw.get("price_net")
        if price_raw is None:
            raise ValueError("price_net fehlt")
        price_net = float(price_raw)
        if price_net <= 0:
            raise ValueError(f"price_net <= 0 ({price_net})")

        unit = (raw.get("unit") or "").strip()
        if not unit:
            raise ValueError("unit fehlt")

        # Unit-Normalisierung (lokale Python-Logik, keine API)
        unit_info = _normalize_unit(unit, product_name=product_name, price=price_net)

        # Confidence: Minimum aus Parser (Vision) und Normalisierer
        claude_conf = float(raw.get("parser_confidence", 1.0) or 1.0)
        claude_conf = max(0.0, min(1.0, claude_conf))
        combined_conf = min(claude_conf, unit_info.confidence)

        # P1 (B+4.3.x): Plausibilitaets-Korridor pruefen.
        # Wenn der normalisierte Preis ausserhalb eines Produkt-typischen
        # Korridors liegt (z.B. CW-Profil 129,60 EUR/lfm statt 1-30 EUR/lfm),
        # deckeln wir die Confidence auf 0.3 und flaggen den Eintrag zum
        # Review. Der Preis wird NICHT verworfen — nur markiert.
        in_corridor, _corridor_name = _check_price_corridor(
            product_name, unit_info.effective_unit, unit_info.price_per_effective_unit
        )
        corridor_violated = not in_corridor
        if corridor_violated:
            combined_conf = min(combined_conf, 0.3)

        needs_review = bool(
            raw.get("needs_review_hint", False)
            or unit_info.needs_review
            or corridor_violated
            or combined_conf < 0.7
        )

        attributes = raw.get("attributes") or {}
        if not isinstance(attributes, dict):
            attributes = {}

        # B+4.2.6 Option C (Phase 1): strukturelle Produkt-Code-Extraktion.
        # Laeuft nach dem LLM-Parse, deterministisch und ohne API-Kosten.
        # Ergaenzt attributes.product_code_* nur wenn ein Code erkannt wurde.
        from app.services.product_code_extractor import extract_product_code
        code = extract_product_code(product_name)
        if code is not None:
            attributes["product_code_type"] = code["type"]
            attributes["product_code_dimension"] = code["dimension"]
            attributes["product_code_raw"] = code["raw"]

        # P3 (B+4.3.x): review_reason in attributes JSON persistieren.
        # Priorisierung: Was _normalize_unit gefunden hat (tieferliegende
        # Ursache: bundgroesse_fehlt, bundpreis_unklar, einheit_nicht_erkannt)
        # ist informativer als das Symptom (preis_ausserhalb_korridor).
        # Nur wenn _normalize_unit keinen Grund gesetzt hat UND der
        # Korridor verletzt ist, setzen wir preis_ausserhalb_korridor.
        if unit_info.review_reason:
            attributes["review_reason"] = unit_info.review_reason
        elif corridor_violated:
            attributes["review_reason"] = REVIEW_REASON_PREIS_AUSSERHALB_KORRIDOR

        # Currency-Normalisierung: Whitelist + Raw-Spiegelung in attributes.
        # Historie: vor Migration f8a2b3e91d04 war currency varchar(3) und
        # ein einziger abweichender LLM-Output wie "EURO" oder "€/Sack"
        # brachte die gesamte Transaction zum Rollback.
        currency, raw_currency = _normalize_currency(raw.get("currency"))
        if raw_currency is not None:
            attributes["raw_currency"] = raw_currency

        return SupplierPriceEntry(
            pricelist_id=pricelist.id,
            tenant_id=pricelist.tenant_id,
            article_number=(raw.get("article_number") or None),
            manufacturer=(raw.get("manufacturer") or None),
            product_name=product_name[:500],
            category=(raw.get("category") or None),
            subcategory=(raw.get("subcategory") or None),
            price_net=price_net,
            currency=currency,
            unit=unit[:50],
            package_size=unit_info.package_size,
            package_unit=unit_info.package_unit,
            pieces_per_package=unit_info.pieces_per_package,
            effective_unit=unit_info.effective_unit[:50],
            price_per_effective_unit=unit_info.price_per_effective_unit,
            attributes=attributes,
            source_page=raw.get("source_page"),
            source_row_raw=(raw.get("source_row_raw") or None),
            parser_confidence=combined_conf,
            needs_review=needs_review,
        )
