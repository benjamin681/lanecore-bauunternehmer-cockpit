#!/usr/bin/env bash
#
# reparse-pricelist.sh — Re-Parse einer SupplierPriceList.
#
# Destructive: loescht alle bestehenden Entries der Pricelist und setzt
# Status zurueck. Verlangt --confirm zur Bestaetigung; --dry-run zeigt
# nur was geloescht wuerde.
#
# Idempotent in dem Sinn, dass wiederholter Aufruf erneut von vorne
# parsst — nicht in dem Sinn, dass die alten Entries zurueckkommen.
#
# Aufruf:
#   ./reparse-pricelist.sh [-h] [--dry-run] [--confirm] [--batch-size N] <pricelist-id>
#
# Standard-Verhalten ohne --confirm: Status-Anzeige + Hinweis, wie
# der echte Lauf ausgesehen haette. Damit kann das Skript gefahrlos
# zur Inspektion aufgerufen werden.
#
# Exit-Codes:
#   0  Erfolg (parse durch oder dry-run)
#   1  Argumentfehler
#   2  Compose-/Container-Problem
#   3  Pricelist nicht gefunden
#   4  Parse-Funktion hat exception geworfen

set -euo pipefail

usage() {
    cat <<'USAGE'
reparse-pricelist.sh — Re-Parse einer SupplierPriceList.

WARNUNG: Loescht alle bestehenden Entries und ruft Claude-Vision neu —
typisch 18-22 Min Laufzeit + 15-20 USD API-Kosten fuer eine Kemmler-A+-
PDF (~26 Seiten, batch_size=3).

Aufruf:
  ./reparse-pricelist.sh [-h] [--dry-run] [--confirm] [--batch-size N] <pricelist-id>

Optionen:
  -h, --help       Diese Hilfe.
  --dry-run        Nur anzeigen, was passieren wuerde. Status,
                   Entry-Count, source_file_path. Kein Schreibvorgang.
  --confirm        Pflicht-Flag fuer den echten Lauf. Ohne --confirm
                   verhaelt sich das Script wie --dry-run.
  --batch-size N   batch_size fuer den Parser. Default 3.

Output bei echtem Lauf:
  - DELETE-Count
  - parse_entries / needs_review / errors aus ParseResult
  - finaler Status (PARSED / PARTIAL_PARSE / ERROR)

Hinweise:
  - Bestehende ProductCorrections + LV-Gap-Resolutions ueberleben den
    Re-Parse und werden vom Parser-Hook beim Insert wieder angewendet.
  - Existierende source_file_path muss im Container-Volume vorhanden
    sein, sonst FileNotFoundError.
USAGE
}

DRY_RUN="false"
CONFIRM="false"
BATCH_SIZE="3"
PL_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0;;
        --dry-run) DRY_RUN="true"; shift;;
        --confirm) CONFIRM="true"; shift;;
        --batch-size) BATCH_SIZE="$2"; shift 2;;
        --) shift; break;;
        -*) echo "Unbekannte Option: $1" >&2; usage; exit 1;;
        *) PL_ID="$1"; shift;;
    esac
done

if [[ -z "$PL_ID" ]]; then
    echo "[reparse] FEHLER: pricelist-id fehlt." >&2
    usage
    exit 1
fi

# Default: Wenn weder --confirm noch --dry-run, dann implizit dry-run.
if [[ "$DRY_RUN" == "false" && "$CONFIRM" == "false" ]]; then
    echo "[reparse] HINWEIS: Weder --confirm noch --dry-run angegeben — fahre als --dry-run."
    DRY_RUN="true"
fi

COMPOSE_DIR=""
if [[ -f "docker-compose.yml" ]]; then
    COMPOSE_DIR="$(pwd)"
elif [[ -f "/home/appuser/lvp/lv-preisrechner/docker-compose.yml" ]]; then
    COMPOSE_DIR="/home/appuser/lvp/lv-preisrechner"
else
    echo "[reparse] FEHLER: docker-compose.yml nicht gefunden." >&2
    exit 2
fi
cd "${COMPOSE_DIR}"

