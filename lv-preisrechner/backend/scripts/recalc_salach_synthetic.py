"""Salach Re-Kalkulation gegen die aktuell modifizierten Rezepte.

Strategie:
1) Fresh SQLite at /tmp/salach_recalc.db gebaut aus aktuellen ORM-Models
2) Copy supplier_price_entries (412 Eintraege) aus prod-DB via raw sqlite3
3) Insert minimal Tenant + User + SupplierPricelist
4) Run _kalkuliere_position fuer 7 betroffene Salach-Positionen
5) Vergleich vs Audit-EPs (Vorher) → Vorher-Nachher
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

TMP_DB = Path("/tmp/salach_recalc.db")
if TMP_DB.exists():
    TMP_DB.unlink()

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

engine = create_engine(f"sqlite:///{TMP_DB}", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

from app.core import database  # noqa: E402
database.engine = engine
database.SessionLocal = TestSession

import sys as _sys  # noqa: E402
for mod_name in list(_sys.modules.keys()):
    if not mod_name.startswith("app."):
        continue
    mod = _sys.modules[mod_name]
    if hasattr(mod, "SessionLocal"):
        try:
            setattr(mod, "SessionLocal", TestSession)
        except Exception:
            pass

database.init_db()

# Disable FK enforcement for synthetic data setup (SQLite default is OFF anyway,
# but app code may switch it on per-connection)
with engine.begin() as _c:
    _c.exec_driver_sql("PRAGMA foreign_keys = OFF")


def _auto_insert(table: str, overrides: dict):
    """Insert eine Zeile in `table`, mit Defaults fuer alle NOT NULL Spalten."""
    with engine.connect() as conn:
        cols_info = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    insert_cols, insert_vals = [], []
    for _, name, ctype, notnull, dflt, _pk in cols_info:
        if name in overrides:
            insert_cols.append(name)
            insert_vals.append(overrides[name])
        elif notnull and dflt is None:
            t = (ctype or "").lower()
            if "int" in t or "bool" in t:
                v = 0
            elif "float" in t or "real" in t or "decimal" in t or "numeric" in t:
                v = 0.0
            elif "datetime" in t or "date" in t or "time" in t:
                v = "2026-04-21T00:00:00"
            elif "json" in t:
                v = "{}"
            elif "blob" in t:
                v = b""
            else:
                v = ""
            insert_cols.append(name)
            insert_vals.append(v)
    placeholders = ", ".join(["?"] * len(insert_cols))
    cols_sql = ", ".join(insert_cols)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})",
            tuple(insert_vals),
        )


TENANT_ID = "19f3cd31-3de6-4baa-9de6-317412d32783"
PRICELIST_ID = "56eaf132-471e-4b35-b16f-252cacf6f31b"

# 1) Tenant
_auto_insert("lvp_tenants", {
    "id": TENANT_ID,
    "name": "e2e-test-2026-04-21",
    "stundensatz_eur": 60.0,
    "bgk_prozent": 10.0,
    "agk_prozent": 12.0,
    "wg_prozent": 5.0,
    "use_new_pricing": 1,
})

# 2) User
_auto_insert("lvp_users", {
    "id": "synth-user",
    "tenant_id": TENANT_ID,
    "email": "synth@test.local",
})

# 3) Supplier Pricelists — copy ALL active pricelists from prod DB so FKs resolve
PROD_DB = BACKEND_DIR / "data" / "lv_preisrechner.db"
_prod_for_pl = sqlite3.connect(PROD_DB)
_prod_for_pl.row_factory = sqlite3.Row
prod_pls = _prod_for_pl.execute(
    "SELECT id, tenant_id, supplier_name, list_name FROM lvp_supplier_pricelists WHERE tenant_id=?",
    (TENANT_ID,),
).fetchall()
_prod_for_pl.close()
for pl in prod_pls:
    _auto_insert("lvp_supplier_pricelists", {
        "id": pl["id"],
        "tenant_id": pl["tenant_id"],
        "supplier_name": pl["supplier_name"] or "Synth",
        "list_name": pl["list_name"] or "Synth",
        "valid_from": "2026-04-01",
        "source_file_path": "/dummy.pdf",
        "source_file_hash": "0" * 64,
        "status": "PARSED",
        "is_active": 1,
        "uploaded_by_user_id": "synth-user",
    })
print(f"# Inserted {len(prod_pls)} pricelists")

# 4) Copy supplier_price_entries from prod DB
prod = sqlite3.connect(PROD_DB)
prod.row_factory = sqlite3.Row

with engine.connect() as conn:
    new_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(lvp_supplier_price_entries)").fetchall()]
prod_cols = [r[1] for r in prod.execute("PRAGMA table_info(lvp_supplier_price_entries)").fetchall()]
common = [c for c in new_cols if c in prod_cols]

prod_rows = prod.execute(
    f"SELECT {', '.join(common)} FROM lvp_supplier_price_entries WHERE tenant_id = ?",
    (TENANT_ID,),
).fetchall()
print(f"# Copying {len(prod_rows)} supplier_price_entries via {len(common)} common columns")

placeholders = ", ".join(["?"] * len(common))
cols_sql = ", ".join(common)
with engine.begin() as conn:
    for row in prod_rows:
        conn.exec_driver_sql(
            f"INSERT INTO lvp_supplier_price_entries ({cols_sql}) VALUES ({placeholders})",
            tuple(row),
        )
prod.close()

from app.models.position import Position  # noqa: E402
from app.services.kalkulation import _kalkuliere_position  # noqa: E402

TENANT = SimpleNamespace(
    id=TENANT_ID,
    name="e2e-test-2026-04-21",
    use_new_pricing=True,
    stundensatz_eur=60.0,
    bgk_prozent=10.0,
    agk_prozent=12.0,
    wg_prozent=5.0,
)

SALACH_POSITIONS = [
    ("59.10.0010", "Innenwand, d=100mm", 1019.59, "m²", "W112", "", "GKB"),
    ("59.10.0020", "Innenwand, d=175mm", 11.57, "m²", "W112", "", "GKB"),
    ("59.10.0030", "Innenwand, d=200mm", 89.22, "m²", "W112", "", "GKB"),
    ("59.20.0010", "Schachtwand d 75 mm", 66.97, "m²", "W628B", "", "GKB"),
    ("59.20.0020", "Schachtwand d 100 mm", 79.75, "m²", "W628B", "", "GKB"),
    ("59.20.0030", "Schachtwand d= 75 mm, GKBI", 165.68, "m²", "W628B", "", "GKBI"),
    ("59.20.0040", "Schachtwand d=100 mm, GKBI", 33.81, "m²", "W628B", "", "GKBI"),
]

EP_BEFORE = {
    "59.10.0010": 63.83, "59.10.0020": 63.83, "59.10.0030": 63.83,
    "59.20.0010": 80.27, "59.20.0020": 80.27,
    "59.20.0030": 83.78, "59.20.0040": 83.78,
}


def make_position(oz, titel, menge, einheit, system, fire, platte):
    p = Position()
    p.id = f"synth-{oz}"; p.lv_id = "synth-salach"; p.reihenfolge = 0
    p.oz = oz; p.titel = titel; p.kurztext = titel; p.langtext = titel
    p.menge = menge; p.einheit = einheit
    p.erkanntes_system = system; p.feuerwiderstand = fire; p.plattentyp = platte
    p.materialien = []
    p.material_ep = 0.0; p.lohn_stunden = 0.0; p.lohn_ep = 0.0
    p.zuschlaege_ep = 0.0; p.ep = 0.0; p.gp = 0.0; p.konfidenz = 1.0
    p.manuell_korrigiert = False; p.warnung = ""
    p.needs_price_review = False; p.price_source_summary = ""
    p.is_bedarf = False; p.is_alternative = False
    return p


def main():
    db = TestSession()
    try:
        print(f"# Tenant: {TENANT.name} (Stundensatz {TENANT.stundensatz_eur} EUR/h, "
              f"Zuschlaege {TENANT.bgk_prozent + TENANT.agk_prozent + TENANT.wg_prozent}%)\n")

        rows, total_b, total_a = [], 0.0, 0.0
        for oz, titel, menge, einheit, sys_, fire, platte in SALACH_POSITIONS:
            p = make_position(oz, titel, menge, einheit, sys_, fire, platte)
            _kalkuliere_position(db, TENANT, None, p)
            ep_b = EP_BEFORE.get(oz, 0.0)
            ep_a = p.ep
            gp_b = round(ep_b * menge, 2)
            gp_a = round(ep_a * menge, 2)
            total_b += gp_b; total_a += gp_a
            rows.append({
                "oz": oz, "system": sys_, "platte": platte, "menge": menge,
                "ep_before": ep_b, "ep_after": round(ep_a, 2),
                "delta_ep": round(ep_a - ep_b, 2),
                "gp_before": gp_b, "gp_after": gp_a, "delta_gp": round(gp_a - gp_b, 2),
                "material_ep": round(p.material_ep, 2),
                "lohn_ep": round(p.lohn_ep, 2),
                "zuschlaege_ep": round(p.zuschlaege_ep, 2),
                "warnung": p.warnung[:140] if p.warnung else "",
            })

        print(f"{'OZ':<13}{'Sys':<8}{'Plt':<6}{'Menge':>10}{'EP_old':>10}{'EP_new':>10}{'ΔEP':>9}{'GP_old':>13}{'GP_new':>13}{'ΔGP':>11}")
        for r in rows:
            print(f"{r['oz']:<13}{r['system']:<8}{r['platte']:<6}{r['menge']:>10.2f}{r['ep_before']:>10.2f}{r['ep_after']:>10.2f}{r['delta_ep']:>9.2f}{r['gp_before']:>13.2f}{r['gp_after']:>13.2f}{r['delta_gp']:>11.2f}")
            if r["warnung"]:
                print(f"  ! {r['warnung']}")

        # Detail-Materialliste fuer 1 W112-Pos und 1 W628B-Pos (zur Verification der Recipe-Aenderungen)
        print("\n# Detail Material-Liste W112 (59.10.0010):")
        p1 = make_position(*SALACH_POSITIONS[0])
        _kalkuliere_position(db, TENANT, None, p1)
        for m in p1.materialien:
            print(f"  - {m.get('dna_pattern','?'):<35} menge={m.get('menge',0):>6}  preis={m.get('preis',0):>6.2f}  gp={m.get('gp',0):>6.2f}  src={m.get('price_source','?')}")

        print("\n# Detail Material-Liste W628B (59.20.0010):")
        p2 = make_position(*SALACH_POSITIONS[3])
        _kalkuliere_position(db, TENANT, None, p2)
        for m in p2.materialien:
            print(f"  - {m.get('dna_pattern','?'):<35} menge={m.get('menge',0):>6}  preis={m.get('preis',0):>6.2f}  gp={m.get('gp',0):>6.2f}  src={m.get('price_source','?')}")

        print("\n# Aufschluesselung neuer EPs:")
        for r in rows:
            print(f"  {r['oz']} ({r['system']}/{r['platte']}): "
                  f"material={r['material_ep']:.2f} + lohn={r['lohn_ep']:.2f} + "
                  f"zuschl={r['zuschlaege_ep']:.2f} = EP {r['ep_after']:.2f}")

        delta = round(total_a - total_b, 2)
        delta_pct = (delta / total_b * 100) if total_b else 0
        print(f"\n# Summe (7 Salach-Positionen):")
        print(f"#   GP vorher : {total_b:>13.2f} EUR")
        print(f"#   GP nachher: {total_a:>13.2f} EUR")
        print(f"#   Delta     : {delta:>+13.2f} EUR ({delta_pct:+.2f}%)")

        out = {
            "tenant": TENANT.name,
            "stundensatz": TENANT.stundensatz_eur,
            "rows": rows,
            "summary": {
                "gp_before": round(total_b, 2),
                "gp_after": round(total_a, 2),
                "delta": delta,
                "delta_pct": round(delta_pct, 4),
            },
        }
        Path("/tmp/salach_recalc.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"# JSON: /tmp/salach_recalc.json")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
