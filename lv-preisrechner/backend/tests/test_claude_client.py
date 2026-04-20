"""Unit-Tests fuer app/services/claude_client.py — Helpers.

Live-Calls gegen Anthropic werden NICHT getestet. Fokus auf den robusten
JSON-Fallback-Pfad, der im Live-Test B+2 an Kemmler gescheitert war
(Claude liefert mehrere JSON-Objekte statt einem).
"""

from __future__ import annotations

from app.services.claude_client import (
    _try_parse_concatenated_json,
    _recover_truncated_array,
)


# ---------------------------------------------------------------------------
# _try_parse_concatenated_json
# ---------------------------------------------------------------------------

def test_concat_json_zwei_objekte_werden_gemergt():
    raw = (
        '{"page": 1, "entries": [{"product_name": "A"}]}\n'
        '{"page": 2, "entries": [{"product_name": "B"}]}'
    )
    result = _try_parse_concatenated_json(raw)
    assert result is not None
    assert len(result) == 2
    assert result[0]["page"] == 1
    assert result[1]["page"] == 2
    assert result[0]["entries"][0]["product_name"] == "A"
    assert result[1]["entries"][0]["product_name"] == "B"


def test_concat_json_ohne_whitespace_separator():
    # Claude gibt manchmal gar kein \n zwischen Objekten
    raw = '{"page":1,"entries":[]}{"page":2,"entries":[]}'
    result = _try_parse_concatenated_json(raw)
    assert result is not None
    assert len(result) == 2


def test_concat_json_mit_trailing_whitespace_ok():
    raw = '{"page": 1, "entries": []}  \n  {"page": 2, "entries": []}   '
    result = _try_parse_concatenated_json(raw)
    assert result is not None
    assert len(result) == 2


def test_concat_json_einzelnes_objekt_gibt_none():
    # Nur EIN Objekt — kein Concat-Fall, Helper soll None geben
    raw = '{"page": 1, "entries": [{"product_name": "A"}]}'
    assert _try_parse_concatenated_json(raw) is None


def test_concat_json_array_wird_abgelehnt():
    # Top-Level-Array ist kein dict → None
    raw = '[1, 2, 3]'
    assert _try_parse_concatenated_json(raw) is None


def test_concat_json_komplett_kaputt_gibt_none():
    raw = "das ist kein json"
    assert _try_parse_concatenated_json(raw) is None


def test_concat_json_drei_objekte():
    raw = (
        '{"page":1,"entries":[{"product_name":"X"}]}'
        '{"page":2,"entries":[{"product_name":"Y"}]}'
        '{"page":3,"entries":[{"product_name":"Z"}]}'
    )
    result = _try_parse_concatenated_json(raw)
    assert result is not None
    assert len(result) == 3
    assert [o["entries"][0]["product_name"] for o in result] == ["X", "Y", "Z"]


def test_concat_json_mit_abgebrochenem_zweitobjekt():
    # Zweites Objekt ist abgeschnitten — das erste gueltige + Break erwartet;
    # da nur 1 vollstaendiges Objekt uebrig bleibt, Helper gibt None (kein Concat).
    raw = '{"page":1,"entries":[]}{"page":2,"entries":[{"product_na'
    result = _try_parse_concatenated_json(raw)
    assert result is None


# ---------------------------------------------------------------------------
# _recover_truncated_array — bestehende Funktion, Regression-Check
# ---------------------------------------------------------------------------

def test_recover_truncated_array_rettet_vollstaendige_eintraege():
    raw = (
        '{"eintraege": [{"a": 1}, {"b": 2}, {"c":'  # abgeschnitten
    )
    recovered = _recover_truncated_array(raw, "eintraege")
    assert recovered is not None
    assert len(recovered["eintraege"]) == 2


def test_recover_truncated_array_gibt_none_wenn_key_fehlt():
    raw = '{"anderer_key": []}'
    assert _recover_truncated_array(raw, "eintraege") is None
