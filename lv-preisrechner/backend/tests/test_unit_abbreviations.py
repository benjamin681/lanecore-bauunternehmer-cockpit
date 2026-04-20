"""Tests fuer die Abkuerzungs-Expansion im Unit-Normalizer.

Nach dem Kemmler-v2-Live-Run haben 7+ Sack-Produkte mit Abkuerzung wie
"20 kg/S." oder "25 kg/Sa." needs_review ausgeloest (confidence 0.30),
obwohl der Preis eindeutig extrahierbar war. Dieser Fix expandiert
bekannte Abkuerzungen vor dem Regel-Pfad.

Die Strings hier sind 1:1 aus dem v2-Live-Report uebernommen
(live_db/report_1776692597.json), damit der Fix gegen echte Daten
validiert wird ohne neuen Full-Run.
"""

from __future__ import annotations

from app.services.pricelist_parser import (
    _expand_unit_abbreviations,
    _normalize_unit,
)


# ---------------------------------------------------------------------------
# _expand_unit_abbreviations Helper
# ---------------------------------------------------------------------------

def test_expand_sa_punkt():
    assert _expand_unit_abbreviations("25 kg/Sa.") == "25 kg/Sack"
    assert _expand_unit_abbreviations("€/Sa.") == "€/Sack"


def test_expand_s_punkt():
    assert _expand_unit_abbreviations("20 kg/S.") == "20 kg/Sack"


def test_expand_rol_mit_und_ohne_punkt():
    assert _expand_unit_abbreviations("25 m/Rol.") == "25 m/Rolle"
    assert _expand_unit_abbreviations("25 m/Rol") == "25 m/Rolle"


def test_expand_pak_punkt():
    assert _expand_unit_abbreviations("10 Stk/Pak.") == "10 Stk/Paket"


def test_expand_ktn_punkt():
    assert _expand_unit_abbreviations("100 Stk/Ktn.") == "100 Stk/Karton"


def test_expand_eim_punkt():
    assert _expand_unit_abbreviations("12,5 l/Eim.") == "12,5 l/Eimer"


def test_expand_geb_punkt():
    assert _expand_unit_abbreviations("25 l/Geb.") == "25 l/Gebinde"


def test_expand_bd_punkt():
    assert _expand_unit_abbreviations("8 St/Bd.") == "8 St/Bund"


def test_expand_mehrere_in_einem_string():
    # Produktname mit Abkuerzung + Unit mit Abkuerzung
    result = _expand_unit_abbreviations(
        "Knauf LUSTRO Mortel 20 kg/S., 24 Stk/Pak."
    )
    assert "20 kg/Sack" in result
    assert "24 Stk/Paket" in result


def test_expand_laesst_unbekannte_abkuerzung_stehen():
    # /P. ist als mehrdeutig NICHT in der Tabelle
    assert _expand_unit_abbreviations("10 kg/P.") == "10 kg/P."
    # /B. ebenfalls
    assert _expand_unit_abbreviations("5 St/B.") == "5 St/B."


def test_expand_nicht_mitten_im_wort():
    # "S.1" (Seite 1 o.ae.) darf NICHT zu "Sack1" werden
    # — die Wortgrenze rechts verhindert das.
    assert _expand_unit_abbreviations("Siehe S.1") == "Siehe S.1"


def test_expand_leer_und_none_safe():
    assert _expand_unit_abbreviations("") == ""
    # None-Input wird via "if not text" abgefangen
    assert _expand_unit_abbreviations(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# End-to-End im Normalizer: die v2-Low-Confidence-Faelle
# ---------------------------------------------------------------------------

def test_abbreviation_normalization_sack_sa_suffix():
    """Knauf SM700PRO-Fall aus v2-Report: 25 kg/Sa. + €/Sack."""
    info = _normalize_unit(
        "€/Sack",
        product_name="Knauf SM700PRO WEISS Klebe-/Armier- u. Renoviermoertel, 25 kg/Sa.",
        price=24.97,
    )
    assert info.effective_unit == "kg"
    assert info.package_size == 25.0
    assert info.package_unit == "kg"
    assert abs(info.price_per_effective_unit - (24.97 / 25)) < 0.001
    assert info.confidence >= 0.9, (
        "Nach Fix sollte /Sa. expandiert und R1 getriggert werden → conf >= 0.9"
    )
    assert info.needs_review is False


def test_abbreviation_normalization_sack_s_suffix():
    """Knauf LUSTRO-Fall aus v2-Report: 20 kg/S. + €/Sack."""
    info = _normalize_unit(
        "€/Sack",
        product_name="Knauf LUSTRO faserarmierter Klebe-/Armiermoertel, 20 kg/S.",
        price=20.76,
    )
    assert info.effective_unit == "kg"
    assert info.package_size == 20.0
    assert abs(info.price_per_effective_unit - (20.76 / 20)) < 0.001
    assert info.confidence >= 0.9
    assert info.needs_review is False


def test_abbreviation_normalization_baumit_fascina():
    """BaumitB. Fascina SEP03-Fall aus v2-Report: 25 kg/Sa."""
    info = _normalize_unit(
        "€/Sack",
        product_name="BaumitB. Fascina SEP03 - weiss Mineralischer Edelputz, 3 mm - 25 kg/Sa.",
        price=20.10,
    )
    assert info.effective_unit == "kg"
    assert abs(info.price_per_effective_unit - 0.804) < 0.001
    assert info.confidence >= 0.9


def test_abbreviation_mehrdeutig_bleibt_review():
    """/P. ist mehrdeutig und darf nicht auto-expandiert werden.

    Die Einheit bleibt unklar, und der Eintrag soll needs_review behalten.
    """
    info = _normalize_unit(
        "€/P.",
        product_name="Artikel mit 10 kg/P.",
        price=15.00,
    )
    # Fallback-Pfad: confidence 0.3, needs_review=True
    assert info.needs_review is True
    assert info.confidence < 0.7


def test_abbreviation_bestehende_regeln_bleiben_unbeeinflusst():
    """Regression: klare Platten-m² weiter mit conf 1.0."""
    info = _normalize_unit(
        "€/m²",
        product_name="Knauf Bauplatte GKB 2000x1250x12,5mm",
        price=3.00,
    )
    assert info.effective_unit == "m²"
    assert info.confidence == 1.0


def test_abbreviation_regel2_bundpreis_unveraendert():
    """Regression: CW-Profil Bundpreis-Falle bleibt needs_review."""
    info = _normalize_unit(
        "€/m",
        product_name="CW-Profil 50x50 BL=2600 mm - 8 St./Bd.",
        price=112.80,
    )
    assert info.needs_review is True
    # Nach Expansion von "/Bd." zu "/Bund" sollte die Bundpreis-Falle weiter greifen
    assert info.pieces_per_package == 8
