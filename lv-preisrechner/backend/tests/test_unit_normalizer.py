"""Unit-Tests fuer app.services.unit_normalizer (B+4.2.6 Scope A)."""

from __future__ import annotations

import pytest

from app.services.unit_normalizer import unit_matches


# ---------------------------------------------------------------------------
# Positive: gleiche Klasse -> True
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "a,b",
    [
        ("m", "lfm"),
        ("lfm", "lfdm"),
        ("m", "Laufm"),
        ("St.", "Stk."),
        ("Stk.", "Stück"),
        ("pce", "pc"),
        ("m²", "qm"),
        ("M2", "qm²"),
        ("kg", "Kilogramm"),
        ("l", "Ltr"),
        ("Rolle", "Rol."),
        ("Pak.", "Packung"),
        ("Sack", "Sk."),
        ("Eimer", "Eim."),
        ("Karton", "Ktn."),
        ("Bund", "Bd."),
        ("Satz", "Set"),
    ],
)
def test_unit_matches_positive(a, b):
    assert unit_matches(a, b) is True, f"{a!r} sollte {b!r} matchen"


# ---------------------------------------------------------------------------
# Negative: verschiedene Klassen -> False
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "a,b",
    [
        ("kg", "Sack"),       # Gewicht vs. Gebinde
        ("m", "m²"),          # Laenge vs. Flaeche
        ("Stk", "m"),         # Stueck vs. Laenge
        ("l", "kg"),          # Volumen vs. Gewicht
        ("Rolle", "Sack"),    # unterschiedliche Gebinde
        ("m²", "kg"),
    ],
)
def test_unit_matches_negative(a, b):
    assert unit_matches(a, b) is False, f"{a!r} darf nicht mit {b!r} matchen"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
def test_unit_matches_empty_vs_string_is_false():
    assert unit_matches("", "m") is False
    assert unit_matches("m", "") is False
    assert unit_matches("", "") is False


def test_unit_matches_none_handled():
    assert unit_matches(None, "m") is False
    assert unit_matches("m", None) is False
    assert unit_matches(None, None) is False


def test_unit_matches_case_insensitive():
    assert unit_matches("M", "lfm") is True
    assert unit_matches("LFM", "m") is True
    assert unit_matches("STÜCK", "stk") is True


def test_unit_matches_ignores_currency_prefix():
    assert unit_matches("€/m", "lfm") is True
    assert unit_matches("EUR/Stk.", "St.") is True
    assert unit_matches("€/m²", "qm") is True


def test_unit_matches_ignores_whitespace_and_punct():
    assert unit_matches(" m ", "lfm") is True
    assert unit_matches("Stk.", " Stück ") is True
    assert unit_matches("Rol.", "Rolle") is True


def test_unit_matches_unknown_units_only_exact():
    """Unbekannte Einheiten (nicht in der Synonym-Tabelle) matchen nur
    bei exakter Gleichheit — nicht gegenueber anderen Unbekannten."""
    assert unit_matches("foo", "foo") is True
    assert unit_matches("foo", "bar") is False


def test_unit_matches_identity_m2_umlaut():
    """Beide Varianten der Flaechen-Einheit sind gleich."""
    assert unit_matches("m²", "m2") is True
    assert unit_matches("qm²", "m²") is True
