"""Bauplan-Analyse Service — Orchestriert Claude-API-Calls für PDF-Analyse."""

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

import anthropic
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings

log = structlog.get_logger()

PlanTyp = Literal["grundriss", "deckenspiegel", "schnitt", "detail", "ansicht", "unbekannt"]

RELEVANTE_PLANTYPEN: set[PlanTyp] = {"grundriss", "deckenspiegel", "schnitt", "detail"}

# Cost per million tokens (approximate, 2026)
MODEL_COSTS = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
}


@dataclass
class AnalyseCallStats:
    """Token usage and cost for a single Claude API call."""
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class BauplanAnalyseService:
    """
    Orchestriert die mehrstufige Bauplan-Analyse:
    1. Plantyp-Klassifikation (Sonnet — günstig)
    2. Detail-Analyse je nach Plantyp (Opus — genau)
    3. JSON-Extraktion aus Antwort
    4. Plausibilitäts-Validierung
    """

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=120.0,  # 2 Minuten Timeout für große Pläne
        )
        self._prompt_cache: dict[str, str] = {}

    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APITimeoutError)),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: log.warning("claude_api_retry", attempt=rs.attempt_number),
    )
    async def _call_claude(self, **kwargs) -> anthropic.types.Message:
        """Claude API call with automatic retry on rate limit / timeout."""
        return await self.client.messages.create(**kwargs)

    async def analyse_page(self, image_base64: str, page_num: int) -> dict:
        """Analysiert eine einzelne Planseite. Returns structured dict + stats."""
        log.info("analysing_bauplan_page", page=page_num)

        # Schritt 1: Plantyp klassifizieren + Basis-Metadaten (Sonnet — günstig)
        plantyp, classify_stats, metadata = await self._classify_plantyp(image_base64)
        log.info(
            "plantyp_classified",
            page=page_num,
            plantyp=plantyp,
            massstab=metadata.get("massstab"),
            raeume_count=metadata.get("raeume_count"),
        )

        if plantyp not in RELEVANTE_PLANTYPEN:
            return {
                "plantyp": plantyp,
                "type": "skipped",
                "reason": f"Plantyp '{plantyp}' nicht relevant für Trockenbau-Kalkulation",
                "stats": classify_stats,
                "_classification_metadata": metadata,
            }

        # Schritt 2: Detail-Analyse (Opus — genau), mit Klassifikations-Kontext
        parsed_result, analyse_stats = await self._detail_analyse(
            image_base64, page_num, plantyp, classification_metadata=metadata,
        )

        # Schritt 3: Validierung
        validated = self._validate_result(parsed_result, plantyp)

        # Kosten zusammenzählen — separat ausweisen
        total_cost = classify_stats.cost_usd + analyse_stats.cost_usd
        total_input = classify_stats.input_tokens + analyse_stats.input_tokens
        total_output = classify_stats.output_tokens + analyse_stats.output_tokens

        validated["_stats"] = {
            "classify_model": classify_stats.model,
            "classify_cost_usd": round(classify_stats.cost_usd, 6),
            "analyse_model": analyse_stats.model,
            "analyse_cost_usd": round(analyse_stats.cost_usd, 6),
            "model": analyse_stats.model,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cost_usd": round(total_cost, 6),
        }
        validated["_classification_metadata"] = metadata

        return validated

    # --- Plantyp-Klassifikation ---

    async def _classify_plantyp(self, image_base64: str) -> tuple[PlanTyp, AnalyseCallStats, dict]:
        """Klassifiziert den Plantyp und extrahiert Basis-Metadaten (günstig mit Sonnet).

        Returns:
            Tuple of (plantyp, stats, metadata_dict).
            metadata_dict contains keys: massstab, geschoss, projekt_info, raeume_count, raum_namen.
        """
        model = settings.claude_model_simple
        response = await self._call_claude(
            model=model,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": image_base64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analysiere diesen Bauplan in zwei Schritten.\n\n"
                            "1. Klassifiziere den Plantyp als EXAKT eines von:\n"
                            "   grundriss | deckenspiegel | schnitt | detail | ansicht | unbekannt\n\n"
                            "2. Extrahiere folgende Metadaten (soweit erkennbar):\n"
                            "   - Maßstab (z.B. '1:100')\n"
                            "   - Geschoss (z.B. 'EG', 'OG1', 'UG')\n"
                            "   - Projekt-Info (Projektname, Adresse, Plan-Nr falls sichtbar)\n"
                            "   - Anzahl erkennbarer Räume und deren Namen/Nummern\n\n"
                            "Antworte NUR als JSON:\n"
                            '{"plantyp": "grundriss", "massstab": "1:100", "geschoss": "EG", '
                            '"projekt_info": {"name": "...", "adresse": "...", "plan_nr": "..."}, '
                            '"raeume_count": 5, "raum_namen": ["Flur 0.1.01", "Büro 0.1.02"]}'
                        ),
                    },
                ],
            }],
        )

        stats = self._calc_stats(model, response)
        raw_text = response.content[0].text.strip()

        # Try to parse JSON response
        metadata: dict = {}
        try:
            parsed = self._extract_json(raw_text)
            metadata = {
                "massstab": parsed.get("massstab"),
                "geschoss": parsed.get("geschoss"),
                "projekt_info": parsed.get("projekt_info"),
                "raeume_count": parsed.get("raeume_count"),
                "raum_namen": parsed.get("raum_namen", []),
            }
            answer = (parsed.get("plantyp") or "").lower()
        except Exception:
            answer = raw_text.lower()

        for plantyp in ("grundriss", "deckenspiegel", "schnitt", "detail", "ansicht"):
            if plantyp in answer:
                return plantyp, stats, metadata  # type: ignore[return-value]
        return "unbekannt", stats, metadata

    # --- Detail-Analyse ---

    async def _detail_analyse(
        self,
        image_base64: str,
        page_num: int,
        plantyp: PlanTyp,
        classification_metadata: dict | None = None,
    ) -> tuple[dict, AnalyseCallStats]:
        """Detaillierte Bauplan-Analyse mit Opus — plantyp-spezifisch.

        classification_metadata from Stage 1 (Sonnet) is injected as context prefix
        so Opus knows the plan type, scale, and room count upfront.
        """
        system_prompt = self._load_system_prompt()
        model = settings.claude_model_complex

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

        # Build context prefix from Stage 1 classification
        context_prefix = ""
        meta = classification_metadata or {}
        if meta:
            parts = [f"Vorklassifikation (Stufe 1): Plantyp={plantyp}"]
            if meta.get("massstab"):
                parts.append(f"Maßstab={meta['massstab']}")
            if meta.get("geschoss"):
                parts.append(f"Geschoss={meta['geschoss']}")
            if meta.get("raeume_count"):
                parts.append(f"Erkannte Räume={meta['raeume_count']}")
            if meta.get("raum_namen"):
                parts.append(f"Raumnamen: {', '.join(meta['raum_namen'][:15])}")
            if meta.get("projekt_info"):
                pi = meta["projekt_info"]
                if isinstance(pi, dict):
                    pi_parts = [f"{k}={v}" for k, v in pi.items() if v]
                    if pi_parts:
                        parts.append(f"Projekt: {', '.join(pi_parts)}")
            context_prefix = " | ".join(parts) + "\n\n"

        user_text = (
            f"{context_prefix}"
            f"Seite {page_num}, Plantyp: {plantyp}.\n\n"
            f"{plantyp_instructions.get(plantyp, 'Analysiere diesen Plan.')}\n\n"
            f"Antworte im JSON-Format gemäß dem System-Prompt."
        )

        response = await self._call_claude(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": image_base64},
                    },
                    {"type": "text", "text": user_text},
                ],
            }],
        )

        stats = self._calc_stats(model, response)
        raw_text = response.content[0].text

        # JSON aus Antwort extrahieren
        parsed = self._extract_json(raw_text)
        parsed["plantyp"] = plantyp
        parsed["_raw_response"] = raw_text
        parsed["_prompt_hash"] = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]

        return parsed, stats

    # --- JSON-Extraktion ---

    @staticmethod
    def _extract_json(response_text: str) -> dict:
        """Extrahiert JSON aus Claude-Antwort, auch wenn Freitext davor/danach steht."""
        # 1. Direktes JSON-Parse
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 2. JSON in Markdown Code-Block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Erstes vollständiges JSON-Objekt finden (mit Brace-Matching)
        depth = 0
        start = None
        for i, char in enumerate(response_text):
            if char == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        return json.loads(response_text[start : i + 1])
                    except json.JSONDecodeError:
                        start = None

        # 4. Fallback: leeres Ergebnis mit Warnung
        log.error("json_extraction_failed", text_preview=response_text[:200])
        return {
            "raeume": [],
            "waende": [],
            "decken": [],
            "konfidenz": 0.0,
            "warnungen": ["JSON konnte nicht aus KI-Antwort extrahiert werden — manuelle Prüfung erforderlich"],
        }

    # --- Validierung ---

    @staticmethod
    def _validate_result(result: dict, plantyp: PlanTyp) -> dict:
        """Plausibilitätsprüfung: plantyp-spezifische Validierung."""
        warnungen = list(result.get("warnungen", []))

        # Konfidenz-Check
        konfidenz = result.get("konfidenz") or 0.0
        if not isinstance(konfidenz, (int, float)):
            try:
                konfidenz = float(konfidenz)
            except (TypeError, ValueError):
                konfidenz = 0.0
        result["konfidenz"] = konfidenz
        if konfidenz < 0.6:
            warnungen.append(
                f"Konfidenz sehr niedrig ({konfidenz:.0%}) — manuelle Prüfung NOTWENDIG"
            )
        elif konfidenz < 0.8:
            warnungen.append(
                f"Konfidenz unter 80% ({konfidenz:.0%}) — einzelne Werte manuell prüfen"
            )

        # Maßstab vorhanden?
        if not result.get("massstab"):
            warnungen.append("Kein Maßstab erkannt — alle Maße unzuverlässig")

        # Plantyp-spezifische Checks
        if plantyp == "grundriss":
            warnungen.extend(_validate_grundriss(result))
        elif plantyp == "deckenspiegel":
            warnungen.extend(_validate_deckenspiegel(result))
        elif plantyp == "schnitt":
            warnungen.extend(_validate_schnitt(result))

        result["warnungen"] = warnungen
        return result

    # --- Hilfsfunktionen ---

    def _load_system_prompt(self) -> str:
        """Lädt System-Prompt aus Datei (mit Cache)."""
        cache_key = "bauplan-analyse"
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "bauplan-analyse.md"
        if prompt_path.exists():
            text = prompt_path.read_text(encoding="utf-8")
            self._prompt_cache[cache_key] = text
            return text
        return ""

    @staticmethod
    def _calc_stats(model: str, response: anthropic.types.Message) -> AnalyseCallStats:
        """Berechnet Token-Usage und Kosten aus API-Response."""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        costs = MODEL_COSTS.get(model, {"input": 15.0, "output": 75.0})
        cost_usd = (
            (input_tokens / 1_000_000) * costs["input"]
            + (output_tokens / 1_000_000) * costs["output"]
        )

        return AnalyseCallStats(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 6),
        )


