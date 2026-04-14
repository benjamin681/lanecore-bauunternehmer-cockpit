"""Bauplan-Analyse Service — Orchestriert Claude-API-Calls für PDF-Analyse."""

from pathlib import Path

import anthropic
import structlog

from app.core.config import settings

log = structlog.get_logger()


class BauplanAnalyseService:
    """
    Orchestriert die mehrstufige Bauplan-Analyse:
    1. PDF → Bilder konvertieren (eine Seite pro Analyse)
    2. Schnell-Check: Handelt es sich um einen Grundriss? (Sonnet)
    3. Detail-Analyse: Räume, Wandlängen, Maßketten (Opus)
    4. Validierung: Plausibilitätsprüfung der Ergebnisse
    5. Strukturierung: Ergebnis in Schema überführen
    """

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def analyse_page(self, image_base64: str, page_num: int) -> dict:
        """Analysiert eine einzelne Planseite mit Claude Vision."""
        log.info("analysing_bauplan_page", page=page_num)

        # Schritt 1: Schnell-Check mit Sonnet (ist es ein Grundriss?)
        is_grundriss = await self._check_if_grundriss(image_base64)
        if not is_grundriss:
            log.info("page_not_grundriss_skipping", page=page_num)
            return {"type": "skipped", "reason": "Kein Grundriss erkannt"}

        # Schritt 2: Detail-Analyse mit Opus
        raw_result = await self._detail_analyse(image_base64, page_num)

        # Schritt 3: Validierung
        validated = await self._validate_result(raw_result)

        return validated

    async def _check_if_grundriss(self, image_base64: str) -> bool:
        """Schnell-Check ob die Seite ein Grundriss ist (günstig mit Sonnet)."""
        response = await self.client.messages.create(
            model=settings.claude_model_simple,
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Ist das ein Grundriss (Draufsicht auf ein Gebäude oder Stockwerk)? "
                            "Antworte NUR mit 'ja' oder 'nein'."
                        ),
                    },
                ],
            }],
        )
        answer = response.content[0].text.strip().lower()
        return answer.startswith("ja")

    async def _detail_analyse(self, image_base64: str, page_num: int) -> dict:
        """Detaillierte Bauplan-Analyse mit Opus."""
        # Prompt aus Datei laden (Prompt-Bibliothek)
        prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "bauplan-analyse.md"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        response = await self.client.messages.create(
            model=settings.claude_model_complex,
            max_tokens=4096,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": f"Analysiere diesen Grundriss (Seite {page_num}). Antworte im JSON-Format.",
                    },
                ],
            }],
        )

        # TODO: JSON aus Antwort extrahieren + parsen
        return {"raw": response.content[0].text}

    async def _validate_result(self, result: dict) -> dict:
        """Plausibilitätsprüfung: Stimmen die Summen? Sind Maße realistisch?"""
        # TODO: Sprint 2 — Validierungslogik implementieren
        return result
