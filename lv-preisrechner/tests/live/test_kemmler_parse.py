"""Live-Test fuer Kemmler-Preislisten-Parser (manuell, nicht Teil der CI).

Simuliert den kompletten Upload + Parse-Flow in-process via FastAPI TestClient.
Nutzt eine frische SQLite-DB unter tests/live/live_db/, die beim naechsten Lauf
ueberschrieben wird (nicht committed).

Usage (vom backend/-Verzeichnis):

    .venv/bin/python ../tests/live/test_kemmler_parse.py <pfad-zur-pdf>

Oder via ENV-Var:

    KEMMLER_PDF_PATH=/pfad/zur.pdf .venv/bin/python ../tests/live/test_kemmler_parse.py

Der Report geht auf stdout und wird zusaetzlich als JSON in
tests/live/live_db/report_<timestamp>.json abgelegt.
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
LIVE_DIR = HERE
BACKEND_DIR = HERE.parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# .env aus backend/.env laden (ANTHROPIC_API_KEY etc.).
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

# Temporaere Daten: alles unter live_db/ (via .gitignore).
LIVE_DB_DIR = LIVE_DIR / "live_db"
LIVE_DB_DIR.mkdir(exist_ok=True)

# Wichtig: vor app-Imports setzen, damit settings das sieht.
os.environ["DATA_DIR"] = str(LIVE_DB_DIR)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core import database  # noqa: E402

# Frische SQLite-DB fuer diesen Lauf.
_DB_FILE = LIVE_DB_DIR / "live.db"
if _DB_FILE.exists():
    _DB_FILE.unlink()
_engine = create_engine(
    f"sqlite:///{_DB_FILE}",
    connect_args={"check_same_thread": False},
)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
database.engine = _engine
database.SessionLocal = _Session

# Re-Bind auch in Modulen, die statisch importiert haben (Worker).
import sys as _sys  # noqa: E402

for _mod_name in list(_sys.modules.keys()):
    _mod = _sys.modules.get(_mod_name)
    if _mod is None or not _mod_name.startswith("app."):
        continue
    if hasattr(_mod, "SessionLocal"):
        try:
            setattr(_mod, "SessionLocal", _Session)
        except Exception:
            pass

database.init_db()

# TestClient-Import erst NACH DB-Setup.
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------
MAX_WAIT_SECONDS = 30 * 60  # 30 Minuten
POLL_INTERVAL = 5  # Sek — TestClient laeuft sync, mehr als 1x nicht noetig.


def _get_pdf_path() -> Path:
    # Erstes nicht-Flag-Argument ist der Pfad
    cand = None
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            continue
        cand = arg
        break
    if not cand:
        cand = os.environ.get("KEMMLER_PDF_PATH")
    if not cand:
        print(
            "[ERROR] Kein PDF-Pfad. Entweder als Argument oder via "
            "KEMMLER_PDF_PATH=... setzen.",
            file=sys.stderr,
        )
        sys.exit(2)
    p = Path(cand).expanduser().resolve()
    if not p.is_file():
        print(f"[ERROR] PDF nicht gefunden: {p}", file=sys.stderr)
        sys.exit(2)
    return p


def _get_max_pages() -> int | None:
    """Liest --max-pages N oder ENV KEMMLER_MAX_PAGES.

    None = alle Seiten verwenden.
    """
    for i, arg in enumerate(sys.argv):
        if arg == "--max-pages" and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                print(
                    "[ERROR] --max-pages erwartet eine Zahl", file=sys.stderr
                )
                sys.exit(2)
        if arg.startswith("--max-pages="):
            try:
                return int(arg.split("=", 1)[1])
            except ValueError:
                sys.exit(2)
    env = os.environ.get("KEMMLER_MAX_PAGES")
    if env:
        try:
            return int(env)
        except ValueError:
            print(
                "[ERROR] KEMMLER_MAX_PAGES muss eine Zahl sein", file=sys.stderr
            )
            sys.exit(2)
    return None


def _truncate_pdf(src: Path, max_pages: int) -> Path:
    """Erzeugt eine neue PDF mit nur den ersten `max_pages` Seiten.

    Ergebnis wird unter live_db/ abgelegt (nicht committed). Wenn die PDF
    kuerzer ist als max_pages, gibt die Originaldatei zurueck.
    """
    import fitz  # PyMuPDF

    src_doc = fitz.open(src)
    n = len(src_doc)
    if max_pages >= n:
        src_doc.close()
        return src
    out = LIVE_DB_DIR / f"{src.stem}__first{max_pages}{src.suffix}"
    new_doc = fitz.open()
    new_doc.insert_pdf(src_doc, from_page=0, to_page=max_pages - 1)
    new_doc.save(out)
    new_doc.close()
    src_doc.close()
    return out


def _register_and_login(client: TestClient) -> str:
    """Legt Test-Tenant + User an, gibt JWT-Token zurueck."""
    email = f"live-kemmler-{int(time.time())}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "LiveTest123!",
            "firma": "Live-Kemmler-Test",
            "vorname": "Live",
            "nachname": "Test",
        },
    )
    if resp.status_code != 201:
        raise RuntimeError(f"Register failed: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


def _upload(client: TestClient, token: str, pdf_path: Path) -> str:
    with pdf_path.open("rb") as f:
        resp = client.post(
            "/api/v1/pricing/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (pdf_path.name, f, "application/pdf")},
            data={
                "supplier_name": "Kemmler",
                "supplier_location": "Neu-Ulm",
                "list_name": "Ausbau 2026-04",
                "valid_from": "2026-04-01",
                "auto_parse": "false",
            },
        )
    if resp.status_code != 201:
        raise RuntimeError(f"Upload failed: {resp.status_code} {resp.text}")
    return resp.json()["id"]


def _trigger_parse(client: TestClient, token: str, pricelist_id: str) -> dict:
    resp = client.post(
        f"/api/v1/pricing/pricelists/{pricelist_id}/parse",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 202:
        raise RuntimeError(f"Parse trigger failed: {resp.status_code} {resp.text}")
    return resp.json()


def _poll_status(client: TestClient, token: str, pricelist_id: str) -> dict:
    """Pollt Status bis PARSED/ERROR oder Timeout. Gibt die letzte Response zurueck."""
    deadline = time.time() + MAX_WAIT_SECONDS
    last = None
    while time.time() < deadline:
        resp = client.get(
            f"/api/v1/pricing/pricelists/{pricelist_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Poll failed: {resp.status_code} {resp.text}")
        last = resp.json()
        if last["status"] in ("PARSED", "ERROR"):
            return last
        print(f"  ... status={last['status']}, warte {POLL_INTERVAL}s ...")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Timeout nach {MAX_WAIT_SECONDS}s")


def _fetch_entries(client: TestClient, token: str, pricelist_id: str) -> list[dict]:
    """Holt alle Entries per Pagination (500er-Chunks)."""
    entries: list[dict] = []
    offset = 0
    while True:
        resp = client.get(
            f"/api/v1/pricing/pricelists/{pricelist_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "include_entries": "true",
                "entries_offset": offset,
                "entries_limit": 500,
            },
        )
        resp.raise_for_status()
        batch = resp.json().get("entries", [])
        if not batch:
            break
        entries.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    return entries


def _histogram(values: list[float], buckets: int = 10) -> list[tuple[str, int]]:
    counts = [0] * buckets
    for v in values:
        idx = min(int(v * buckets), buckets - 1)
        counts[idx] += 1
    out = []
    for i, c in enumerate(counts):
        lo = i * (100 // buckets)
        hi = (i + 1) * (100 // buckets)
        out.append((f"{lo:>3d}-{hi:<3d}%", c))
    return out


def _render_report(pl: dict, entries: list[dict], elapsed_s: float) -> dict:
    n_total = len(entries)
    needs_review_count = sum(1 for e in entries if e.get("needs_review"))
    confs = [float(e.get("parser_confidence", 0.0)) for e in entries]

    # Top-N Helfer
    def _top(key: str, n: int = 10) -> list[tuple[str, int]]:
        c = Counter(
            (e.get(key) or "—").strip() or "—" for e in entries
        )
        return c.most_common(n)

    # High/Low-Confidence-Beispiele
    sorted_hi = sorted(entries, key=lambda e: e.get("parser_confidence", 0), reverse=True)
    sorted_lo = sorted(entries, key=lambda e: e.get("parser_confidence", 0))

    hi_samples = sorted_hi[:5]
    lo_samples = [e for e in sorted_lo if e.get("parser_confidence", 0) < 0.5][:5]

    return {
        "pricelist_id": pl.get("id"),
        "status": pl.get("status"),
        "parse_error": pl.get("parse_error"),
        "elapsed_seconds": round(elapsed_s, 2),
        "entries_total": n_total,
        "needs_review_count": needs_review_count,
        "needs_review_pct": (
            round(100 * needs_review_count / n_total, 1) if n_total else 0.0
        ),
        "avg_confidence": (
            round(sum(confs) / len(confs), 3) if confs else 0.0
        ),
        "confidence_histogram": _histogram(confs),
        "top_manufacturers": _top("manufacturer"),
        "top_units": _top("effective_unit"),
        "top_categories": _top("category"),
        "hi_confidence_samples": hi_samples,
        "lo_confidence_samples": lo_samples,
    }


def _print_report(report: dict) -> None:
    print()
    print("=" * 72)
    print("KEMMLER LIVE-PARSE REPORT")
    print("=" * 72)
    print(f"Pricelist-ID:     {report['pricelist_id']}")
    print(f"Status:           {report['status']}")
    if report.get("parse_error"):
        print(f"Parse-Error:      {report['parse_error']}")
    print(f"Laufzeit:         {report['elapsed_seconds']:.1f} s")
    print()
    print(f"Entries gesamt:   {report['entries_total']}")
    print(
        f"Needs-Review:     {report['needs_review_count']} "
        f"({report['needs_review_pct']} %)"
    )
    print(f"Avg Confidence:   {report['avg_confidence']}")
    print()
    print("Confidence-Histogramm:")
    for label, cnt in report["confidence_histogram"]:
        bar = "█" * min(50, cnt)
        print(f"  {label} {cnt:>4d}  {bar}")
    print()
    print("Top-10 Hersteller:")
    for name, cnt in report["top_manufacturers"]:
        print(f"  {cnt:>4d}  {name}")
    print()
    print("Top-10 Einheiten (effective_unit):")
    for unit, cnt in report["top_units"]:
        print(f"  {cnt:>4d}  {unit}")
    print()
    print("Top-10 Kategorien:")
    for cat, cnt in report["top_categories"]:
        print(f"  {cnt:>4d}  {cat}")
    print()
    print("--- 5 Beispiele mit HOHER Confidence (>= 0.9):")
    for e in report["hi_confidence_samples"]:
        if float(e.get("parser_confidence", 0)) < 0.9:
            continue
        print(
            f"  [{e['parser_confidence']:.2f}] "
            f"{e.get('manufacturer') or '—'} · "
            f"{e.get('product_name')!r} · "
            f"{e.get('price_net')} {e.get('unit')} → "
            f"{e.get('price_per_effective_unit')} €/{e.get('effective_unit')}"
        )
    print()
    print("--- 5 Beispiele mit NIEDRIGER Confidence (< 0.5):")
    if not report["lo_confidence_samples"]:
        print("  (keine — alle Entries >= 0.5)")
    for e in report["lo_confidence_samples"]:
        print(
            f"  [{e['parser_confidence']:.2f}] "
            f"{e.get('manufacturer') or '—'} · "
            f"{e.get('product_name')!r} · "
            f"{e.get('price_net')} {e.get('unit')}"
        )
    print()
    print("=" * 72)


def main() -> int:
    orig_pdf = _get_pdf_path()
    max_pages = _get_max_pages()
    if max_pages is not None:
        print(f"[0/5] --max-pages={max_pages} → PDF wird gekuerzt …")
        pdf_path = _truncate_pdf(orig_pdf, max_pages)
    else:
        pdf_path = orig_pdf
    print(f"[1/5] PDF:        {pdf_path} ({pdf_path.stat().st_size / 1024 / 1024:.2f} MB)")

    with TestClient(app) as client:
        print("[2/5] Register + Login …")
        token = _register_and_login(client)

        print("[3/5] Upload + parse-Trigger …")
        pl_id = _upload(client, token, pdf_path)
        print(f"       pricelist_id = {pl_id}")

        t0 = time.time()
        _trigger_parse(client, token, pl_id)
        # TestClient fuehrt BackgroundTasks sync nach Response aus →
        # danach ist Status bereits PARSED/ERROR.

        print("[4/5] Warte auf Parse-Abschluss …")
        pl_final = _poll_status(client, token, pl_id)
        elapsed = time.time() - t0
        print(f"       Status: {pl_final['status']} nach {elapsed:.1f}s")

        if pl_final["status"] != "PARSED":
            print()
            print(f"[ERROR] Parse fehlgeschlagen: {pl_final.get('parse_error')}")
            return 1

        print("[5/5] Hole alle Entries …")
        entries = _fetch_entries(client, token, pl_id)
        print(f"       {len(entries)} Entries geladen.")

    report = _render_report(pl_final, entries, elapsed)
    _print_report(report)

    # Report als JSON auch ablegen
    out_file = LIVE_DB_DIR / f"report_{int(time.time())}.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport gespeichert: {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