# --- Validierungsfunktionen (Modul-Level) ---


def _safe_float(val: object, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _validate_grundriss(result: dict) -> list[str]:
    """Plausibilitäts-Checks für Grundrisse."""
    warnings: list[str] = []
    raeume = result.get("raeume") or []
    waende = result.get("waende") or []

    for raum in raeume:
        flaeche = _safe_float(raum.get("flaeche_m2"))
        name = raum.get("bezeichnung", "?")
        if 0 < flaeche < 1.0:
            warnings.append(f"Raum '{name}': Fläche unrealistisch klein ({flaeche:.1f} m²)")
        if flaeche > 500:
            warnings.append(f"Raum '{name}': Fläche ungewöhnlich groß ({flaeche:.1f} m²)")

    total_area = sum(_safe_float(r.get("flaeche_m2")) for r in raeume)
    if total_area > 0 and len(raeume) > 0:
        total_wall_length = sum(_safe_float(w.get("laenge_m")) for w in waende)
        ratio = total_wall_length / total_area
        if ratio > 0 and (ratio < 0.1 or ratio > 1.5):
            warnings.append(
                f"Wandlängen/Fläche-Verhältnis ungewöhnlich ({ratio:.2f} m/m²). "
                f"Typisch: 0.3–0.6 m/m²"
            )

    for wand in waende:
        hoehe = _safe_float(wand.get("hoehe_m"))
        if hoehe > 0 and (hoehe < 2.0 or hoehe > 6.0):
            warnings.append(f"Wand '{wand.get('id', '?')}': Höhe {hoehe:.2f}m ungewöhnlich")

    return warnings


def _validate_deckenspiegel(result: dict) -> list[str]:
    """Plausibilitäts-Checks für Deckenspiegel."""
    warnings: list[str] = []
    decken = result.get("decken") or []

    for decke in decken:
        flaeche = _safe_float(decke.get("flaeche_m2"))
        raum = decke.get("raum", "?")

        if 0 < flaeche < 1.0:
            warnings.append(f"Decke '{raum}': Fläche unrealistisch klein ({flaeche:.1f} m²)")
        if flaeche > 500:
            warnings.append(f"Decke '{raum}': Fläche ungewöhnlich groß ({flaeche:.1f} m²)")

        abhaenge = decke.get("abhaengehoehe_m")
        if abhaenge is not None and (abhaenge < 0.05 or abhaenge > 1.0):
            warnings.append(
                f"Decke '{raum}': Abhängehöhe {abhaenge:.2f}m ungewöhnlich (typisch: 0.10–0.50m)"
            )

    # "entfällt"-Positionen prüfen
    gestrichene = result.get("gestrichene_positionen", [])
    if gestrichene:
        warnings.append(
            f"{len(gestrichene)} gestrichene Position(en) erkannt — "
            f"nicht in Kalkulation enthalten"
        )

    return warnings


def _validate_schnitt(result: dict) -> list[str]:
    """Plausibilitäts-Checks für Schnitte."""
    warnings: list[str] = []
    raeume = result.get("raeume", [])

    for raum in raeume:
        hoehe = _safe_float(raum.get("hoehe_m"))
        name = raum.get("bezeichnung", "?")
        if hoehe > 0 and (hoehe < 2.2 or hoehe > 6.0):
            warnings.append(f"Raum '{name}': Höhe {hoehe:.2f}m ungewöhnlich (typisch: 2.40–4.00m)")

    return warnings
