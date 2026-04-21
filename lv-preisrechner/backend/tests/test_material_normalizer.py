"""Tests fuer material_normalizer (B+4.2.5).

Ziel: Reale Kemmler-Produktnamen und LV-DNA-Pattern so normalisieren,
dass rapidfuzz.token_set_ratio >= 85 trifft — ohne False-Positives
zwischen verschiedenen Produkt-Familien (GK vs. Profil vs. Putz).

Fixtures liegen in tests/fixtures/kemmler_real_names.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures" / "kemmler_real_names.json"


def _load_fixtures():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data["positives"], data["negatives"]


# ---------------------------------------------------------------------------
# Reine Normalisierung (deterministisch, ohne Fuzzy)
# ---------------------------------------------------------------------------
def test_normalize_product_name_strips_article_number():
    from app.services.material_normalizer import normalize_product_name
    out = normalize_product_name("Anschlusswinkel f. UA-Profil 48 mm - Nr. 00708449")
    assert "00708449" not in out
    assert "nr" not in out.split()


def test_normalize_product_name_lowercases_and_collapses_whitespace():
    from app.services.material_normalizer import normalize_product_name
    out = normalize_product_name("Knauf   DIAMANT   Hartgipspl.\tGKFI")
    assert out == out.lower()
    assert "  " not in out


def test_normalize_removes_parentheses_content_hrak():
    """'(HRAK)', '(HRK)' sind Kemmler-Technik-Klammern und duerfen das
    Matching nicht stoeren — sie werden entfernt oder in eigene Tokens
    aufgeloest."""
    from app.services.material_normalizer import normalize_product_name
    out = normalize_product_name("SINIAT Massivbaupl. (HRAK) 2000x625x20 mm - (LaMassiv - GKF)")
    # Sowohl "gkf" als auch "20" muessen als Token bleiben
    tokens = set(out.split())
    assert "gkf" in tokens
    assert "20" in tokens
    # Das Herstellerlabel "siniat" muss ueberleben
    assert "siniat" in tokens


def test_normalize_keeps_digits_after_unit_strip():
    """'12,5 mm' / '12.5mm' / '12,5 MM' werden alle zu '12.5'."""
    from app.services.material_normalizer import normalize_product_name
    a = normalize_product_name("Platte 12,5 mm")
    b = normalize_product_name("Platte 12.5mm")
    c = normalize_product_name("PLATTE 12,5 MM")
    assert "12.5" in a.split()
    assert "12.5" in b.split()
    assert "12.5" in c.split()


def test_normalize_package_units_to_kg_token():
    """'30 kg/Sack' soll in beiden Seiten identisch erscheinen — entweder
    als '30kg' kombiniert oder als '30' + 'kg' getrennt. Der Normalizer
    wendet die gleiche Regel auf Produktname und DNA-Pattern an, d. h.
    Prod- und Pattern-Token muessen gleich normalisiert sein."""
    from app.services.material_normalizer import normalize_product_name, normalize_dna_pattern
    prod = normalize_product_name("Knauf Goldband neu 30 kg/Sack")
    pat = normalize_dna_pattern("Knauf|Gips-Grundputz|Goldband|30kg|")
    prod_tokens = set(prod.split())
    pat_tokens = set(pat.split())
    # Hersteller + Produkt-Kern muessen in beiden vorkommen
    assert "knauf" in prod_tokens
    assert "knauf" in pat_tokens
    assert "goldband" in prod_tokens
    assert "goldband" in pat_tokens
    # Das Paketgewicht muss in IDENTISCHER Form in beiden Tokenlisten sein
    assert "30kg" in prod_tokens, f"30kg expected in prod tokens: {prod_tokens}"
    assert "30kg" in pat_tokens, f"30kg expected in pat tokens: {pat_tokens}"


def test_normalize_dna_pattern_splits_pipes_and_drops_category():
    """Design-Entscheidung: Kategorie (Slot 1) wird verworfen, weil sie
    in realen Produktnamen nicht vorkommt. Hersteller (Slot 0) bleibt."""
    from app.services.material_normalizer import normalize_dna_pattern
    out = normalize_dna_pattern("Knauf|Gipskarton|GKFI|12.5|")
    tokens = set(out.split())
    assert "knauf" in tokens
    assert "gkfi" in tokens
    assert "12.5" in tokens
    assert "gipskarton" not in tokens, "Kategorie muss entfernt sein"


def test_normalize_dna_pattern_empty_manufacturer_ok():
    """Hersteller leer darf nicht in leere Normalisierung muenden."""
    from app.services.material_normalizer import normalize_dna_pattern
    out = normalize_dna_pattern("|Trockenbauprofile|CW|100|")
    tokens = set(out.split())
    assert "cw" in tokens
    assert "100" in tokens


def test_normalize_fl_asche_quirk():
    """Kemmler-Eigenart 'Fl.asche' — der Punkt darf nicht die Tokenisierung
    sabotieren. '800 g/Fl.asche' wird zu '800g' (Gramm-Packung kondensiert)
    und die Artikelnummer verschwindet. Das ist gewollt: DNA-Pattern
    fuehrt das Paketgewicht als '800g'."""
    from app.services.material_normalizer import normalize_product_name
    out = normalize_product_name("Knauf Brio Falzkleber - 800 g/Fl.asche Nr. 00088533")
    tokens = out.split()
    # Gewicht in kondensierter Form
    assert "800g" in tokens, f"800g expected in {tokens}"
    # Artikelnummer weg
    assert "00088533" not in out


# ---------------------------------------------------------------------------
# Fuzzy-Hilfsfunktion: kombiniert Normalizer + rapidfuzz
# ---------------------------------------------------------------------------
def _score(product: str, pattern: str) -> float:
    """Hilfs-Score fuer die Tests: normalisiert beide Seiten und liefert
    rapidfuzz.token_set_ratio in [0, 100].
    """
    from app.services.material_normalizer import (
        normalize_dna_pattern,
        normalize_product_name,
        fuzzy_match_score,
    )
    return fuzzy_match_score(
        product_name=product,
        dna_pattern=pattern,
    )


# ---------------------------------------------------------------------------
# Parametrisierte Fixture-Tests (positive)
# ---------------------------------------------------------------------------
_positives, _negatives = _load_fixtures()


@pytest.mark.parametrize("fixture", _positives, ids=[f["id"] for f in _positives])
def test_fixture_positive_matches_above_threshold(fixture):
    """Jede positive Fixture: Score >= 85 mit Normalizer+rapidfuzz."""
    score = _score(fixture["product_name"], fixture["dna_pattern"])
    assert score >= 85, (
        f"Positive fixture '{fixture['id']}' scored {score} (<85). "
        f"product='{fixture['product_name']}' pattern='{fixture['dna_pattern']}' "
        f"note='{fixture.get('note','')}'"
    )


@pytest.mark.parametrize("fixture", _negatives, ids=[f["id"] for f in _negatives])
def test_fixture_negative_below_threshold(fixture):
    """Jede negative Fixture: Score < 85 (kein False-Positive)."""
    score = _score(fixture["product_name"], fixture["dna_pattern"])
    assert score < 85, (
        f"Negative fixture '{fixture['id']}' falsely scored {score} (>=85). "
        f"product='{fixture['product_name']}' pattern='{fixture['dna_pattern']}' "
        f"note='{fixture.get('note','')}'"
    )


# ---------------------------------------------------------------------------
# Aggregated stat: Positive-Match-Rate muss >= 85% sein
# ---------------------------------------------------------------------------
def test_aggregated_match_rate_above_85_percent():
    """Acceptance Criterion: >=85% der positiven Fixtures matchen."""
    scores = [_score(f["product_name"], f["dna_pattern"]) for f in _positives]
    hits = sum(1 for s in scores if s >= 85)
    rate = hits / len(scores)
    assert rate >= 0.85, (
        f"Positive match rate {rate:.0%} ({hits}/{len(scores)}) < 85%. "
        f"Scores: {list(zip([f['id'] for f in _positives], scores))}"
    )