if ! docker compose ps postgres >/dev/null 2>&1; then
    echo "[reparse] FEHLER: Postgres-Container laeuft nicht." >&2
    exit 2
fi
if ! docker compose ps backend >/dev/null 2>&1; then
    echo "[reparse] FEHLER: Backend-Container laeuft nicht." >&2
    exit 2
fi

set -a
[[ -f .env ]] && . ./.env
set +a
PGUSER="${POSTGRES_USER:-lvpuser}"
PGDB="${POSTGRES_DB:-lvpreisrechner}"

# Existenz + Snapshot
SNAP="$(docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -t -A \
    -F'|' -c "SELECT id, status, COALESCE(entries_total::text, 'NULL'),
                     source_file_path
              FROM lvp_supplier_pricelists WHERE id = '${PL_ID}'" 2>/dev/null \
    || true)"
if [[ -z "$SNAP" ]]; then
    echo "[reparse] FEHLER: Pricelist ${PL_ID} nicht gefunden." >&2
    exit 3
fi
ENTRY_COUNT="$(docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -t -A \
    -c "SELECT COUNT(*) FROM lvp_supplier_price_entries
        WHERE pricelist_id = '${PL_ID}'" | tr -d '[:space:]')"

echo "[reparse] Snapshot vor Aktion:"
IFS='|' read -r SNAP_ID SNAP_STATUS SNAP_TOTAL SNAP_PATH <<< "$SNAP"
echo "  pricelist_id:     ${SNAP_ID}"
echo "  status:           ${SNAP_STATUS}"
echo "  entries_total:    ${SNAP_TOTAL}"
echo "  actual_entries:   ${ENTRY_COUNT}"
echo "  source_file_path: ${SNAP_PATH}"
echo "  batch_size:       ${BATCH_SIZE}"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[reparse] dry-run — keine Aenderung. Mit --confirm wirklich fahren."
    exit 0
fi

# Echter Lauf — DB Reset
echo "[reparse] DELETE entries + Status-Reset ..."
docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" <<SQL
BEGIN;
DELETE FROM lvp_supplier_price_entries WHERE pricelist_id = '${PL_ID}';
UPDATE lvp_supplier_pricelists
   SET status = 'PENDING_PARSE',
       entries_total = NULL,
       entries_reviewed = NULL,
       parse_error = NULL,
       parse_error_details = NULL,
       is_active = false
 WHERE id = '${PL_ID}';
COMMIT;
SQL

echo "[reparse] Triggere Parse — typisch 18-22 Min ..."

# Inline-Python im Backend (kein /tmp-Pfad-Geraffel).
docker compose exec -T \
    -e PRICELIST_ID="${PL_ID}" \
    -e BATCH_SIZE="${BATCH_SIZE}" \
    backend python -c '
import os, sys, time
from app.core.database import SessionLocal
from app.services.pricelist_parser import PricelistParser

PRICELIST_ID = os.environ["PRICELIST_ID"]
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "3"))

start = time.time()
print(f"[reparse-py] start pid={os.getpid()} batch_size={BATCH_SIZE}", flush=True)
db = SessionLocal()
try:
    parser = PricelistParser(db=db, batch_size=BATCH_SIZE)
    result = parser.parse(PRICELIST_ID)
    elapsed = time.time() - start
    print(f"[reparse-py] done in {elapsed:.1f}s", flush=True)
    print(f"  total_entries:    {result.total_entries}")
    print(f"  parsed_entries:   {result.parsed_entries}")
    print(f"  skipped_entries:  {result.skipped_entries}")
    print(f"  needs_review:     {result.needs_review_count}")
    print(f"  avg_confidence:   {result.avg_confidence:.3f}")
    print(f"  errors:           {len(result.errors)}")
    for e in result.errors[:10]:
        print(f"    - {e}")
finally:
    db.close()
' || { echo "[reparse] FEHLER: Parse-Funktion hat exception geworfen" >&2; exit 4; }

# Final-Status
docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -c "
SELECT id, status, entries_total, entries_reviewed,
       LEFT(COALESCE(parse_error, ''), 80) AS parse_error
FROM lvp_supplier_pricelists WHERE id = '${PL_ID}';"
