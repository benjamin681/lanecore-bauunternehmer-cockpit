"""Live-Smoke fuer den Katalog-Luecken-Endpoint gegen den echten
Stuttgart-LV.

Nicht Teil der CI. Laeuft direkt gegen ``data/lv_preisrechner.db`` und
nutzt die Service-Funktion ``compute_lv_gaps``, die vom API-Handler
auch aufgerufen wird (der HTTP-Layer ist durch ``test_lvs_gaps.py``
bereits mit 10 Tests abgedeckt).

Usage (vom backend/-Verzeichnis):

    .venv/bin/python ../tests/live/test_gaps_smoke.py

Der Report geht auf stdout und wird zusaetzlich als JSON in
``tests/live/e2e_gaps_smoke.json`` abgelegt.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

# Pfad zum Backend setzen, damit `app....`-Imports funktionieren.
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault(
    "DATABASE_URL", f"sqlite:///{(BACKEND / 'data' / 'lv_preisrechner.db').as_posix()}"
)

from app.core import database  # noqa: E402
from app.models.lv import LV  # noqa: E402
from app.services.catalog_gaps import compute_lv_gaps  # noqa: E402


TENANT = "19f3cd31-3de6-4baa-9de6-317412d32783"
LV_ID = "9d9fda20-0ba7-47da-ae77-5518068097cb"


def _call(lv: LV, include_low_confidence: bool) -> tuple[dict, float]:
    t0 = time.time()
    report = compute_lv_gaps(lv, include_low_confidence=include_low_confidence)
    elapsed_ms = round((time.time() - t0) * 1000, 2)
    return report.model_dump(), elapsed_ms


def _perf_bucket(ms: float) -> str:
    if ms < 500:
        return "gruen (<500ms)"
    if ms < 1000:
        return "gelb (500-1000ms)"
    return "rot (>1000ms)"


def main() -> int:
    db = database.SessionLocal()
    try:
        lv = db.query(LV).filter(LV.id == LV_ID, LV.tenant_id == TENANT).first()
        if lv is None:
            print(f"ERR: LV {LV_ID} fuer Tenant {TENANT} nicht gefunden")
            return 2

        print(f"LV geladen: {lv.original_dateiname} | Positionen: {len(lv.positions)}")

        # Call A: default
        a_body, a_ms = _call(lv, include_low_confidence=False)
        print(
            "\n=== Call A — Default (ohne Opt-in) ===\n"
            f"  elapsed: {a_ms} ms  [{_perf_bucket(a_ms)}]\n"
            f"  total_positions: {a_body['total_positions']}\n"
            f"  total_materials: {a_body['total_materials']}\n"
            f"  gaps_count:       {a_body['gaps_count']}\n"
            f"  missing_count:    {a_body['missing_count']}\n"
            f"  estimated_count:  {a_body['estimated_count']}\n"
            f"  low_confidence_count: {a_body['low_confidence_count']}"
        )
        # Counter-Invariante
        inv_a = a_body["gaps_count"] == (
            a_body["missing_count"]
            + a_body["estimated_count"]
            + a_body["low_confidence_count"]
        )
        print(f"  counter_invariant: {'OK' if inv_a else 'FAIL'}")
        # Severities
        sev_a = Counter(g["severity"] for g in a_body["gaps"])
        print(f"  severity distribution (gaps): {dict(sev_a)}")
        # Sortierung: first missing (or no gaps)
        if a_body["gaps"]:
            first = a_body["gaps"][0]["severity"]
            last = a_body["gaps"][-1]["severity"]
            print(f"  first severity: {first}  last: {last}")

        # Call B: include_low_confidence=true
        b_body, b_ms = _call(lv, include_low_confidence=True)
        print(
            "\n=== Call B — Mit include_low_confidence=true ===\n"
            f"  elapsed: {b_ms} ms  [{_perf_bucket(b_ms)}]\n"
            f"  gaps_count:       {b_body['gaps_count']}\n"
            f"  missing_count:    {b_body['missing_count']}\n"
            f"  estimated_count:  {b_body['estimated_count']}\n"
            f"  low_confidence_count: {b_body['low_confidence_count']}"
        )
        inv_b = b_body["gaps_count"] == (
            b_body["missing_count"]
            + b_body["estimated_count"]
            + b_body["low_confidence_count"]
        )
        print(f"  counter_invariant: {'OK' if inv_b else 'FAIL'}")
        sev_b = Counter(g["severity"] for g in b_body["gaps"])
        print(f"  severity distribution (gaps): {dict(sev_b)}")
        print(f"  b_count >= a_count: {b_body['gaps_count'] >= a_body['gaps_count']}")

        # UT40-Verifikation: keine Gap-Zeile darf UT40 im material_name
        # enthalten (Filter ist im Matcher, nicht im Gaps-Report — aber
        # wenn der Matcher UT40 gefiltert hat, erscheint es auch nicht
        # als supplier_price. Stattdessen Daemmung-40mm -> Sonorock oder
        # estimated).
        ut40_hits = [
            g for g in b_body["gaps"]
            if "UT40" in (g["material_name"] or "")
            or "UT40" in (g["source_description"] or "")
        ]
        print(f"\n  UT40-Hits in Gaps: {len(ut40_hits)} (erwartet 0)")

        # Call C: Stichproben aus Call B
        print("\n=== Call C — Stichproben ===")
        samples = {
            "missing": next(
                (g for g in b_body["gaps"] if g["severity"] == "missing"), None
            ),
            "low_confidence": next(
                (g for g in b_body["gaps"] if g["severity"] == "low_confidence"), None
            ),
            "estimated": next(
                (g for g in b_body["gaps"] if g["severity"] == "estimated"), None
            ),
        }
        for label, g in samples.items():
            if g is None:
                print(f"  [{label}] keine im Report")
                continue
            print(
                f"  [{label}] pos={g['position_oz']} "
                f"name='{g['material_name']}'  "
                f"conf={g['match_confidence']}  "
                f"source='{g['price_source']}'"
            )
            # Plausibilitaets-Checks
            if label == "missing" and g["match_confidence"] is not None:
                print("    WARN: missing sollte match_confidence=None haben")
            if label == "low_confidence":
                c = g["match_confidence"]
                if c is None or c >= 0.5:
                    print(
                        f"    WARN: low_confidence erwartet <0.5, hier: {c}"
                    )

        # Snapshot speichern
        out = {
            "lv_id": LV_ID,
            "tenant_id": TENANT,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "call_a_default": {
                "elapsed_ms": a_ms,
                "summary": {
                    k: a_body[k]
                    for k in (
                        "total_positions", "total_materials", "gaps_count",
                        "missing_count", "estimated_count", "low_confidence_count",
                    )
                },
                "severity_distribution": dict(sev_a),
                "counter_invariant": inv_a,
            },
            "call_b_with_low_confidence": {
                "elapsed_ms": b_ms,
                "summary": {
                    k: b_body[k]
                    for k in (
                        "total_positions", "total_materials", "gaps_count",
                        "missing_count", "estimated_count", "low_confidence_count",
                    )
                },
                "severity_distribution": dict(sev_b),
                "counter_invariant": inv_b,
            },
            "samples": {label: g for label, g in samples.items()},
            "ut40_hits_in_gaps": len(ut40_hits),
        }
        out_path = HERE / "e2e_gaps_smoke.json"
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"\nSnapshot gespeichert: {out_path}")

        # Kurzer Pass/Fail-Block
        ok = (
            inv_a and inv_b
            and a_body["gaps_count"] > 0
            and b_body["gaps_count"] >= a_body["gaps_count"]
            and len(ut40_hits) == 0
            and all(
                g["severity"] in {"missing", "estimated"} for g in a_body["gaps"]
            )
        )
        print(f"\nOverall: {'OK' if ok else 'FAIL'}")
        return 0 if ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
