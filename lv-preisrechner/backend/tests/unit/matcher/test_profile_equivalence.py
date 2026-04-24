"""Tests fuer :mod:`app.services.profile_equivalence`.

Sichert:
- UA 48 <-> UA 50, UA 73 <-> UA 75, UA 98 <-> UA 100 (bidirektional).
- Abmessungs-Strings mit Suffix ("48x40x2", "50 mm") werden toleriert.
- Unbekannte Profil-Typen oder Groessen geben leere Alias-Liste zurueck.
- Case-Insensitive am Typ-Namen.
"""
from __future__ import annotations

import pytest

from app.services.profile_equivalence import (
    PROFILE_SIZE_EQUIVALENCE,
    dimension_aliases,
)


# --------------------------------------------------------------------------- #
# Bidirektionaler Alias-Hit
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "profile_type, size, expected",
    [
        # 50er System -> historische Breite
        ("UA", "50", ["48"]),
        ("UA", "75", ["73"]),
        ("UA", "100", ["98"]),
        # Historisch -> 50er System
        ("UA", "48", ["50"]),
        ("UA", "73", ["75"]),
        ("UA", "98", ["100"]),
    ],
)
def test_ua_bidirectional_alias(profile_type, size, expected):
    assert dimension_aliases(profile_type, size) == expected


# --------------------------------------------------------------------------- #
# Suffix-Toleranz auf der Abmessung
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "size_input, expected",
    [
        ("48x40x2", ["50"]),          # voller Kemmler-Produkt-Suffix
        ("50 mm", ["48"]),            # Leerzeichen + Einheit
        ("  75  ", ["73"]),           # Whitespace-Padding
        ("100x40x2 mm", ["98"]),      # Dim+Einheit kombiniert
    ],
)
def test_size_suffix_toleranz(size_input, expected):
    assert dimension_aliases("UA", size_input) == expected


# --------------------------------------------------------------------------- #
# Case-Insensitive am Typ
# --------------------------------------------------------------------------- #
def test_case_insensitive_profile_type():
    assert dimension_aliases("ua", "50") == ["48"]
    assert dimension_aliases("Ua", "50") == ["48"]
    assert dimension_aliases(" UA ", "50") == ["48"]


# --------------------------------------------------------------------------- #
# Keine Aliase fuer unbekannte Typen / Groessen
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "profile_type, size",
    [
        ("CW", "50"),            # kein Mapping definiert fuer CW
        ("UW", "75"),            # kein Mapping definiert fuer UW
        ("UA", "60"),            # UA hat keinen Alias fuer 60
        ("UA", "500"),           # abwegige Groesse
        ("", "50"),              # leerer Typ
        ("UA", ""),              # leere Groesse
        ("UA", "no-digits"),     # keine Ganzzahl extrahierbar
    ],
)
def test_no_alias_returns_empty(profile_type, size):
    assert dimension_aliases(profile_type, size) == []


# --------------------------------------------------------------------------- #
# Keine Selbst-Duplikate in den Aliases
# --------------------------------------------------------------------------- #
def test_alias_enthaelt_nicht_den_ausgangswert():
    """Der Rueckgabewert enthaelt NUR Alternativen, nicht das Original."""
    assert "50" not in dimension_aliases("UA", "50")
    assert "48" not in dimension_aliases("UA", "48")


# --------------------------------------------------------------------------- #
# Mapping-Struktur-Sanity
# --------------------------------------------------------------------------- #
def test_mapping_struktur_sanity():
    """Jedes Paar ist ein echtes Paar mit zwei verschiedenen Zahlen."""
    for ptype, pairs in PROFILE_SIZE_EQUIVALENCE.items():
        assert ptype.isupper(), f"Key {ptype} sollte uppercase sein"
        for a, b in pairs:
            assert isinstance(a, int) and isinstance(b, int)
            assert a != b, f"Pair ({a}, {b}) — Selbst-Aequivalenz ergibt keinen Sinn"
