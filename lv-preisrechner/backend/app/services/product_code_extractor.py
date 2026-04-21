"""B+4.2.6 Option C — Phase 1.

Extrahiert den strukturellen Produkt-Code aus einem freien Produktnamen.
Ein Produkt-Code im Sinne dieses Moduls ist ein Token der Form

    <TYP><DIMENSION>

mit TYP = 2 oder 3 ASCII-Grossbuchstaben und DIMENSION = ein oder mehr
Ziffern. Beispiele aus dem Kemmler-Katalog: ``CW75``, ``UW100``,
``KKZ30``, ``SLP30``, ``TP50``.

Die Funktion ist **rein deterministisch** — kein LLM, kein Netzwerk-
Call. Sie wird vom Parser nach dem LLM-Parse aufgerufen und ergaenzt
die strukturierten Felder in ``attributes``, **ohne** den LLM-Output
zu aendern.

Semantisch **neutral**: Der Extraktor entscheidet NICHT, ob ein
extrahierter Code matching-relevant ist (z. B. ``UT40`` aus einem
PE-Folien-Produktcode). Diese Entscheidung gehoert in den Matcher
(Phase 2).

Scope-Entscheidungen (siehe ``docs/b426_optionC_phase1_baseline.md``):

- Regex bleibt einfach ``[A-Z]{2,3}\\d+`` — Doppel-Dimensionen wie
  ``CD60/27`` werden auf ``CD60`` verkuerzt.
- Trennzeichen ``-`` oder ``_`` zwischen Alpha- und Digit-Teil werden
  toleriert (``CW-75`` -> ``CW75``).
- Leerzeichen zwischen Alpha- und Digit-Teil werden ebenfalls toleriert
  (``CW 75`` -> ``CW75``). Die Toleranz ist konservativ: nach dem
  Alpha-Token muss **direkt** das Digit-Token folgen, um False-Positives
  durch Fliesstext (``CW Profil 75 mm``) zu vermeiden.
- Bei mehreren Matches im Namen gewinnt das **erste** Vorkommen.
- Kein Match -> die Funktion gibt ``None`` zurueck.
"""

from __future__ import annotations

import re

# Vor-Normalisierung: entferne Bindestriche/Unterstriche zwischen
# einem Alpha- und einem Digit-Token. Leerzeichen werden beibehalten,
# aber das eigentliche Match-Pattern erlaubt sie optional zwischen den
# beiden Teilen.
_STRIP_TRENNER_RE = re.compile(r"([A-Z])[-_]+(\d)")

# Match-Pattern: 2..3 ASCII-Grossbuchstaben, optional EIN Leerzeichen,
# dann eine oder mehr Ziffern. Keine Word-Boundary am Anfang, damit
# z. B. "Kemmler KKZ30" den KKZ30-Code findet — der Anfang ist dann
# entweder ein anderes Wort oder String-Start.
_CODE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2,3}) ?(\d+)")


def extract_product_code(name: str | None) -> dict | None:
    """Findet den ersten Produkt-Code im Namen.

    Args:
        name: Freier Produktname aus dem Parser-Response. ``None`` oder
            leerer String liefert ``None``.

    Returns:
        ``{"type": "CW", "dimension": "75", "raw": "CW75"}`` wenn ein
        Code gefunden wurde, sonst ``None``. Die Keys sind immer alle
        drei vorhanden; der Caller entscheidet, welche er ins
        ``attributes``-Dict uebernimmt.
    """
    if not name:
        return None
    # Vor-Normalisierung: Trenner zwischen Alpha und Digit entfernen.
    normalized = _STRIP_TRENNER_RE.sub(r"\1\2", name)
    m = _CODE_RE.search(normalized)
    if not m:
        return None
    alpha = m.group(1)
    digit = m.group(2)
    return {
        "type": alpha,
        "dimension": digit,
        "raw": f"{alpha}{digit}",
    }
