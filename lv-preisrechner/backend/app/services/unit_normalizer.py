"""Einheiten-Synonym-Matching fuer den price_lookup (B+4.2.6).

Problem: SupplierPriceEntries tragen die Einheit so, wie sie auf der
Lieferanten-Rechnung steht — zum Beispiel "€/m", "Stk.", "Sack". Die
DNA-Pattern aus dem Material-Rezept nutzen die interne Schreibweise
"lfm", "St.", "m²". Ein strikter Equality-Filter scheitert an solchen
Varianten, obwohl die Einheiten semantisch identisch sind.

Loesung: Eine kleine Synonym-Tabelle pro Groesse (Laenge, Stueck,
Flaeche, Gewicht, Volumen, Paketformen) und eine einzige
Public-Function `unit_matches(a, b)`. Case-insensitiv, ignoriert
Whitespace und das fuehrende Currency-Praefix ("€/...").

Scope:
- Keine Umrechnung (0.5 m != 50 cm werden NICHT gleichgesetzt).
- Keine Gebinde-Logik (z. B. "Sack/25kg" vs. "kg" — das regelt die
  Parser-Pipeline in price_per_effective_unit).
- Einfache Lookup-Tabelle, kein ML.
"""

from __future__ import annotations

import re


# Synonym-Klassen. Jeder Set enthaelt die TOKEN-Varianten, die gegenseitig
# als aequivalent behandelt werden. Die Eintraege sind bereits auf die
# Form nach _canonical() — Kleinbuchstaben, ohne Punkt/Slash/Whitespace.
_SYNONYMS: list[set[str]] = [
    # Laenge
    {"m", "lfm", "lfdm", "laufm", "laufendermeter", "laufendemeter", "lfdmeter"},
    # Stueck
    {"st", "stk", "stueck", "stk", "pce", "pc", "pcs"},
    # Flaeche
    {"m2", "m²", "qm", "qm²"},
    # Gewicht
    {"kg", "kilogramm", "kilo"},
    # Volumen
    {"l", "ltr", "liter"},
    # Rolle
    {"rol", "rolle", "rollen", "rl"},
    # Paket (lose Packung)
    {"pkg", "pack", "packung", "pak", "paket"},
    # Sack
    {"sack", "sk"},
    # Eimer
    {"eimer", "eim"},
    # Karton
    {"karton", "ktn"},
    # Bund/Bündel
    {"bund", "bd"},
    # Satz (Kemmler-Eigenart für Montagesets)
    {"satz", "set"},
    # Flasche
    {"flasche", "fl", "fla", "flasch"},
]


# Tabelle: token -> kanonische Klassen-ID
_TOKEN_TO_CLASS: dict[str, int] = {}
for idx, cls in enumerate(_SYNONYMS):
    for token in cls:
        _TOKEN_TO_CLASS[token] = idx


# Regex: entferne Currency-Prefixe wie "€/" oder "EUR/" am Anfang und
# reduziere dann auf alphanum + "²"
_PREFIX_RE = re.compile(r"^\s*(€|eur|\$|chf)\s*/\s*", re.IGNORECASE)
_STRIP_RE = re.compile(r"[\.\s/\\_\-]+")


_UMLAUT_MAP = str.maketrans({"ü": "ue", "ö": "oe", "ä": "ae", "ß": "ss"})


def _canonical(unit: str | None) -> str:
    """Reduziert einen Einheiten-String auf eine vergleichbare Form."""
    if not unit:
        return ""
    s = unit.strip().lower()
    s = s.translate(_UMLAUT_MAP)  # "stück" -> "stueck"
    s = _PREFIX_RE.sub("", s)
    s = _STRIP_RE.sub("", s)
    # "m²" -> "m2" — lass uns "²" als 2 behandeln, damit die Klasse
    # {"m2", "m²", "qm", "qm²"} greift. "qm²" darf nicht zu "qm2"
    # kanonisiert werden, denn das wuerde es aus der Klasse werfen.
    # Daher behalten wir Sonderzeichen in der Klassen-Tabelle bei und
    # erlauben beide Formen.
    if s.endswith("²"):
        s_alt = s[:-1] + "2"
    else:
        s_alt = s
    # Wir probieren beide Formen — wenn eine in der Klassen-Tabelle ist,
    # gewinnt sie.
    if s in _TOKEN_TO_CLASS:
        return s
    if s_alt in _TOKEN_TO_CLASS:
        return s_alt
    return s


def unit_matches(a: str | None, b: str | None) -> bool:
    """True wenn a und b derselben Einheiten-Klasse angehoeren oder exakt
    gleich sind. Leere/None-Werte gelten als nicht-match.

    Beispiele:
      unit_matches("m", "lfm")        -> True
      unit_matches("St.", "Stk.")     -> True
      unit_matches("€/m", "lfm")      -> True
      unit_matches("m²", "qm")        -> True
      unit_matches("kg", "Sack")      -> False
      unit_matches("kg", None)        -> False
    """
    ca = _canonical(a)
    cb = _canonical(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    ai = _TOKEN_TO_CLASS.get(ca)
    bi = _TOKEN_TO_CLASS.get(cb)
    # Nur wenn beide in einer bekannten Klasse landen UND in derselben.
    if ai is not None and bi is not None and ai == bi:
        return True
    return False
