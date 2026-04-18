"""Live-Smoke-Test: Echter Claude-API-Call gegen die echten PDFs.

Benötigt: ANTHROPIC_API_KEY in .env. Läuft NICHT in CI — manueller Trigger.

Nutzt echte Habau-LV + Kemmler-Preisliste, ruft Claude Sonnet 4.6 auf,
meldet am Ende: Anzahl Positionen, Summe, Matching-Quote.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from app.core import database  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.kalkulation import kalkuliere_lv  # noqa: E402
from app.services.lv_parser import parse_and_store as parse_lv  # noqa: E402
from app.services.pdf_filler import generate_filled_pdf  # noqa: E402
from app.services.price_list_parser import activate, parse_and_store as parse_pl  # noqa: E402


def human_eur(v: float) -> str:
    return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    print("=" * 80)
    print("Live-Smoke-Test LV-Preisrechner")
    print("=" * 80)
    print(f"DB: {settings.database_url}")
    print(f"Primary model: {settings.claude_model_primary}")
    print(f"Upload dir: {settings.upload_dir}")
    if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("sk-dummy"):
        print("ERROR: ANTHROPIC_API_KEY nicht gesetzt. .env prüfen.")
        sys.exit(1)

    # Frische DB
    database.init_db()

    db = database.SessionLocal()
    try:
        # 1. Tenant + User
        tenant = Tenant(name="Livesmoke-Betrieb")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="smoke@test.de",
            password_hash="x",
        )
        db.add(user)
        db.commit()

        # 2. Preisliste-PDF finden
        downloads = Path.home() / "Downloads"
        kemmler_candidates = [
            downloads / "A+ Liste Ausbau.pdf",
            downloads / "A-Liste Ausbau.pdf",
        ]
        kemmler_pdf = next((p for p in kemmler_candidates if p.exists()), None)
        if not kemmler_pdf:
            print(f"ERROR: Keine Kemmler-PDF in {downloads} gefunden")
            sys.exit(1)

        lv_pdf_path = downloads / "LV-Trockenbauarbeiten.pdf"
        if not lv_pdf_path.exists():
            print(f"ERROR: LV-PDF nicht gefunden: {lv_pdf_path}")
            sys.exit(1)

        # 3. Preisliste parsen
        print(f"\n[1/4] Parse Preisliste: {kemmler_pdf.name} ({kemmler_pdf.stat().st_size / 1024:.0f} KB)")
        t0 = time.time()
        with open(kemmler_pdf, "rb") as f:
            pl = parse_pl(
                db=db,
                tenant_id=tenant.id,
                pdf_bytes=f.read(),
                original_dateiname=kemmler_pdf.name,
                haendler="Kemmler",
                niederlassung="Neu-Ulm",
                stand_monat="04/2026",
            )
        print(
            f"    {pl.eintraege_gesamt} Einträge erkannt "
            f"({pl.eintraege_unsicher} unsicher) in {time.time() - t0:.1f}s"
        )
        activate(db, tenant.id, pl.id)
        print("    Preisliste aktiviert.")

        # 4. LV parsen
        print(f"\n[2/4] Parse LV: {lv_pdf_path.name} ({lv_pdf_path.stat().st_size / 1024:.0f} KB)")
        t0 = time.time()
        with open(lv_pdf_path, "rb") as f:
            lv = parse_lv(
                db=db,
                tenant_id=tenant.id,
                pdf_bytes=f.read(),
                original_dateiname=lv_pdf_path.name,
            )
        print(
            f"    Projekt: {lv.projekt_name}\n"
            f"    Auftraggeber: {lv.auftraggeber}\n"
            f"    {lv.positionen_gesamt} Positionen erkannt "
            f"({lv.positionen_unsicher} unsicher) in {time.time() - t0:.1f}s"
        )

        # 5. Kalkulation
        print(f"\n[3/4] Kalkulation (DNA-Matching gegen Kemmler-Preisliste)")
        t0 = time.time()
        lv = kalkuliere_lv(db, lv.id, tenant.id)
        print(
            f"    Angebotssumme netto: {human_eur(lv.angebotssumme_netto)}\n"
            f"    Sicher gematcht: {lv.positionen_gematcht}/{lv.positionen_gesamt}\n"
            f"    Unsicher: {lv.positionen_unsicher}\n"
            f"    Dauer: {time.time() - t0:.1f}s"
        )

        # Top 5 Positionen + 5 mit Warnung
        print("\n    Top 5 Positionen nach GP:")
        top = sorted(lv.positions, key=lambda p: -p.gp)[:5]
        for p in top:
            print(
                f"      {p.oz:12s} {p.erkanntes_system:8s} {p.menge:>8.1f} {p.einheit:<5s} "
                f"EP {human_eur(p.ep):>12s}  GP {human_eur(p.gp):>14s}"
            )

        warnungen = [p for p in lv.positions if p.warnung]
        if warnungen:
            print(f"\n    Positionen mit Warnung: {len(warnungen)}")
            for p in warnungen[:5]:
                print(f"      {p.oz}: {p.warnung[:80]}")

        # 6. PDF erzeugen
        print(f"\n[4/4] PDF generieren")
        t0 = time.time()
        out = generate_filled_pdf(lv, tenant.name)
        print(f"    {out}")
        print(f"    Größe: {out.stat().st_size / 1024:.1f} KB · Dauer: {time.time() - t0:.1f}s")

        print("\n" + "=" * 80)
        print(f"FERTIG — Angebotssumme netto: {human_eur(lv.angebotssumme_netto)}")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    main()
