"""B+4.2.6 Option C Phase 1c — Unit-Tests fuer :mod:`product_code_extractor`.

Die Tests sind in drei Gruppen gegliedert:

1. Happy-Path — Eingaben, die einen Produkt-Code enthalten und korrekt
   extrahiert werden muessen.
2. Guard-Tests — Eingaben, die bewusst NICHT matchen sollen, damit keine
   False-Positives entstehen.
3. Integration — Parser-Flow-Smoke-Test ohne echten LLM-Call.

Scope-Erinnerung (siehe ``docs/b426_optionC_phase1_baseline.md``):

- Regex: ``[A-Z]{2,3}\\d+`` (streng, Grossbuchstaben).
- Trennzeichen ``-`` / ``_`` zwischen Alpha und Digit werden entfernt.
- Ein Leerzeichen zwischen Alpha und Digit ist toleriert.
- Erstes Vorkommen gewinnt.
- Kein Match → Rueckgabe ``None``.
"""

from __future__ import annotations

import pytest

from app.services.product_code_extractor import extract_product_code


# --------------------------------------------------------------------------- #
# Happy Path
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name,expected_type,expected_dim,expected_raw",
    [
        ("CW 75x50x0,6 mm", "CW", "75", "CW75"),
        ("CW-75 Profil", "CW", "75", "CW75"),
        ("CW75 testing", "CW", "75", "CW75"),
        ("Kemmler KKZ30 Kalkzementputz 30 kg/Sack", "KKZ", "30", "KKZ30"),
        ("Kemmler SLP30 Styroporleichtputz 30 kg/Sack", "SLP", "30", "SLP30"),
        ("Knauf MP75 Leichtputz", "MP", "75", "MP75"),
        ("PE-Folie S=0,20 mm - 4000 mm x 50 m/Ro. UT40", "UT", "40", "UT40"),
        ("ASA01 Ankerschnellabhänger für CD-Profil", "ASA", "01", "ASA01"),
        (
            "Trennwandpl. Sonorock WLG040, 1000x625x40 mm - 7,5 m²/Pak.",
            "WLG",
            "040",
            "WLG040",
        ),
    ],
)
def test_extract_happy_path(name, expected_type, expected_dim, expected_raw):
    """Standard-Produktcodes werden korrekt extrahiert.

    Zweck: sichert, dass die 2-3-Buchstaben-plus-Zahlen-Pattern stabil
    erkannt werden — inklusive Varianten mit Bindestrich, Leerzeichen
    oder direktem Kontakt zwischen Alpha und Digit.

    Erwartetes Verhalten: der Rueckgabe-Dict enthaelt type, dimension
    und raw passend zum Input.

    Wenn dieser Test nach einer Aenderung ROT wird, greift der
    Extraktor einen bisher funktionierenden Input nicht mehr — das
    waere eine Regression fuer die Kemmler- und Hornbach-Katalog-
    Abdeckung.
    """
    result = extract_product_code(name)
    assert result is not None, f"Kein Code extrahiert aus {name!r}"
    assert result["type"] == expected_type
    assert result["dimension"] == expected_dim
    assert result["raw"] == expected_raw


def test_extract_erstes_vorkommen_gewinnt():
    """Bei mehreren Codes im Namen gewinnt das erste Vorkommen.

    Zweck: stellt sicher, dass die Reihenfolge deterministisch ist.
    ``TP75 Türpfosten-Steckwinkel f. 75 mm CW/UA-Prof`` enthaelt sowohl
    ``TP75`` als auch ``CW`` (ohne Dimension) — der Extraktor darf nur
    ``TP75`` zurueckgeben.

    Erwartetes Verhalten: result["raw"] == "TP75".

    Wenn dieser Test ROT wird, springt der Extraktor nach hinten oder
    priorisiert Codes anders — das wuerde die Matcher-Strategie fuer
    Phase 2 unterwandern.
    """
    result = extract_product_code(
        "TP75 Türpfosten-Steckwinkel f. 75 mm CW/UA-Prof mit Kabeldurchlas"
    )
    assert result is not None
    assert result["raw"] == "TP75"


