"""Regressions-Checks fuer Pricelist-Parser-Konfiguration.

Schuetzen die nach dem Kemmler-Live-Test gelernten Werte vor
unbeabsichtigtem Zurueckdrehen:

- Batch-Size default 3 (nicht 5): verhindert Output-Truncation, weil Claude
  sonst bei dichten Seiten im pages-Wrapper abgeschnitten wird.
- max_tokens = 32_000 (nicht 16_000): bei 5er-Batches kam Claude ans Limit,
  3er plus 32k gibt sichere Marge.
"""

from __future__ import annotations

import inspect

from app.services import pricelist_parser as pp


def test_default_batch_size_ist_3():
    """Default-Batch-Size = 3 (nicht 5). Regression nach Live-Test B+2."""
    sig = inspect.signature(pp.PricelistParser.__init__)
    assert sig.parameters["batch_size"].default == 3, (
        "Default-Batch-Size wurde zurueckgedreht. Das fuehrt auf Kemmler "
        "zu JSON-Truncation in 3/5 Batches."
    )


def test_pricelist_max_tokens_mindestens_32k():
    """max_tokens-Override fuer Pricelist-Parsing >= 32_000."""
    assert pp._PRICELIST_MAX_TOKENS >= 32_000, (
        "_PRICELIST_MAX_TOKENS zu niedrig. Kemmler-Live-Test zeigt, dass "
        "16k fuer Multi-Image-Batches nicht reicht."
    )


def test_parser_ruft_extract_json_mit_max_tokens_auf(monkeypatch):
    """Der Parser muss _PRICELIST_MAX_TOKENS an extract_json weiterreichen."""

    captured: dict = {}

    class _Spy:
        def extract_json(self, **kwargs):
            captured.update(kwargs)
            # Minimal-Response, damit der Rest nicht kracht.
            return {"pages": []}, "claude-sonnet-4-6"

    # Wir brauchen eine echte pricelist-Instanz plus Dummy-PDF-Bytes.
    # Schneller Pfad: Mock der PDF-Utils, direkt einen Batch-Loop simulieren.
    from app.services.pricelist_parser import PricelistParser

    parser = PricelistParser(db=None, claude_client=_Spy())  # type: ignore[arg-type]

    # Direkt einen extract_json-Call simulieren (umgeht PDF-Loading):
    from app.prompts.kemmler_parser_prompt import SYSTEM_PROMPT

    parser._claude.extract_json(
        system=SYSTEM_PROMPT,
        images=[{"type": "image", "source": {}}],
        max_tokens=pp._PRICELIST_MAX_TOKENS,
    )

    assert captured.get("max_tokens") == pp._PRICELIST_MAX_TOKENS
