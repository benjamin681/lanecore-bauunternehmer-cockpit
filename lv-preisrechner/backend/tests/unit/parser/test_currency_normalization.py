"""Unit-Tests fuer ``_normalize_currency`` im pricelist_parser.

Hintergrund: Der LLM-basierte PDF-Parser liefert fuer die currency-
Spalte in seltenen Faellen Varianten wie "EURO", "Euro", "€/Sack" oder
" EUR " (mit Whitespace). Diese Randfaelle liessen das gesamte
Batch-Insert der Supplier-Preisliste mit
``StringDataRightTruncation`` an der ``varchar(3)``-Spalte abbrechen.

Die Helper-Funktion normalisiert Claude-Output auf eine kleine
Whitelist (EUR/USD/CHF/GBP) und spiegelt abweichende Rohwerte in
``attributes["raw_currency"]`` fuers Debugging.

Die Tests gliedern sich in:
- Whitelist-Hit (sauber oder normalisierbar).
- Fallback (unbekannter/kaputter Wert).
- Edge-Cases (None, leere Strings, Nicht-String-Typen).
"""
from __future__ import annotations

import pytest

from app.services.pricelist_parser import (
    CURRENCY_DEFAULT,
    _normalize_currency,
)


# --------------------------------------------------------------------------- #
# Whitelist-Hit
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw_input, expected_currency, expected_raw",
    [
        ("EUR", "EUR", None),          # Pass-through, kein Raw-Eintrag
        ("USD", "USD", None),
        ("CHF", "CHF", None),
        ("GBP", "GBP", None),
    ],
)
def test_currency_whitelist_passthrough(raw_input, expected_currency, expected_raw):
    """Saubere ISO-4217-Codes laufen ohne Normalisierungs-Spur durch."""
    currency, raw = _normalize_currency(raw_input)
    assert currency == expected_currency
    assert raw == expected_raw


@pytest.mark.parametrize(
    "raw_input, expected_raw",
    [
        ("eur", "eur"),          # lower-case → upper, raw wird gespiegelt
        ("Eur", "Eur"),          # mixed case, raw gespiegelt
    ],
)
def test_currency_case_normalized(raw_input, expected_raw):
    """Case-Varianten werden auf EUR gemappt und als raw-Spur geloggt."""
    currency, raw = _normalize_currency(raw_input)
    assert currency == "EUR"
    assert raw == expected_raw


def test_currency_pure_whitespace_is_silent():
    """Reiner Whitespace um einen sauberen Whitelist-Code spiegelt NICHT.

    Rationale: strip+upper landet auf dem Whitelist-Eintrag und das
    Original unterscheidet sich nur durch Whitespace — keine
    Debugging-relevante Drift.
    """
    currency, raw = _normalize_currency(" EUR ")
    assert currency == "EUR"
    assert raw is None


# --------------------------------------------------------------------------- #
# Fallback
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw_input",
    [
        "EURO",          # Hauefigste LLM-Abweichung
        "Euro",
        "€/Sack",        # Einheit rutscht ins Currency-Feld
        "Sack",          # Nur Einheit
        "  €  ",         # Nur Symbol, nicht im Whitelist
        "DM",            # historischer Code
        "JPY",           # gueltig aber nicht im Whitelist
    ],
)
def test_currency_fallback_to_default(raw_input):
    """Unbekannte oder nicht-whitelistete Werte landen auf EUR + raw."""
    currency, raw = _normalize_currency(raw_input)
    assert currency == CURRENCY_DEFAULT == "EUR"
    # Raw muss gespiegelt werden (fuer Debugging)
    assert raw == raw_input.strip()


# --------------------------------------------------------------------------- #
# Edge-Cases
# --------------------------------------------------------------------------- #
def test_currency_none_input():
    currency, raw = _normalize_currency(None)
    assert currency == "EUR"
    assert raw is None


@pytest.mark.parametrize("raw_input", ["", "   ", "\t\n"])
def test_currency_empty_string(raw_input):
    currency, raw = _normalize_currency(raw_input)
    assert currency == "EUR"
    assert raw is None
