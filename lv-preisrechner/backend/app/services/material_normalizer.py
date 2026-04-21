"""Material-Namen-Normalisierung fuer Fuzzy-Matching (B+4.2.5 / 4.2.6).

Problem: Reale Kemmler-Artikelnamen ("Knauf DIAMANT Hartgipspl. GKFI
2000x1250x12,5 mm") und interne DNA-Pattern ("Knauf|Gipskarton|GKFI|12.5|")
haben dieselbe Produkt-DNA, aber wegen Klammer-Inhalt, Artikelnummern-
Suffixen, Einheitensuffixen und Formatierungsvarianten liegt eine naive
Ratio bei ~0.45 — unter der Schwelle 0.85, die price_lookup.py als
Fuzzy-Trefferkriterium nutzt.

Loesung: Beide Seiten auf eine kanonische Token-Form reduzieren und
asymmetrische Token-Coverage rechnen ("Wie viel Prozent der Pattern-
Tokens sind im Produktnamen enthalten?"). Reihenfolge-invariant und
robust gegen zusaetzliches Rauschen in einem der Strings.

Design:
- `normalize_product_name(s)` fuer freie Produktbezeichnungen.
- `normalize_dna_pattern(p)` fuer DNA-Pattern der Form A|B|C|D|E
  (Kategorie wird bewusst verworfen; siehe Docstring).
- `fuzzy_match_score(product_name, dna_pattern)` und
  `score_query_against_candidate(query, candidate)` liefern beide den
  asymmetrischen Coverage-Score in [0, 100].

Nicht enthalten: aggressive Synonymisierung (GKF↔GKB, GKFI↔GKBI). Das
waere eine Falschinformation — GKFI ist Feuerschutz imprägniert, GKB
ist die Standardplatte. Nur *identische* Codes werden als Token
behalten.

rapidfuzz-Entscheidung (B+4.2.6 Scope C): wurde aus den Abhaengigkeiten
entfernt. Die Coverage-Metrik braucht rapidfuzz nicht; der stdlib-
SequenceMatcher-Fallback in price_lookup._best_fuzzy reicht als zweite
Sicherung voellig aus. Wiedereinfuehrung waere trivial, sobald ein
echter Rechtschreibfehler-Case auftritt, der Coverage nicht loest.
"""

from __future__ import annotations

import re
from functools import lru_cache


# ---------------------------------------------------------------------------
# Regex-Werkzeuge (kompiliert, modulweit wiederverwendet)
# ---------------------------------------------------------------------------

# Artikelnummern-Suffix: "Nr. 00123456" / "Art.-Nr. 12345"
_ARTICLE_NR_RE = re.compile(r"\b(?:nr\.?|art\.?\s*-?\s*nr\.?)\s*\d{3,}\b", re.IGNORECASE)

# Package/Bundle-Marker, die nichts zur Identifikation beitragen:
# "100 St./Pak.", "100 Stk/Ktn.", "8 St./Bd.", "BL=2600 mm"
_PACKAGE_MARKER_RE = re.compile(
    r"\b(?:\d+\s*(?:stk|st|pak|bd|bund|ktn|karton|rolle|rol|sack|pal)[\./]*\.?|bl\s*=\s*\d+\s*mm)\b",
    re.IGNORECASE,
)

# Masse: "12,5 mm" / "12.5mm" / "2000 mm" / "1250x12,5 mm"
# Entfernt die "mm"-Einheit nach einer Zahl und normalisiert Komma zu Punkt.
_MM_UNIT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\b", re.IGNORECASE)

# Kilogramm-Paketung: "30 kg/Sack" oder "25 kg" -> behalten wir als "30kg"
# Wichtig: der Schraegstrich + "Sack|Eimer|Fl.|Flasche|Rolle" darf weg.
_KG_PACK_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*kg(?:\s*/\s*[a-zäöüß\.]+)?",
    re.IGNORECASE,
)

# Gramm-Paketung: "800 g/Fl.asche" / "165 g/m²"
_G_PACK_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*g(?:\s*/\s*[a-zäöüß\.\²\³0-9]+)?",
    re.IGNORECASE,
)

# Klammer-Inhalte: "(HRAK)", "(LaMassiv - GKF)", "(Haftputz)"
# Den INHALT behalten wir, aber ohne Klammern — token_set_ratio kommt damit klar.
_PAREN_RE = re.compile(r"[()]")

# Komma in Dezimalzahlen zu Punkt: "12,5" -> "12.5"
_DECIMAL_COMMA_RE = re.compile(r"(\d),(\d)")

# Mehrfach-Whitespace kollabieren
_WS_RE = re.compile(r"\s+")

# Nicht-alphanumerische Trenner entfernen (ausser Punkt in "12.5" und Bindestrich
# bei "UA-Profil"): wir reduzieren auf Token-Grenzen. Bindestriche werden zu
# Leerzeichen, damit "UA-Profil" in Tokens "ua" + "profil" zerfaellt — das
# erhoeht token_set_ratio-Trefferwahrscheinlichkeit gegen DNA-Pattern, die
# Produktname und Variante separat fuehren.
_NON_TOKEN_CHARS_RE = re.compile(r"[_/,;:=\-–—+\[\]\{\}\|\"'`*]")

