#!/usr/bin/env bash
#
# recalc-lv.sh — Triggert kalkuliere_lv und gibt Summary aus.
#
# Idempotent: wiederholte Aufrufe rechnen das LV jedes Mal frisch.
# Keine destruktiven Schritte, daher kein --dry-run noetig.
#
# Aufruf:
#   ./recalc-lv.sh [-h] <lv-id> [<tenant-id>]
#
# Wenn tenant-id weggelassen wird, wird sie aus der DB nachgeschlagen.
#
# Exit-Codes:
#   0  Erfolg
#   1  Argumentfehler
#   2  Compose-/Container-Problem
#   3  LV nicht gefunden / Kalkulation fehlgeschlagen

set -euo pipefail

usage() {
    cat <<'USAGE'
recalc-lv.sh — Rekalkulation eines LV via kalkuliere_lv.

Aufruf:
  ./recalc-lv.sh [-h] <lv-id> [<tenant-id>]

Argumente:
  lv-id       UUID des LV. Pflicht.
  tenant-id   UUID des Tenants. Optional — wird aus DB geholt
              falls nicht angegeben.

Output:
  LV-Projektname, status, angebotssumme_netto,
  Anzahl Positionen, Anzahl Positionen mit needs_price_review.
USAGE
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

LV_ID="${1:-}"
TENANT_ID="${2:-}"

if [[ -z "$LV_ID" ]]; then
    echo "[recalc-lv] FEHLER: lv-id fehlt." >&2
    usage
    exit 1
fi

# Compose-Dir finden
COMPOSE_DIR=""
if [[ -f "docker-compose.yml" ]]; then
    COMPOSE_DIR="$(pwd)"
elif [[ -f "/home/appuser/lvp/lv-preisrechner/docker-compose.yml" ]]; then
    COMPOSE_DIR="/home/appuser/lvp/lv-preisrechner"
else
    echo "[recalc-lv] FEHLER: docker-compose.yml nicht gefunden." >&2
    exit 2
fi
cd "${COMPOSE_DIR}"

if ! docker compose ps backend >/dev/null 2>&1; then
    echo "[recalc-lv] FEHLER: Backend-Container laeuft nicht." >&2
    exit 2
fi

# Inline-Python-Script (kein PYTHONPATH-Fummeln, lebt ohnehin nur in /home/appuser/app).
docker compose exec -T -e LV_ID="${LV_ID}" -e ARG_TENANT="${TENANT_ID}" backend python -c '
import os, sys
from app.core.database import SessionLocal
from app.models.lv import LV
from app.services.kalkulation import kalkuliere_lv

LV_ID = os.environ["LV_ID"]
TENANT_ID = os.environ.get("ARG_TENANT") or None

db = SessionLocal()
try:
    lv = db.get(LV, LV_ID)
    if lv is None:
        print(f"[recalc-lv] FEHLER: LV {LV_ID} nicht gefunden", file=sys.stderr)
        sys.exit(3)
    if not TENANT_ID:
        TENANT_ID = lv.tenant_id

    result = kalkuliere_lv(db, LV_ID, TENANT_ID)
    db.commit()
    db.refresh(lv)

    pos_count = len(lv.positions)
    review_count = sum(1 for p in lv.positions if p.needs_price_review)
    print(f"projekt_name:        {lv.projekt_name}")
    print(f"status:              {lv.status}")
    print(f"angebotssumme_netto: {lv.angebotssumme_netto}")
    print(f"positionen_count:    {pos_count}")
    print(f"needs_review_count:  {review_count}")
finally:
    db.close()
' || { echo "[recalc-lv] FEHLER: Rekalkulation fehlgeschlagen" >&2; exit 3; }
