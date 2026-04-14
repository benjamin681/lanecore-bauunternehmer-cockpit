"""Tests for analysis pipeline and JSON extraction."""

import pytest
from app.services.bauplan_service import BauplanAnalyseService
from app.services.analyse_pipeline import _merge_page_results


# --- JSON Extraction Tests ---


class TestJsonExtraction:
    """Tests for _extract_json static method."""

    def test_direct_json(self):
        """Direct JSON string should parse."""
        result = BauplanAnalyseService._extract_json('{"konfidenz": 0.95, "raeume": []}')
        assert result["konfidenz"] == 0.95

    def test_json_in_code_block(self):
        """JSON wrapped in markdown code block should parse."""
        text = 'Hier ist das Ergebnis:\n```json\n{"konfidenz": 0.85, "raeume": []}\n```\nFertig.'
        result = BauplanAnalyseService._extract_json(text)
        assert result["konfidenz"] == 0.85

    def test_json_in_code_block_no_lang(self):
        """JSON in code block without language tag should parse."""
        text = '```\n{"konfidenz": 0.9}\n```'
        result = BauplanAnalyseService._extract_json(text)
        assert result["konfidenz"] == 0.9

    def test_json_with_surrounding_text(self):
        """JSON embedded in free text should be found."""
        text = 'Analyse abgeschlossen. {"massstab": "1:100", "raeume": []} Das war die Analyse.'
        result = BauplanAnalyseService._extract_json(text)
        assert result["massstab"] == "1:100"

    def test_no_json_returns_fallback(self):
        """When no JSON found, return fallback with warning."""
        result = BauplanAnalyseService._extract_json("Ich konnte den Plan nicht analysieren.")
        assert result["konfidenz"] == 0.0
        assert len(result["warnungen"]) > 0

    def test_nested_json(self):
        """Deeply nested JSON should parse correctly."""
        text = '{"raeume": [{"bezeichnung": "Büro", "flaeche_m2": 24.5}], "konfidenz": 0.92}'
        result = BauplanAnalyseService._extract_json(text)
        assert len(result["raeume"]) == 1
        assert result["raeume"][0]["flaeche_m2"] == 24.5


# --- Result Merging Tests ---


class TestMergeResults:
    """Tests for _merge_page_results."""

    def test_merge_single_page(self):
        results = [{"plantyp": "grundriss", "massstab": "1:100", "konfidenz": 0.9, "raeume": [{"name": "A"}], "waende": [], "decken": [], "warnungen": []}]
        merged = _merge_page_results(results)
        assert merged["plantyp"] == "grundriss"
        assert merged["konfidenz"] == 0.9
        assert len(merged["raeume"]) == 1

    def test_merge_skipped_pages(self):
        results = [
            {"type": "skipped", "plantyp": "ansicht"},
            {"plantyp": "grundriss", "konfidenz": 0.85, "raeume": [{"name": "B"}], "waende": [], "decken": [], "warnungen": []},
        ]
        merged = _merge_page_results(results)
        assert merged["plantyp"] == "grundriss"
        assert len(merged["raeume"]) == 1

    def test_merge_konfidenz_takes_minimum(self):
        results = [
            {"plantyp": "grundriss", "konfidenz": 0.95, "raeume": [], "waende": [], "decken": [], "warnungen": []},
            {"plantyp": "grundriss", "konfidenz": 0.72, "raeume": [], "waende": [], "decken": [], "warnungen": ["Unsicher"]},
        ]
        merged = _merge_page_results(results)
        assert merged["konfidenz"] == 0.72

    def test_merge_combines_warnings(self):
        results = [
            {"plantyp": "grundriss", "konfidenz": 0.9, "raeume": [], "waende": [], "decken": [], "warnungen": ["W1"]},
            {"plantyp": "grundriss", "konfidenz": 0.9, "raeume": [], "waende": [], "decken": [], "warnungen": ["W2", "W3"]},
        ]
        merged = _merge_page_results(results)
        assert len(merged["warnungen"]) == 3

    def test_merge_empty_list(self):
        merged = _merge_page_results([])
        assert merged["konfidenz"] == 1.0
        assert merged["raeume"] == []


# --- Validation Tests ---


class TestValidation:
    """Tests for _validate_result."""

    def test_low_confidence_adds_warning(self):
        result = {"konfidenz": 0.5, "raeume": [], "waende": [], "decken": [], "warnungen": []}
        validated = BauplanAnalyseService._validate_result(result, "grundriss")
        assert any("Konfidenz" in w for w in validated["warnungen"])

    def test_missing_massstab_adds_warning(self):
        result = {"konfidenz": 0.9, "raeume": [], "waende": [], "decken": [], "warnungen": []}
        validated = BauplanAnalyseService._validate_result(result, "grundriss")
        assert any("Maßstab" in w for w in validated["warnungen"])

    def test_high_confidence_no_extra_warnings(self):
        result = {"konfidenz": 0.95, "massstab": "1:100", "raeume": [], "waende": [], "decken": [], "warnungen": []}
        validated = BauplanAnalyseService._validate_result(result, "grundriss")
        assert len(validated["warnungen"]) == 0

    def test_unrealistic_room_area_warns(self):
        result = {
            "konfidenz": 0.9,
            "massstab": "1:100",
            "raeume": [{"bezeichnung": "Tiny", "flaeche_m2": 0.5}],
            "waende": [],
            "decken": [],
            "warnungen": [],
        }
        validated = BauplanAnalyseService._validate_result(result, "grundriss")
        assert any("unrealistisch klein" in w for w in validated["warnungen"])

    def test_deckenspiegel_entfaellt_noted(self):
        result = {
            "konfidenz": 0.9,
            "massstab": "1:50",
            "raeume": [],
            "waende": [],
            "decken": [],
            "gestrichene_positionen": [{"bezeichnung": "GKb Nassraum", "grund": "entfällt"}],
            "warnungen": [],
        }
        validated = BauplanAnalyseService._validate_result(result, "deckenspiegel")
        assert any("gestrichene" in w for w in validated["warnungen"])
