# Skill: Claude-API-Integration

## Modell-Auswahl-Strategie

### Entscheidungsbaum für Bauplan-Analyse

```
PDF-Seite eingehend
    ↓
[Sonnet] Ist es ein Grundriss? (günstig)
    ↓ ja
[Sonnet] Plan-Qualität OK? (Schärfe, Lesbarkeit)
    ↓ gut          ↓ schlecht
[Sonnet]         [Opus]
Detail-Analyse   Detail-Analyse
    ↓
Konfidenz < 0.8?
    ↓ ja
[Opus] Erneuter Versuch
```

**Kosten-Orientierung (Stand 2026):**
- Sonnet: ~$3 / MTok Input, ~$15 / MTok Output
- Opus: ~$15 / MTok Input, ~$75 / MTok Output
- Pro Standard-Grundriss (1 Seite, 1024×1024px): ~2.000 Tokens Input, ~500 Output
- Sonnet: ~$0.014 / Seite | Opus: ~$0.07 / Seite
- **Fazit:** Sonnet wo möglich, Opus nur bei Bedarf

---

## Prompt-Engineering für Baupläne

### Strukturierte Outputs erzwingen

```python
# SCHLECHT: Freitext-Anfrage
"Analysiere diesen Bauplan und sage mir die Maße"

# GUT: JSON-Schema vorschreiben
system = """Du antwortest IMMER in diesem JSON-Format:
{
  "raeume": [...],
  "waende": [...],
  "konfidenz": 0.0-1.0,
  "warnungen": [...]
}
Niemals Freitext außerhalb des JSON."""
```

### Prompt-Chaining für komplexe Pläne

```python
# Schritt 1: Orientierung (schnell)
step1 = await claude.ask("Was siehst du? Wie viele Räume, welcher Maßstab?")

# Schritt 2: Raumweise Detail-Analyse
for raum in step1.raeume:
    detail = await claude.ask(f"Analysiere Raum {raum.name} im Detail: Maße, Wandtypen, Öffnungen")

# Schritt 3: Kreuzcheck
check = await claude.ask(f"Stimmen die Teilmaße mit der Gesamtfläche überein? Validiere: {all_results}")
```

### Vision-API Best Practices

```python
# Bild-Qualität optimieren
from PIL import Image
import base64
import io

def prepare_image_for_claude(pdf_page_image: Image.Image) -> str:
    """
    - Mindest-Auflösung: 1000px auf der längsten Seite
    - Max für beste Qualität: 2048px (Claude Vision limit)
    - PNG bevorzugen (verlustfrei für Maßzahlen)
    - JPEG nur wenn PNG zu groß (>5MB)
    """
    # Auf max. 2048px skalieren
    max_size = 2048
    ratio = min(max_size / max(pdf_page_image.size), 1.0)
    if ratio < 1.0:
        new_size = (int(pdf_page_image.size[0] * ratio), int(pdf_page_image.size[1] * ratio))
        pdf_page_image = pdf_page_image.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    pdf_page_image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()
```

---

## Retry-Strategie mit Tenacity

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import anthropic

@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APITimeoutError)),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(3),
)
async def call_claude_with_retry(client, **kwargs):
    return await client.messages.create(**kwargs)
```

---

## Kosten- und Token-Kontrolle

```python
# Token-Zähler (vor dem API-Call)
import anthropic

client = anthropic.Anthropic()
token_count = client.messages.count_tokens(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": [{"type": "image", ...}, {"type": "text", ...}]}]
)
# Warne wenn > 10.000 Tokens (teuer)
if token_count.input_tokens > 10_000:
    log.warning("high_token_count", tokens=token_count.input_tokens)
```

---

## JSON-Extraktion aus Claude-Antwort

```python
import json
import re

def extract_json(response_text: str) -> dict:
    """Extrahiert JSON aus Claude-Antwort, auch wenn Freitext davor/danach."""
    # Versuche direktes JSON-Parse
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Suche JSON-Block in Markdown Code-Block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Suche erstes vollständiges JSON-Objekt
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Kein JSON in Antwort gefunden: {response_text[:200]}")
```

---

## Konfidenz-Validierung

```python
def validate_analyse_result(result: dict) -> tuple[bool, list[str]]:
    """Prüft ob Analyse-Ergebnis plausibel ist."""
    errors = []

    # Konfidenz-Check
    if result.get("konfidenz", 0) < 0.6:
        errors.append("Konfidenz zu niedrig — manuelle Prüfung erforderlich")

    # Flächen-Plausibilität
    total_area = sum(r["flaeche_m2"] for r in result.get("raeume", []))
    if total_area < 10:
        errors.append("Gesamtfläche unrealistisch klein (<10m²)")
    if total_area > 50_000:
        errors.append("Gesamtfläche unrealistisch groß (>50.000m²)")

    # Maßstab vorhanden
    if not result.get("massstab"):
        errors.append("Kein Maßstab erkannt — Maße unzuverlässig")

    return len(errors) == 0, errors
```

---

## Audit-Trail (für jeden API-Call)

```python
# Jeder Claude-Call wird geloggt für Reproduzierbarkeit
@dataclass
class ClaudeCallLog:
    job_id: str
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    prompt_hash: str   # SHA256 des System-Prompts
    page_num: int
    konfidenz: float
    # Speicherung in DB für Audit
```
