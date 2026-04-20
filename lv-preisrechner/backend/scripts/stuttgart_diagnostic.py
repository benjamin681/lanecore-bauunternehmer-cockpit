"""Diagnose-Lauf: parse Stuttgart-LV mit Production-Pipeline, speichere raw JSON.

Nutzt EXAKT dieselbe Kette wie parse_and_store() (lv_parser.py):
- pdf_to_page_images(dpi=200, max_pages=80)
- claude.extract_json() mit lv_parser.SYSTEM_PROMPT
- Batch-weise (claude_pages_per_batch=5)

Schreibt nach tests/golden/snapshots/stuttgart_raw_parse.json.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.services.claude_client import claude
from app.services.lv_parser import SYSTEM_PROMPT, detect_optional_flags
from app.services.pdf_utils import pdf_to_page_images

LV_PR_DIR = Path(__file__).resolve().parents[2]
FIXTURE = LV_PR_DIR / "tests" / "golden" / "fixtures" / "stuttgart_omega_sorg_LV.pdf"
SNAPSHOT_DIR = LV_PR_DIR / "tests" / "golden" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Output-Name via CLI: `python -m scripts.stuttgart_diagnostic stuttgart_raw_parse_v2.json`
OUT_NAME = sys.argv[1] if len(sys.argv) > 1 else "stuttgart_raw_parse.json"
OUT_PATH = SNAPSHOT_DIR / OUT_NAME


def main() -> None:
    print(f"[diagnostic] Lade PDF: {FIXTURE}")
    pdf_bytes = FIXTURE.read_bytes()
    print(f"[diagnostic] PDF-Groesse: {len(pdf_bytes) / 1024:.1f} KB")

    t0 = time.time()
    images = pdf_to_page_images(pdf_bytes, dpi=200, max_pages=80)
    t_render = time.time() - t0
    print(f"[diagnostic] PDF->Images: {len(images)} Seiten in {t_render:.1f}s")

    batch_size = max(1, settings.claude_pages_per_batch)
    print(f"[diagnostic] Batch-Groesse: {batch_size} Seiten/Call")

    # Sammle alles
    projekt_name = ""
    auftraggeber = ""
    positionen: list[dict] = []
    batch_stats: list[dict] = []
    models_used: list[str] = []

    t_api_start = time.time()
    total_input_tokens = 0
    total_output_tokens = 0

    for start in range(0, len(images), batch_size):
        batch = images[start : start + batch_size]
        batch_idx = start // batch_size + 1
        page_range = f"{start + 1}-{start + len(batch)}"
        t_batch = time.time()
        try:
            parsed, model = claude.extract_json(system=SYSTEM_PROMPT, images=batch)
        except Exception as exc:
            print(f"[diagnostic] BATCH {batch_idx} FEHLER (Seiten {page_range}): {exc}")
            batch_stats.append({"batch": batch_idx, "pages": page_range, "error": str(exc)})
            continue
        t_batch_dur = time.time() - t_batch
        models_used.append(model)
        if not projekt_name:
            projekt_name = str(parsed.get("projekt_name", ""))
        if not auftraggeber:
            auftraggeber = str(parsed.get("auftraggeber", ""))
        batch_positions = parsed.get("positionen", []) or []
        positionen.extend(batch_positions)
        batch_stats.append(
            {
                "batch": batch_idx,
                "pages": page_range,
                "model": model,
                "dauer_s": round(t_batch_dur, 1),
                "positionen": len(batch_positions),
            }
        )
        print(
            f"[diagnostic] Batch {batch_idx:2} (S.{page_range}): {len(batch_positions):3} Positionen, {t_batch_dur:.1f}s ({model})"
        )

    t_api_total = time.time() - t_api_start

    # Wende denselben detect_optional_flags-Helper wie im Parser an — der Snapshot
    # reflektiert damit den vollen State, den die DB nach parse_and_store haette.
    for p in positionen:
        is_bedarf, is_alt = detect_optional_flags(
            kurztext=str(p.get("kurztext", "") or ""),
            titel=str(p.get("titel", "") or ""),
            langtext=str(p.get("langtext", "") or ""),
            einheit=str(p.get("einheit", "") or ""),
        )
        p["is_bedarf"] = is_bedarf
        p["is_alternative"] = is_alt

    # Analyse
    bedarf_positions = []
    alt_positions = []
    systeme = Counter()
    einheiten = Counter()

    for p in positionen:
        if p.get("is_bedarf"):
            bedarf_positions.append(p.get("oz", ""))
        if p.get("is_alternative"):
            alt_positions.append(p.get("oz", ""))
        sys_key = p.get("erkanntes_system", "") or ""
        if sys_key:
            systeme[sys_key] += 1
        eh = p.get("einheit", "") or ""
        if eh:
            einheiten[eh] += 1

    summary = {
        "fixture": str(FIXTURE.name),
        "pdf_size_kb": round(len(pdf_bytes) / 1024, 1),
        "pages_rendered": len(images),
        "render_seconds": round(t_render, 1),
        "batches": len(batch_stats),
        "batch_size": batch_size,
        "api_seconds": round(t_api_total, 1),
        "total_seconds": round(t_render + t_api_total, 1),
        "models_used": sorted(set(models_used)),
        "projekt_name": projekt_name,
        "auftraggeber": auftraggeber,
        "positionen_total": len(positionen),
        "bedarfspositionen_count": len(bedarf_positions),
        "bedarfspositionen_oz": bedarf_positions,
        "alternativpositionen_count": len(alt_positions),
        "alternativpositionen_oz": alt_positions,
        "erkannte_systeme": dict(systeme.most_common()),
        "einheiten": dict(einheiten.most_common()),
        "batch_stats": batch_stats,
    }

    raw_payload = {
        "summary": summary,
        "positionen": positionen,
    }
    OUT_PATH.write_text(
        json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print("=" * 60)
    print("DIAGNOSE-REPORT")
    print("=" * 60)
    print(f"Fixture:         {FIXTURE.name}")
    print(f"Seiten:          {len(images)}")
    print(f"Batches:         {len(batch_stats)} x {batch_size} Seiten")
    print(f"Models:          {', '.join(sorted(set(models_used)))}")
    print(f"Render-Zeit:     {t_render:.1f}s")
    print(f"API-Zeit:        {t_api_total:.1f}s")
    print(f"Gesamt:          {t_render + t_api_total:.1f}s")
    print()
    print(f"Projekt:         {projekt_name}")
    print(f"Auftraggeber:    {auftraggeber}")
    print(f"Positionen:      {len(positionen)}")
    print(f"  davon Bedarf:  {len(bedarf_positions)}")
    print(f"  davon Alt.:    {len(alt_positions)}")
    print()
    print("Erkannte Systeme:")
    for sys_key, count in systeme.most_common():
        print(f"  {sys_key:25} {count}")
    print()
    print("Einheiten:")
    for eh, count in einheiten.most_common():
        print(f"  {eh:10} {count}")
    print()
    print(f"Snapshot gespeichert: {OUT_PATH}")


if __name__ == "__main__":
    main()
