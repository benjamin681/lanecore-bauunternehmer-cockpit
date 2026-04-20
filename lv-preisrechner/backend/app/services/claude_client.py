"""Gemeinsamer Anthropic-Client mit Sonnet-Primary + Opus-Fallback bei niedriger Konfidenz."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import structlog
from anthropic import Anthropic, APIStatusError

from app.core.config import settings

log = structlog.get_logger()


def _try_parse_concatenated_json(raw: str) -> list[dict[str, Any]] | None:
    """Parst mehrere JSON-Objekte, die direkt hintereinander stehen.

    Claude liefert bei Multi-Image-Prompts gelegentlich ein Objekt pro Bild
    statt ein gemeinsames Wrapper-Objekt, z.B.:

        {"page": 3, "entries": [...]}
        {"page": 4, "entries": [...]}

    `json.loads()` bricht hier mit "Extra data" ab. Dieser Helper nutzt
    `raw_decode()` in einer Schleife, um alle Top-Level-Objekte sequentiell
    einzulesen. Gibt die Liste der Objekte zurueck oder None, wenn schon das
    erste Objekt nicht geparst werden kann (dann kein Concat-Fall).
    """
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    idx = 0
    text = raw.strip()
    n = len(text)
    while idx < n:
        # Fuehrende Whitespaces/Newlines ueberspringen
        while idx < n and text[idx] in " \t\n\r":
            idx += 1
        if idx >= n:
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            # Konnten nichts (mehr) dekodieren
            break
        if not isinstance(obj, dict):
            # Nur Objekte akzeptieren (keine Arrays/Primitives)
            return None
        objects.append(obj)
        idx = end
    if len(objects) < 2:
        # Ein Objekt allein ist kein Concat-Fall — hier nichts gewonnen.
        return None
    return objects


def _recover_truncated_array(raw: str, array_key: str) -> dict[str, Any] | None:
    """Rettet Einträge aus abgeschnittenem JSON mit Top-Level-Array.

    Strategie: finde letzte vollständige Objekt-Klammer im Array, schließe künstlich.
    """
    # Finde Position von "<array_key>": [
    m = re.search(rf'"{array_key}"\s*:\s*\[', raw)
    if not m:
        return None
    start = m.end()
    # Walk: zähle Klammern, notiere Positionen nach jedem Objekt-Ende auf Top-Level (depth == 1)
    depth = 1  # wir sind bereits im Array
    in_str = False
    escape = False
    last_good_end = -1
    i = start
    while i < len(raw):
        c = raw[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{" or c == "[":
                depth += 1
            elif c == "}" or c == "]":
                depth -= 1
                if depth == 1 and c == "}":
                    # Vollständiges Objekt im Array abgeschlossen
                    last_good_end = i
                if depth == 0:
                    # Array komplett — normaler JSON-Parse sollte ohnehin klappen
                    last_good_end = i
                    break
        i += 1
    if last_good_end < 0:
        return None
    recovered = raw[: last_good_end + 1] + "]}"
    try:
        return json.loads(recovered)
    except json.JSONDecodeError:
        return None


class ClaudeClient:
    """Wrapper um Anthropic-SDK mit Modell-Fallback-Logik."""

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            log.warning("anthropic_api_key_not_set")
        # 10-Min-Timeout pro Call (Vision kann langsam sein)
        self._client = Anthropic(
            api_key=settings.anthropic_api_key or "sk-dummy",
            timeout=600.0,
        )

    def extract_json(
        self,
        *,
        system: str,
        user_text: str | None = None,
        images: list[dict] | None = None,
        force_fallback: bool = False,
    ) -> tuple[dict[str, Any], str]:
        """
        Schickt den Prompt an Claude, erwartet JSON im Response.

        Args:
            system: System-Prompt
            user_text: User-Text (optional)
            images: Liste Claude-kompatibler Image-Blöcke (base64 oder url)
            force_fallback: Nutze direkt Opus statt Sonnet

        Returns:
            (parsed_json, model_used)
        """
        model = (
            settings.claude_model_fallback if force_fallback else settings.claude_model_primary
        )

        content_blocks: list[dict] = []
        if images:
            content_blocks.extend(images)
        if user_text:
            content_blocks.append({"type": "text", "text": user_text})
        if not content_blocks:
            content_blocks = [{"type": "text", "text": "Bitte antworte mit JSON."}]

        # Retry bei 429/529 (Rate-Limit, Overloaded) mit exponential backoff
        last_err = None
        for attempt in range(3):
            try:
                msg = self._client.messages.create(
                    model=model,
                    max_tokens=settings.claude_max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": content_blocks}],
                )
                break
            except APIStatusError as exc:
                last_err = exc
                if exc.status_code in (429, 529, 503) and attempt < 2:
                    backoff = 2 ** attempt * 5  # 5s, 10s
                    log.warning(
                        "claude_retry",
                        attempt=attempt + 1,
                        status=exc.status_code,
                        backoff_s=backoff,
                    )
                    time.sleep(backoff)
                    continue
                log.error("claude_request_failed", model=model, status=exc.status_code, error=str(exc))
                raise
            except Exception as exc:
                log.error("claude_request_failed", model=model, error=str(exc))
                raise
        else:
            raise last_err if last_err else RuntimeError("claude retry exhausted")

        # Claude gibt JSON im Text zurück
        text_blocks = [b.text for b in msg.content if b.type == "text"]
        raw = "\n".join(text_blocks).strip()

        # Robustes JSON-Parsing: Code-Fence entfernen
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        # Leere Antwort? → bei Sonnet: 1x mit Opus retry. Sonst: leere Struktur.
        if not raw:
            stop_reason = getattr(msg, "stop_reason", "unknown")
            log.warning("claude_empty_response", model=model, stop_reason=stop_reason)
            if not force_fallback:
                log.info("claude_retry_with_opus")
                return self.extract_json(
                    system=system,
                    user_text=user_text,
                    images=images,
                    force_fallback=True,
                )
            # Auch Opus leer → leere Antwort zurückgeben (Batch wird geskippt, Job läuft weiter)
            return {"eintraege": [], "positionen": []}, model

        try:
            return json.loads(raw), model
        except json.JSONDecodeError as exc:
            # Fallback 1: Claude gab mehrere Top-Level-JSON-Objekte hintereinander
            # (typisch bei Multi-Image-Prompts — ein Objekt pro Bild). Sammel sie
            # als Liste und gib sie zurueck. Aufrufer muss list[dict] tolerieren.
            concat = _try_parse_concatenated_json(raw)
            if concat is not None:
                log.warning(
                    "claude_json_concat_recovered",
                    count=len(concat),
                    original_error=str(exc),
                )
                return concat, model  # type: ignore[return-value]
            # Fallback 2: truncated Top-Level-Array retten
            for key in ("eintraege", "positionen"):
                recovered = _recover_truncated_array(raw, key)
                if recovered is not None:
                    log.warning(
                        "claude_json_recovered",
                        key=key,
                        count=len(recovered.get(key, [])),
                        original_error=str(exc),
                    )
                    return recovered, model
            log.error("claude_json_parse_failed", error=str(exc), raw=raw[:500])
            raise ValueError(f"Claude gab kein gültiges JSON: {exc}") from exc


claude = ClaudeClient()
