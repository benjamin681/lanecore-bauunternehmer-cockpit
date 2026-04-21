"""Smoke-Test fuer price_lookup gegen die echte Kemmler-04/2026-Liste
(B+4.2.6 Scope B).

Ablauf:
  1. Kopiert die existierende tests/live/live_db/live.db in eine
     temporaere Snapshot-Datei — die Produktion/CI bleibt unberuehrt.
  2. Patcht das Schema (Spalte `use_new_pricing` auf tenant, fehlt in
     der alten Snapshot-DB), aktiviert die Kemmler-Liste und setzt
     Status = APPROVED.
  3. Fuehrt `lookup_price` fuer 20 typische Trockenbau-DNA-Pattern aus.
  4. Druckt einen strukturierten Report.

Aufruf:
  cd lv-preisrechner/backend
  .venv/bin/python scripts/smoke_lookup.py

Kein CI, kein pytest — rein manuelles Validierungs-Tool.

HINWEIS (Fixture-Overlap):
In B+4.2.5 haben wir 15 Artikelnamen aus DIESER Kemmler-Liste als
Normalizer-Fixtures verwendet. Die restlichen 312 Entries der Liste
sind fuer den Lookup-Service weiterhin "unbekannte Daten". Zusaetzlich
stammen die 20 DNA-Pattern hier aus dem Rezept-Katalog (W112/W115/...),
nicht aus den Fixtures. Damit ist der Smoke zwar nicht perfekt entkoppelt,
aber tauglich als realistischer Belastungstest.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
LIVE_DB = BACKEND.parent / "tests" / "live" / "live_db" / "live.db"
SNAP_DB = BACKEND.parent / "tests" / "live" / "live_db" / "smoke_snapshot.db"


# ---------------------------------------------------------------------------
# 20 Trockenbau-Pattern aus realen LV-Rezepten (materialrezepte.py)
# ---------------------------------------------------------------------------
PATTERNS: list[dict] = [
    # Gipskartonplatten
    {"id": "GKB 12.5", "dna": "Knauf|Gipskarton|GKB|12.5|", "unit": "m²"},
    {"id": "GKF 12.5", "dna": "Knauf|Gipskarton|GKF|12.5|", "unit": "m²"},
    {"id": "GKFI 12.5", "dna": "Knauf|Gipskarton|GKFI|12.5|", "unit": "m²"},
    {"id": "Diamant 12.5", "dna": "Knauf|Gipskarton|DIAMANT|12.5|", "unit": "m²"},
    {"id": "Silentboard 12.5", "dna": "Knauf|Gipskarton|Silentboard|12.5|", "unit": "m²"},
    # Profile
    {"id": "CW 50", "dna": "|Trockenbauprofile|CW|50|", "unit": "lfm"},
    {"id": "CW 75", "dna": "|Trockenbauprofile|CW|75|", "unit": "lfm"},
    {"id": "CW 100", "dna": "|Trockenbauprofile|CW|100|", "unit": "lfm"},
    {"id": "UW 50", "dna": "|Trockenbauprofile|UW|50|", "unit": "lfm"},
    {"id": "UW 100", "dna": "|Trockenbauprofile|UW|100|", "unit": "lfm"},
    {"id": "CD 60/27", "dna": "|Trockenbauprofile|CD|60|", "unit": "lfm"},
    {"id": "UD 27", "dna": "|Trockenbauprofile|UD|27|", "unit": "lfm"},
    {"id": "UA 50", "dna": "|Unterkonstruktion|UA-Profil|50|", "unit": "lfm"},
    # Putze / Gipse
    {"id": "Rotband 30kg", "dna": "Knauf|Gips-Grundputz|Rotband|30kg|", "unit": "Sack"},
    {"id": "Goldband 30kg", "dna": "Knauf|Gips-Grundputz|Goldband|30kg|", "unit": "Sack"},
    {"id": "Multifinish 25kg", "dna": "Knauf|Gips-Grundputz|Multifinish|25kg|", "unit": "Sack"},
    {"id": "MP75 30kg", "dna": "Knauf|Gips-Grundputz|MP75|30kg|", "unit": "Sack"},
    # Kleinteile
    {"id": "Kreuzverbinder CD", "dna": "|Unterkonstruktion|Kreuzverbinder|60|", "unit": "Stk."},
    {"id": "Direktabhaenger 125", "dna": "|Unterkonstruktion|Direktabhaenger|125|", "unit": "Stk."},
    {"id": "Noniusabhaenger", "dna": "Kemmler|Unterkonstruktion|Noniusabhaenger||", "unit": "Stk."},
]


def _prepare_snapshot() -> Path:
    """Kopiert live.db nach smoke_snapshot.db und patcht Schema + Daten."""
    if not LIVE_DB.exists():
        raise SystemExit(
            f"live.db nicht gefunden: {LIVE_DB}\n"
            "Bitte zuerst den B+2-Live-Lauf ausfuehren (tests/live/test_kemmler_parse.py)."
        )
    if SNAP_DB.exists():
        SNAP_DB.unlink()
    shutil.copy(LIVE_DB, SNAP_DB)

    con = sqlite3.connect(SNAP_DB)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(lvp_tenants)").fetchall()}
        if "use_new_pricing" not in cols:
            con.execute(
                "ALTER TABLE lvp_tenants ADD COLUMN use_new_pricing BOOLEAN NOT NULL DEFAULT 0"
            )
        con.execute("UPDATE lvp_tenants SET use_new_pricing = 1")
        con.execute("UPDATE lvp_supplier_pricelists SET is_active = 1, status = 'APPROVED'")
        # Position-Tabelle: fehlende Spalten koennten SELECT sprengen, wenn
        # die ORM-Session sie ansteuert. Wir brauchen fuer lookup_price nur
        # Tenant/SupplierPriceEntry/SupplierPriceList — Position ist
        # unbeteiligt. Wir ignorieren fehlende position-Spalten.
        con.commit()
    finally:
        con.close()

    return SNAP_DB


def _run_smoke(snap: Path) -> dict:
    """Konfiguriert SQLAlchemy auf die Snapshot-DB und ruft lookup_price
    fuer alle Pattern auf."""
    # DB-URL ueberschreiben, bevor Models importieren
    os.environ["DATABASE_URL"] = f"sqlite:///{snap}"
    # late imports
    from app.core import database as db_mod  # noqa: F401
    # Die App nutzt eine globale engine — wir ueberschreiben sie explizit.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_mod.engine = create_engine(f"sqlite:///{snap}", connect_args={"check_same_thread": False})
    db_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_mod.engine)

    from app.models.pricing import SupplierPriceList
    from app.services.price_lookup import lookup_price

    session = db_mod.SessionLocal()
    try:
        pl = session.query(SupplierPriceList).filter(SupplierPriceList.is_active.is_(True)).first()
        if not pl:
            raise SystemExit("Keine aktive Kemmler-Preisliste im Snapshot.")
        tenant_id = pl.tenant_id

        results: list[dict] = []
        t0 = time.time()
        for p in PATTERNS:
            parts = p["dna"].split("|")
            mfr = parts[0].strip() or None
            cat = parts[1].strip() or None
            produkt = parts[2] if len(parts) > 2 else ""
            abm = parts[3] if len(parts) > 3 else ""
            var = parts[4] if len(parts) > 4 else ""
            material = " ".join(x for x in (produkt, abm, var) if x)
            r = lookup_price(
                db=session,
                tenant_id=tenant_id,
                material_name=material,
                unit=p["unit"],
                manufacturer=mfr,
                category=cat,
            )
            results.append({
                "id": p["id"],
                "dna": p["dna"],
                "price_source": r.price_source,
                "price": float(r.price) if r.price else None,
                "confidence": round(r.match_confidence, 2),
                "needs_review": r.needs_review,
                "source_description": r.source_description,
            })
        elapsed = time.time() - t0
        return {"results": results, "elapsed_s": round(elapsed, 2)}
    finally:
        session.close()


def _report(out: dict) -> None:
    from collections import Counter
    rows = out["results"]
    stages = Counter(r["price_source"] for r in rows)
    stage_2_hits = sum(1 for r in rows if r["price_source"] == "supplier_price")
    stage_1_hits = sum(1 for r in rows if r["price_source"] == "override")
    legacy_hits = sum(1 for r in rows if r["price_source"] == "legacy_price")
    total = len(rows)
    early_hits = stage_1_hits + stage_2_hits + legacy_hits  # Stage <= 3

    print("=" * 72)
    print("SMOKE-LOOKUP gegen Kemmler Ausbau 04/2026")
    print(f"Snapshot: {SNAP_DB}")
    print(f"Pattern gesamt: {total}")
    print(f"Laufzeit: {out['elapsed_s']}s")
    print()
    print("Verteilung nach Stage:")
    for stage, n in stages.most_common():
        pct = 100 * n / total
        print(f"  {stage:15} {n:3}  ({pct:4.0f}%)")
    print()
    print(f"Match-Rate Stage ≤ 2c (supplier_price):  {stage_2_hits}/{total} = {100*stage_2_hits/total:.0f}%")
    print(f"Match-Rate Stage ≤ 3c (inkl. legacy):    {early_hits}/{total} = {100*early_hits/total:.0f}%")
    print()
    print("Alle Pattern:")
    print(f"  {'ID':<22} {'Stage':<15} {'Conf':>5}  Beschreibung")
    print(f"  {'-'*22} {'-'*15} {'-'*5}  {'-'*40}")
    for r in rows:
        desc = r["source_description"][:58]
        print(f"  {r['id']:<22} {r['price_source']:<15} {r['confidence']:>5.2f}  {desc}")


def main() -> int:
    snap = _prepare_snapshot()
    out = _run_smoke(snap)
    _report(out)
    if not out["results"]:
        return 1
    hits = sum(1 for r in out["results"] if r["price_source"] == "supplier_price")
    if hits / len(out["results"]) < 0.5:
        print()
        print(f"WARNUNG: Match-Rate Stage <=2c liegt bei {hits}/{len(out['results'])} (<50%).")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
