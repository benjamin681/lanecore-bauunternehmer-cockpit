#!/usr/bin/env python
"""B+4.3.0b Phase 4 — Smoke-Test gegen echte Stuttgart-LV-Positionen.

Ruft :func:`list_candidates_for_position` direkt auf die Service-Funktion
fuer drei ausgewaehlte Positionen auf und berichtet Preise, Kandidaten-
Listen, Blacklist-Verhalten und Laufzeit.

Wichtig: das Skript nutzt die **bestehende Dev-DB** (nicht in-memory)
und die bereits gebackfillten Kemmler-Entries (`product_code_*` in
`attributes`). Keine API-Calls, keine Kosten.
"""

from __future__ import annotations

import time
from decimal import Decimal

from app.core import database
from app.models.position import Position
from app.services.price_lookup import list_candidates_for_position

TENANT = "19f3cd31-3de6-4baa-9de6-317412d32783"

POSITIONS = [
    ("W628A (CW/UW/Daemmung)", "cb0e9791-dea0-4d07-b76c-f2b6eeb4edd3"),
    ("Deckensegel (exotisch)", "6b822cd7-ec25-4236-a030-acc59c2ab5bb"),
    ("Streckmetalldecke", "6e9c2797-3621-47ec-a18c-d0f999b603de"),
]


def _dump_position(db, label: str, pos_id: str) -> None:
    pos = db.query(Position).filter(Position.id == pos_id).first()
    if not pos:
        print(f"\n### {label}: Position NOT FOUND ({pos_id})")
        return
    start = time.perf_counter()
    materials = list_candidates_for_position(
        db=db,
        tenant_id=TENANT,
        erkanntes_system=pos.erkanntes_system,
        feuerwiderstand=pos.feuerwiderstand,
        plattentyp=pos.plattentyp,
        limit=3,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n### {label}")
    print(
        f"   oz={pos.oz}  system={pos.erkanntes_system}  "
        f"menge={pos.menge}{pos.einheit}  elapsed={elapsed_ms:.0f} ms"
    )
    if not materials:
        print("   materials: [] (kein Rezept)")
        return
    print(f"   materials: {len(materials)}")
    for i, m in enumerate(materials, start=1):
        print(
            f"   [{i}] {m['material_name']!r} ({m['required_amount']}"
            f" {m['unit']}) — {len(m['candidates'])} Kandidaten"
        )
        for c in m["candidates"]:
            marker = "★" if c["stage"] == "supplier_price" else (
                "≈" if c["stage"] == "fuzzy" else "Ø"
            )
            price = c["price_net"]
            name = c["candidate_name"][:55]
            print(
                f"       {marker} {c['stage']:14}  "
                f"conf={c['match_confidence']:.2f}  "
                f"price={price:7.3f} {c['unit']:6}  {name!r}"
            )
    # UT40-Sanity: kein einziges candidate_name darf UT40 enthalten
    leaked = [
        c["candidate_name"]
        for m in materials
        for c in m["candidates"]
        if "UT40" in c["candidate_name"]
    ]
    if leaked:
        print(f"   ⚠ UT40 leaked into candidates: {leaked}")
    else:
        print("   ✓ UT40 blacklist clean")


def main() -> int:
    db = database.SessionLocal()
    try:
        for label, pos_id in POSITIONS:
            _dump_position(db, label, pos_id)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
