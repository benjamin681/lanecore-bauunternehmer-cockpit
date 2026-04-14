"""Bauplan-Analyse Service — Orchestriert Claude-API-Calls für PDF-Analyse."""

from pathlib import Path
from typing import Literal

import anthropic
import structlog

from app.core.config import settings

log = structlog.get_logger()

PlanTyp = Literal["grundriss", "deckenspiegel", "schnitt", "detail", "ansicht", "unbekannt"]

# Plantypen die für Trockenbau relevant sind und analysiert werden
RELEVANTE_PLANTYPEN: set[PlanTyp] = {"grundriss", "deckenspiegel", "schnitt", "detail"}


class BauplanAnalyseService:
    """
    Orchestriert die mehrstufige Bauplan-Analyse:
    1. PDF → Bilder konvertieren (eine Seite pro Analyse)
    2. Plantyp-Klassifikation: Grundriss, Deckenspiegel, Schnitt, Detail? (Sonnet)
    3. Detail-Analyse: je nach Plantyp (Opus)
    4. Validierung: Plausibilitätsprüfung der Ergebnisse
    5. Strukturierung: Ergebnis in Schema überführen
    """

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def analyse_page(self, image_base64: str, page_num: int) -> dict:
        """Analysiert eine einzelne Planseite mit Claude Vision."""
        log.info("analysing_bauplan_page", page=page_num)

        # Schritt 1: Plantyp klassifizieren (günstig mit Sonnet)
        plantyp = await self._classify_plantyp(image_base64)
        log.info("plantyp_classified", page=page_num, plantyp=plantyp)

        if plantyp not in RELEVANTE_PLANTYPEN:
            log.info("page_not_relevant_skipping", page=page_num, plantyp=plantyp)
            return {
                "plantyp": plantyp,
                "type": "skipped",
                "reason": f"Plantyp '{plantyp}' nicht relevant für Trockenbau-Kalkulation",
            }

        # Schritt 2: Detail-Analyse mit Opus (plantyp-spezifisch)
        raw_result = await self._detail_analyse(image_base64, page_num, plantyp)

        # Schritt 3: Validierung
        validated = await self._validate_result(raw_result, plantyp)

        return validated

    async def _classify_plantyp(self, image_base64: str) -> PlanTyp:
        """Klassifiziert den Plantyp (günstig mit Sonnet)."""
        response = await self.client.messages.create(
            model=settings.claude_model_simple,
            max_tokens=50,
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
                            "Klassifiziere diesen Bauplan. Antworte NUR mit einem Wort:\n"
                            "- grundriss (Draufsicht mit Wänden, Türen, Räumen)\n"
                            "- deckenspiegel (Spiegelansicht der Decke, Leuchten, Deckenraster)\n"
                            "- schnitt (vertikaler Querschnitt, Geschosse übereinander)\n"
                            "- detail (Konstruktionsdetail, Maßstab 1:10 oder kleiner)\n"
                            "- ansicht (Außenansicht / Fassade)\n"
                            "- unbekannt"
                        ),
                    },
                ],
            }],
        )
        answer = response.content[0].text.strip().lower()

        # Robustes Parsing: erstes bekanntes Wort finden
        for plantyp in ("grundriss", "deckenspiegel", "schnitt", "detail", "ansicht"):
            if plantyp in answer:
                return plantyp  # type: ignore[return-value]
        return "unbekannt"

    async def _detail_analyse(
        self, image_base64: str, page_num: int, plantyp: PlanTyp
    ) -> dict:
        """Detaillierte Bauplan-Analyse mit Opus — plantyp-spezifisch."""
        # System-Prompt aus Datei laden
        prompt_path = (
            Path(__file__).parent.parent.parent.parent / "prompts" / "bauplan-analyse.md"
        )
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

        # User-Prompt je nach Plantyp anpassen
        plantyp_instructions = {
            "grundriss": (
                "Analysiere diesen Grundriss. Extrahiere alle Räume mit Flächen, "
                "Wandlängen nach Wandtyp (W112/W115/W118), und Türöffnungen."
            ),
            "deckenspiegel": (
                "Analysiere diesen Deckenspiegel. Extrahiere alle Deckentypen pro Raum "
                "(GKb-Abhangdecke, Aquapanel, Kühldecke etc.), Abhängehöhen, "
                "Profiltypen (CD 60/27), Deckenschürzen und Nassraum-Kennzeichnungen. "
                "Achte besonders auf 'entfällt'-Markierungen — diese nicht kalkulieren!"
            ),
            "schnitt": (
                "Analysiere diesen Gebäudeschnitt. Extrahiere Raumhöhen, Geschosshöhen, "
                "Abhängehöhen von Decken und Wandhöhen."
            ),
            "detail": (
                "Analysiere dieses Konstruktionsdetail. Beschreibe den Aufbau Schicht für "
                "Schicht, einschließlich Profil-Typen, Plattentypen und -stärken."
            ),
        }

        user_text = (
            f"Seite {page_num}, Plantyp: {plantyp}.\n\n"
            f"{plantyp_instructions.get(plantyp, 'Analysiere diesen Plan.')}\n\n"
            f"Antworte im JSON-Format gemäß dem System-Prompt."
        )

        response = await self.client.messages.create(
            model=settings.claude_model_complex,
            max_tokens=8192,
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
                    {"type": "text", "text": user_text},
                ],
            }],
        )

        # TODO: JSON aus Antwort extrahieren + parsen
        return {"plantyp": plantyp, "raw": response.content[0].text}

    async def _validate_result(self, result: dict, plantyp: PlanTyp) -> dict:
        """Plausibilitätsprüfung: plantyp-spezifische Validierung."""
        # TODO: Sprint 2 — Validierungslogik implementieren
        #
        # Grundriss:
        #   - Summe Raumflächen ≈ Bruttogeschossfläche × 0.85
        #   - Wandlängen pro m² Grundfläche: 0.3–0.6 m/m²
        #
        # Deckenspiegel:
        #   - Summe Deckenflächen ≈ Summe Raumflächen
        #   - Abhängehöhe 0.10–0.60m (sonst Warnung)
        #   - Nassraum-Decken nur in Nassräumen (WC, Dusche, Küche)
        #
        # Schnitt:
        #   - Raumhöhen: Wohnbau 2.40–2.60m, Büro 2.70–3.20m
        #   - Geschosshöhen: 2.80–4.00m
        return result
