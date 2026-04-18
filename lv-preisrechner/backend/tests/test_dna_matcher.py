"""Tests für DNA-Matcher: scoring + best-match."""

from app.services.dna_matcher import _parse_pattern, _score_entry
from app.models.price_entry import PriceEntry


def _entry(**kwargs) -> PriceEntry:
    return PriceEntry(
        id="x",
        price_list_id="pl",
        hersteller=kwargs.get("hersteller", ""),
        kategorie=kwargs.get("kategorie", ""),
        produktname=kwargs.get("produktname", ""),
        abmessungen=kwargs.get("abmessungen", ""),
        variante=kwargs.get("variante", ""),
        dna="",
        preis=1.0,
        einheit="€/m²",
        preis_pro_basis=1.0,
        basis_einheit="m²",
        konfidenz=1.0,
    )


def test_exakter_match_gibt_hohen_score():
    e = _entry(hersteller="Knauf", kategorie="Gipskarton", produktname="GKB", abmessungen="12.5mm")
    score = _score_entry(e, _parse_pattern("Knauf|Gipskarton|GKB|12.5mm|"))
    assert score > 0.9


def test_kategorie_mismatch_gibt_tiefen_score():
    e = _entry(hersteller="Knauf", kategorie="Daemmung", produktname="Thermolan")
    score = _score_entry(e, _parse_pattern("Knauf|Gipskarton|GKB|12.5mm|"))
    assert score < 0.5


def test_hersteller_offen_matcht_alle():
    e = _entry(hersteller="Siniat", kategorie="Gipskarton", produktname="GKB", abmessungen="12.5mm")
    # Pattern ohne Hersteller
    score = _score_entry(e, _parse_pattern("|Gipskarton|GKB|12.5mm|"))
    assert score > 0.7


def test_parse_pattern():
    p = _parse_pattern("Knauf|Gipskarton|GKB|12.5mm|")
    assert p["hersteller"] == "Knauf"
    assert p["kategorie"] == "Gipskarton"
    assert p["produktname"] == "GKB"
    assert p["abmessungen"] == "12.5mm"
    assert p["variante"] == ""
