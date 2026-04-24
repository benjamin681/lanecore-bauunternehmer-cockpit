"""Funktional aequivalente Profil-Abmessungen fuer den DNA-Matcher.

Hintergrund
-----------
Rezepte in ``materialrezepte.py`` referenzieren Profile in der 50er-
Metallstaender-Nomenklatur (UA 50, UA 75, UA 100). Kemmler und einige
andere Haendler fuehren die historische Profilbreite (UA 48, UA 73,
UA 98) — funktional identisch (gleiches 50er-System, gleiche Statik,
gleicher Einsatzzweck).

Ohne Aequivalenzwissen liefert der Lookup auf ``|Profile|UA|50|`` ein
``not_found``, obwohl in der Preisliste geeignete UA-48-Eintraege
vorliegen. Das fuehrte in der Salach-Rekalkulation vom 2026-04-24 dazu,
dass 82 Tueroeffnungs-Positionen auf EP=0 gefallen sind.

Design
------
Die Mapping-Struktur :data:`PROFILE_SIZE_EQUIVALENCE` ist ein Dict von
Profil-Typ → Liste aequivalenter Dimensions-Paare. Jedes Paar ist ein
bidirektionaler Alias: ``(48, 50)`` heisst "48 und 50 sind austauschbar".

:func:`dimension_aliases` liefert zu einem gegebenen (type, size) alle
bekannten Alternativ-Werte. Der Aufrufer (kalkulation.py) nutzt die
Liste fuer einen Retry-Lookup, wenn der erste Versuch ``not_found``
geliefert hat.

Erweiterbarkeit
---------------
Neue Aequivalenzen werden hier eingetragen. Beispiel:
    PROFILE_SIZE_EQUIVALENCE["CW"] = [(48, 50)]
falls bei einem Haendler CW 48 auftaucht.

Stand 2026-04-24: nur UA-Profile betroffen — Kemmler-A+-Pruefung hat
keine 48/73/98-Varianten bei CW/UW/CD/UD gezeigt.
"""
from __future__ import annotations


# Bidirektionale Dimensions-Aequivalenzen pro Profil-Typ.
# Konvention: die erste Zahl ist die historische Profilbreite, die
# zweite das 50er-Systemmass. Der Matcher akzeptiert beide Richtungen.
PROFILE_SIZE_EQUIVALENCE: dict[str, list[tuple[int, int]]] = {
    "UA": [
        (48, 50),
        (73, 75),
        (98, 100),
    ],
}


def dimension_aliases(profile_type: str, size: str) -> list[str]:
    """Liefert alternative Groessen-Werte fuer ein (Typ, Groesse)-Paar.

    Args:
        profile_type: Kurz-Code des Profils (z.B. "UA"). Case-insensitive.
        size: Abmessungs-String wie er im DNA-Pattern steht ("50",
              "48x40x2", "75 mm"). Es wird versucht, die Breite (erste
              Ganzzahl) zu extrahieren und Aliases anzubieten.

    Returns:
        Liste alternativer Abmessungs-Werte als Strings. Der urspruengliche
        ``size`` ist NICHT enthalten — der Aufrufer probiert ihn zuerst und
        hier nur die Alternativen. Leere Liste wenn kein Mapping definiert.
    """
    if not profile_type or not size:
        return []
    type_key = profile_type.strip().upper()
    pairs = PROFILE_SIZE_EQUIVALENCE.get(type_key)
    if not pairs:
        return []

    # Erste Ganzzahl aus size extrahieren — toleriert "50", "48x40x2",
    # "75 mm", "100x50x0,6".
    width = _leading_int(size)
    if width is None:
        return []

    aliases: list[int] = []
    for a, b in pairs:
        if width == a and b not in aliases:
            aliases.append(b)
        elif width == b and a not in aliases:
            aliases.append(a)

    return [str(a) for a in aliases]


def _leading_int(value: str) -> int | None:
    """Holt die erste zusammenhaengende Ganzzahl aus einem String."""
    acc = ""
    for ch in value.strip():
        if ch.isdigit():
            acc += ch
        elif acc:
            break
    if not acc:
        return None
    try:
        return int(acc)
    except ValueError:
        return None
