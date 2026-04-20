"""Unit-Tests fuer app/services/claude_client.py — Helpers.

Live-Calls gegen Anthropic werden NICHT getestet. Fokus auf den robusten
JSON-Fallback-Pfad, der im Live-Test B+2 an Kemmler gescheitert war
(Claude liefert mehrere JSON-Objekte statt einem).
"""

from __future__ import annotations

from app.services.claude_client import (
    ClaudeClient,
    _try_parse_concatenated_json,
    _recover_truncated_array,
)


# ---------------------------------------------------------------------------
# Fake Anthropic SDK
# ---------------------------------------------------------------------------

class _Block:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Msg:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


class _FakeAnthropic:
    """Minimaler Ersatz fuer den Anthropic-SDK-Client in Tests.

    Nimmt eine Liste von Response-Texten entgegen; bei jedem
    messages.create() wird der naechste aus der Liste zurueckgegeben.
    """

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []
        # Anthropic-SDK: client.messages.create(...)
        self.messages = self

    def create(self, *, model, max_tokens, system, messages):  # noqa: D401
        self.calls.append({"model": model, "max_tokens": max_tokens})
        if not self.responses:
            raise AssertionError("FakeAnthropic: keine Responses mehr uebrig")
        text = self.responses.pop(0)
        return _Msg(text)


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


# ---------------------------------------------------------------------------
# Fix 3: Opus-Fallback bei JSONDecodeError
# ---------------------------------------------------------------------------

def test_opus_fallback_bei_korruptem_json_erfolgreich():
    """Wenn Sonnet korruptes JSON liefert, wird 1x mit Opus retried."""
    from app.core.config import settings

    cc = ClaudeClient()
    # Response 1 (Sonnet): kaputt — weder json.loads, noch concat, noch recover.
    # Response 2 (Opus): valide.
    cc._client = _FakeAnthropic([
        '{"pages": [{"page": 1, "entries": [{"prod',  # echter Truncation-Mid-Objekt
        '{"pages": [{"page": 1, "entries": []}]}',    # Opus liefert korrektes JSON
    ])

    result, model = cc.extract_json(system="sys", user_text="txt")
    assert result == {"pages": [{"page": 1, "entries": []}]}
    assert len(cc._client.calls) == 2, "Erster Call Sonnet, zweiter Call Opus"
    # Zweiter Call MUSS auf dem Fallback-Modell laufen
    assert cc._client.calls[0]["model"] == settings.claude_model_primary
    assert cc._client.calls[1]["model"] == settings.claude_model_fallback


def test_opus_fallback_nur_einmal_bei_doppeltem_fail():
    """Wenn auch Opus kaputtes JSON liefert, wirft ValueError (kein Loop)."""
    cc = ClaudeClient()
    cc._client = _FakeAnthropic([
        '{"broken',   # Sonnet kaputt
        '{"still-broken',  # Opus ebenfalls kaputt
    ])

    import pytest

    with pytest.raises(ValueError, match="Claude gab kein gültiges JSON"):
        cc.extract_json(system="sys")

    # Exakt 2 Calls: 1x Sonnet + 1x Opus (kein dritter Retry-Loop)
    assert len(cc._client.calls) == 2


def test_opus_fallback_nicht_getriggert_wenn_primary_ok():
    """Happy-Path: Sonnet liefert valides JSON, Opus wird nie gerufen."""
    cc = ClaudeClient()
    cc._client = _FakeAnthropic([
        '{"ok": true}',
    ])

    result, _ = cc.extract_json(system="sys")
    assert result == {"ok": True}
    assert len(cc._client.calls) == 1


def test_opus_fallback_nicht_bei_concat_recovery():
    """Concat-JSON greift VOR Opus-Fallback — kein extra Call."""
    cc = ClaudeClient()
    # Sonnet gibt 2 Top-Level-Objekte zurueck (concat-Fall).
    cc._client = _FakeAnthropic([
        '{"page":1,"entries":[]}{"page":2,"entries":[]}',
    ])

    result, _ = cc.extract_json(system="sys")
    # Concat-Recovery liefert eine Liste
    assert isinstance(result, list)
    assert len(result) == 2
    # Nur 1 Call an Anthropic, kein Opus-Fallback
    assert len(cc._client.calls) == 1


def test_opus_fallback_reicht_max_tokens_override_weiter():
    """max_tokens-Override muss auch beim Opus-Retry gelten."""
    cc = ClaudeClient()
    cc._client = _FakeAnthropic([
        '{"kaputt',
        '{"ok": 1}',
    ])
    cc.extract_json(system="sys", max_tokens=32_000)
    # Beide Calls mit 32k
    assert cc._client.calls[0]["max_tokens"] == 32_000
    assert cc._client.calls[1]["max_tokens"] == 32_000