# --------------------------------------------------------------------------- #
# Guard-Tests — bewusst KEIN Match
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name",
    [
        "cw75",  # lowercase → verboten
        "",  # leer
        None,  # None
        "30",  # nur Ziffern
        "CW",  # nur Buchstaben, keine Zahl
        "Baumit Multicontact 25 kg/Sack",  # freier Produktname ohne Code
        "DIAMANTI1000",  # 8 Grossbuchstaben vor der Zahl
        "W3.0",  # Dezimalzahl, zu kurzer Alpha-Teil
    ],
)
def test_extract_guard_kein_match(name):
    """Eingaben ohne passendes Code-Pattern liefern None.

    Zweck: verhindert False-Positives. Lowercase-Codes, leere Strings,
    reine Zahlen, reine Buchstaben und freie Produktnamen ohne
    [A-Z]{2,3}\\d+-Pattern duerfen keinen Code zurueckliefern.

    Erwartetes Verhalten: Rueckgabe ist None.

    Wenn dieser Test ROT wird, produziert der Extraktor Schrott-
    Strukturen, die der Matcher morgen fälschlich als Typ-Code
    interpretieren koennte.
    """
    assert extract_product_code(name) is None


def test_extract_cw_profil_bleibt_bewusst_ohne_code():
    """**Design-Entscheidung:** Kemmler-Strings wie
    ``CW-Profil 100x50x0,6 mm BL=2600 mm`` tragen **keinen** Produkt-
    Code im strukturellen Sinn — der Typ (CW) und die Dimension (100)
    sind durch das Wort ``Profil`` voneinander getrennt.

    Die strenge Regex ``[A-Z]{2,3}\\d+`` (mit Toleranz fuer maximal
    einen Bindestrich oder ein Leerzeichen zwischen Alpha und Digit)
    matcht diesen Fall bewusst NICHT. Matcher-Strategie fuer diese
    Eintraege: Fuzzy-Fallback (klassischer Pfad aus B+4.2.6) — siehe
    Option A in ``docs/b426_optionC_phase1_baseline.md``.

    Wenn dieser Test ROT wird (also doch ein Code extrahiert wird),
    ist die Regex unerwartet aufgeweicht worden. Das kann zu False-
    Positives bei Produktnamen mit Typ-Praefix + freiem Text + Zahl
    fuehren und sollte begruendet werden.
    """
    result = extract_product_code("CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.")
    assert result is None


# --------------------------------------------------------------------------- #
# Integration — Parser-Flow ohne LLM
# --------------------------------------------------------------------------- #
def test_parser_flow_setzt_attributes_fields_bei_code(tmp_path):
    """Integration: das _build_entry ruft extract_product_code und
    setzt die Felder in attributes, wenn der Produktname einen Code
    enthaelt.

    Wir testen nicht den vollen Worker-Flow (das braucht Claude), nur
    die Post-Processor-Integration im _build_entry. Dazu bauen wir ein
    minimales Pricelist + Raw-Dict, rufen den Parser-Internal-Schritt
    auf und pruefen die Entry-Attribute.
    """
    from unittest.mock import MagicMock

    from app.models.pricing import SupplierPriceList
    from app.services.pricelist_parser import PricelistParser

    pl = SupplierPriceList(
        id="pl-test",
        tenant_id="t-test",
        supplier_name="Kemmler",
        list_name="Test",
        source_file_path="/tmp/test.pdf",
        source_file_hash="h",
    )
    parser = PricelistParser(db=MagicMock(), claude_client=MagicMock())
    entry = parser._build_entry(
        pl,
        {
            "product_name": "Kemmler KKZ30 Kalkzementputz 30 kg/Sack",
            "unit": "€/Sack",
            "price_net": 7.86,
        },
    )
    assert entry.attributes.get("product_code_type") == "KKZ"
    assert entry.attributes.get("product_code_dimension") == "30"
    assert entry.attributes.get("product_code_raw") == "KKZ30"


def test_parser_flow_laesst_attributes_leer_wenn_kein_code():
    """Integration: wenn der Produktname keinen Code traegt, bleiben
    die product_code_*-Keys **NICHT gesetzt** — der attributes-Dict
    wird NICHT mit None-Werten verschmutzt.
    """
    from unittest.mock import MagicMock

    from app.models.pricing import SupplierPriceList
    from app.services.pricelist_parser import PricelistParser

    pl = SupplierPriceList(
        id="pl-test",
        tenant_id="t-test",
        supplier_name="Baumit",
        list_name="Test",
        source_file_path="/tmp/test.pdf",
        source_file_hash="h",
    )
    parser = PricelistParser(db=MagicMock(), claude_client=MagicMock())
    entry = parser._build_entry(
        pl,
        {
            # Bewusst OHNE [A-Z]{2,3}\\d+-Pattern im Namen — der Parser
            # darf die product_code_*-Keys nicht spuken.
            "product_name": "Baumit Haftmörtel 25 kg/Sack",
            "unit": "€/Sack",
            "price_net": 23.70,
        },
    )
    assert "product_code_type" not in entry.attributes
    assert "product_code_dimension" not in entry.attributes
    assert "product_code_raw" not in entry.attributes
