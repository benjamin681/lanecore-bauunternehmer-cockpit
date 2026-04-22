#!/usr/bin/env python
"""B+4.2.6 Option C Phase 2c — Backfill von product_code_*-Feldern.

Wendet :func:`app.services.product_code_extractor.extract_product_code`
rueckwirkend auf alle Entries einer Pricelist an und ergaenzt die drei
neuen Keys in :attr:`SupplierPriceEntry.attributes`:

    product_code_type       (z. B. "CW")
    product_code_dimension  (z. B. "75")
    product_code_raw        (z. B. "CW75")

Die Funktion ist deterministisch (pure Regex) und ohne API-Call, daher
unkritisch zu wiederholen. Bestehende Keys werden **nicht**
ueberschrieben; nur fehlende product_code_*-Keys werden erganzt.

Aufruf:

    # Dry-Run (keine DB-Aenderung):
    python -m scripts.backfill_product_codes --pricelist-id <uuid> --dry-run

    # Echte Schreibung:
    python -m scripts.backfill_product_codes --pricelist-id <uuid>

Gibt einen Bericht mit Count (nach product_code_type) und einer Top-10-
Uebersicht auf stdout aus.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Iterable

from app.core import database
from app.models.pricing import SupplierPriceEntry
from app.services.product_code_extractor import extract_product_code


def backfill_pricelist(
    pricelist_id: str,
    *,
    dry_run: bool = False,
) -> tuple[int, Counter, list[tuple[str, str]]]:
    """Fuehre den Backfill aus und liefere (changed_count, counter_by_type,
    sample_changes)."""
    db = database.SessionLocal()
    try:
        entries: list[SupplierPriceEntry] = (
            db.query(SupplierPriceEntry)
            .filter(SupplierPriceEntry.pricelist_id == pricelist_id)
            .all()
        )
        by_type: Counter[str] = Counter()
        samples: list[tuple[str, str]] = []
        changed = 0

        for e in entries:
            code = extract_product_code(e.product_name)
            if code is None:
                continue

            attrs = dict(e.attributes or {})

            # Safety: wenn ein Key schon drin ist, bewahren wir ihn —
            # aber das sollte fuer Kemmler leer sein.
            if (
                "product_code_type" in attrs
                or "product_code_dimension" in attrs
                or "product_code_raw" in attrs
            ):
                # Nichts ueberschreiben; trotzdem nicht als Aenderung zaehlen
                continue

            attrs["product_code_type"] = code["type"]
            attrs["product_code_dimension"] = code["dimension"]
            attrs["product_code_raw"] = code["raw"]

            if not dry_run:
                e.attributes = attrs
                # Trigger SQLAlchemy-JSON-change-detection
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(e, "attributes")

            changed += 1
            by_type[code["type"]] += 1
            if len(samples) < 5:
                samples.append((code["raw"], e.product_name[:70]))

        if not dry_run:
            db.commit()
        else:
            db.rollback()

        return changed, by_type, samples
    finally:
        db.close()


def format_report(
    pricelist_id: str,
    changed: int,
    by_type: Counter,
    samples: Iterable[tuple[str, str]],
    *,
    dry_run: bool,
) -> str:
    lines = []
    mode = "DRY RUN (nichts committed)" if dry_run else "WRITE (committed)"
    lines.append(f"=== Backfill {mode} — Pricelist {pricelist_id} ===")
    lines.append(f"Entries geaendert: {changed}")
    lines.append("")
    lines.append("Aufschluesselung nach product_code_type:")
    for typ, n in by_type.most_common(20):
        lines.append(f"  {typ:6} {n:3}")
    lines.append("")
    lines.append("Stichproben (bis zu 5):")
    for raw, name in samples:
        lines.append(f"  {raw:10}  {name}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pricelist-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed, by_type, samples = backfill_pricelist(
        args.pricelist_id, dry_run=args.dry_run
    )
    print(format_report(args.pricelist_id, changed, by_type, samples, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