# Abmessungstupel "2000x1250x12.5" → "2000 1250 12.5" (x zwischen Zahlen splitten)
_DIM_X_RE = re.compile(r"(?<=\d)[x×](?=\d)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@lru_cache(maxsize=2048)
def normalize_product_name(name: str) -> str:
    """Bereitet einen freien Produktnamen fuer Fuzzy-Matching vor.

    Beispiele:
      >>> normalize_product_name("Knauf DIAMANT Hartgipspl. GKFI 2000x1250x12,5 mm")
      'knauf diamant hartgipspl. gkfi 2000x1250x12.5'
      >>> normalize_product_name("Anschlusswinkel f. UA-Profil 48 mm - Nr. 00708449")
      'anschlusswinkel f. ua profil 48'

    Schritte:
      1. lowercase
      2. Artikelnummern-Suffixe entfernen
      3. Package-Marker entfernen ("100 St./Pak.", "BL=2600 mm")
      4. Dezimal-Komma zu Punkt
      5. "mm"-Einheit hinter Zahlen entfernen (Zahl bleibt)
      6. "kg"/"g"-Packung kondensieren ("30 kg/Sack" -> "30kg")
      7. Klammern entfernen (Inhalt bleibt als Tokens)
      8. Nicht-Token-Zeichen durch Leerzeichen ersetzen
      9. Whitespace kollabieren
    """
    if not name:
        return ""
    s = name.lower()

    # 2. Artikelnummer
    s = _ARTICLE_NR_RE.sub(" ", s)

    # 3. Package-Marker
    s = _PACKAGE_MARKER_RE.sub(" ", s)

    # 4. Dezimal-Komma zu Punkt (wiederholt anwenden, falls 3-stellige Dezimalen)
    s = _DECIMAL_COMMA_RE.sub(r"\1.\2", s)
    s = _DECIMAL_COMMA_RE.sub(r"\1.\2", s)

    # 4b. "2000x1250x12.5" -> "2000 1250 12.5" (damit alle Zahlen eigene
    # Tokens werden; das verbessert token_set_ratio erheblich)
    s = _DIM_X_RE.sub(" ", s)

    # 6. kg/g-Packung (vor mm, sonst wuerde "800 g/Fl.asche" durchschlupfen)
    s = _KG_PACK_RE.sub(lambda m: f" {m.group(1)}kg ", s)
    s = _G_PACK_RE.sub(lambda m: f" {m.group(1)}g ", s)

    # 5. mm-Einheit
    s = _MM_UNIT_RE.sub(lambda m: f" {m.group(1)} ", s)

    # 7. Klammern raus
    s = _PAREN_RE.sub(" ", s)

    # 8. sonstige Trennzeichen zu Leerzeichen
    s = _NON_TOKEN_CHARS_RE.sub(" ", s)

    # 9. whitespace kollabieren
    s = _WS_RE.sub(" ", s).strip()
    return s


@lru_cache(maxsize=2048)
def normalize_dna_pattern(pattern: str) -> str:
    """Normalisiert einen DNA-Pattern ("Hersteller|Kategorie|Produktname|
    Abmessungen|Variante") zur gleichen Token-Form wie `normalize_product_name`.

    **Kategorie wird absichtlich verworfen**, weil sie ein internes Meta-
    Attribut ist und in realen Produktnamen nicht vorkommt (z. B. ein
    "Knauf DIAMANT Hartgipspl. GKFI 12,5 mm" enthaelt das Wort
    "Gipskarton" nicht explizit). Hersteller bleibt erhalten.

    Beispiele:
      >>> normalize_dna_pattern("Knauf|Gipskarton|GKFI|12.5|")
      'knauf gkfi 12.5'
      >>> normalize_dna_pattern("|Trockenbauprofile|CW|100|")
      'cw 100'
    """
    if not pattern:
        return ""
    parts = pattern.split("|")
    # Struktur: [hersteller, kategorie, produktname, abmessungen, variante]
    keep: list[str] = []
    for idx, raw in enumerate(parts):
        if idx == 1:  # Kategorie ueberspringen
            continue
        s = raw.strip()
        if s:
            keep.append(s)
    return normalize_product_name(" ".join(keep))


def fuzzy_match_score(*, product_name: str, dna_pattern: str) -> float:
    """Liefert einen asymmetrischen Coverage-Score in [0, 100].

    Definition:
      score = 100 * |Schnittmenge(pat_tokens, prod_tokens)| / |pat_tokens|

    Das heisst: "Wie viel Prozent der Pattern-Tokens sind im Produktnamen
    enthalten?" Asymmetrisch deshalb, weil der reale Produktname haeufig
    zusaetzliche Tokens enthaelt (Abmessungen, Verpackungshinweise,
    Artikelnummern), die das Matching nicht stoeren duerfen.

    Rueckgabe: 0.0 wenn eine Seite leer, sonst in [0, 100].
    """
    prod = normalize_product_name(product_name)
    pat = normalize_dna_pattern(dna_pattern)
    if not prod or not pat:
        return 0.0
    prod_tokens = set(prod.split())
    pat_tokens = set(pat.split())
    if not pat_tokens:
        return 0.0
    matched = sum(1 for t in pat_tokens if t in prod_tokens)
    return 100.0 * matched / len(pat_tokens)


def score_query_against_candidate(query: str, candidate: str) -> float:
    """Fuzzy-Score fuer "freier Anfrage-String gegen Katalog-Produktname".

    Beide Seiten werden durch `normalize_product_name` geschickt und
    anschliessend wird die asymmetrische Token-Coverage berechnet:
    Wie viel Prozent der Anfrage-Tokens sind im Katalog-Namen enthalten?

    Verwendet von `price_lookup.lookup_price` in der Fuzzy-Stufe (2c/3c),
    wo `material_name` die Anfrage ist und `entry.product_name` der
    Katalog-Eintrag.

    Rueckgabe: 0.0 wenn Anfrage leer, sonst in [0, 100].
    """
    q_norm = normalize_product_name(query)
    c_norm = normalize_product_name(candidate)
    # B+4.2.6: Verschmolzene Typ+Dim-Tokens ("cw75") in zwei Tokens zerlegen,
    # bevor wir mit dem Token-Set arbeiten. Das trifft die Rezept-Eingaben
    # aus kalkulation._resolve_material_via_lookup, wo material_name ohne
    # Leerzeichen gejoint wird.
    q_norm = _explode_alnum(q_norm)
    c_norm = _explode_alnum(c_norm)
    q_tokens_list = q_norm.split()
    c_tokens_list = c_norm.split()
    q_tokens = set(q_tokens_list)
    c_tokens = set(c_tokens_list)
    if not q_tokens:
        return 0.0

    # Baseline-Score (asymmetrische Coverage) -- bleibt als Fallback-Signal.
    matched = sum(1 for t in q_tokens if t in c_tokens)
    residual = 100.0 * matched / len(q_tokens)

    # B+4.2.6: Die Typ-/Dimensions-Spezial-Logik greift nur fuer
    # *Profil-Code-Anfragen* (kurzer Typ-Code wie "cw"/"uw"/"ua"/"cd"/"ud"
    # + genau eine numerische Dimension). Produktnamen wie "Rotband Pro"
    # oder "Knauf Diamant" bleiben beim urspruenglichen Coverage-Score.
    q_dims = {t for t in q_tokens if _is_numeric_token(t)}
    q_alpha = [t for t in q_tokens_list if t.isalpha()]
    # B+4.2.6-Iteration 3: Harte Typ-Priorisierung nur fuer bekannte
    # Trockenbau-Profil-Codes. Andere 2-Token-Anfragen (z. B. "GKB 12.5",
    # "Rotband Pro") fallen zurueck auf den urspruenglichen Coverage-Score,
    # damit hier kein False-Negative entsteht.
    _STRICT_TYPE_CODES = {"cw", "uw", "ua", "cd", "ud"}
    is_profile_code = (
        len(q_tokens_list) == 2
        and len(q_alpha) == 1
        and q_alpha[0] in _STRICT_TYPE_CODES
        and len(q_dims) == 1
    )
    if not is_profile_code:
        return residual

    q_type = q_alpha[0]
    c_type = _leading_alpha_token(c_tokens_list)
    type_match = 100.0 if q_type == c_type else 0.0

    c_dims = {t for t in c_tokens if _is_numeric_token(t)}
    dim_match = 100.0 if q_dims & c_dims else 0.0

    # Gewichtung: 60 % Typ / 25 % Dim / 15 % Residual (B+4.2.6-Iteration 2)
    return 0.60 * type_match + 0.25 * dim_match + 0.15 * residual


# --------------------------------------------------------------------------- #
# Interne Helfer fuer B+4.2.6-Scoring
# --------------------------------------------------------------------------- #
_ALNUM_SPLIT_RE = re.compile(r"([a-z]+)(\d)")


def _explode_alnum(text: str) -> str:
    """Zerlegt verschmolzene Typ+Zahl-Tokens: "cw75" -> "cw 75".

    Greift nur bei lowercase Buchstaben gefolgt von einer Ziffer, damit
    Produktnamen mit Groesserpaketen wie "DIN4103" erhalten bleiben.
    """
    return _ALNUM_SPLIT_RE.sub(r"\1 \2", text)


def _leading_alpha_token(tokens: list[str]) -> str | None:
    """Erstes rein-alphabetisches Token mit mind. 2 Zeichen."""
    for tok in tokens:
        if len(tok) >= 2 and tok.isalpha():
            return tok
    return None


def _is_numeric_token(tok: str) -> bool:
    """True, wenn der Token eine Zahl (auch Dezimal mit Punkt) ist."""
    try:
        float(tok)
        return True
    except ValueError:
        return False
