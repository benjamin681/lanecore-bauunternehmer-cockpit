#!/usr/bin/env bash
#
# check-pricelist-status.sh — Status-Snapshot einer SupplierPriceList.
#
# Read-only, daher nicht destructive — kein --dry-run noetig.
#
# Aufruf:
#   ./check-pricelist-status.sh [-h] <pricelist-id>
#
# Output:
#   id, status, is_active, entries_total, entries_reviewed,
#   parse_error (truncated), parse_error_details (count + summary).
#
# Exit-Codes:
#   0  Erfolg
#   1  Argumentfehler
#   2  Compose-/Container-Problem
#   3  Pricelist nicht gefunden

set -euo pipefail

usage() {
    cat <<'USAGE'
check-pricelist-status.sh — Status-Snapshot einer SupplierPriceList.

Aufruf:
  ./check-pricelist-status.sh [-h] <pricelist-id>

Output:
  Tabular view: id | status | is_active | entries_total |
                entries_reviewed | parse_error | parse_error_details_count
  Plus pro Batch-Failure eine kurze Zeile mit batch_idx, page_range und
  error_class.
USAGE
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

PL_ID="${1:-}"
if [[ -z "$PL_ID" ]]; then
    echo "[check-pricelist] FEHLER: pricelist-id fehlt." >&2
    usage
    exit 1
fi

COMPOSE_DIR=""
if [[ -f "docker-compose.yml" ]]; then
    COMPOSE_DIR="$(pwd)"
elif [[ -f "/home/appuser/lvp/lv-preisrechner/docker-compose.yml" ]]; then
    COMPOSE_DIR="/home/appuser/lvp/lv-preisrechner"
else
    echo "[check-pricelist] FEHLER: docker-compose.yml nicht gefunden." >&2
    exit 2
fi
cd "${COMPOSE_DIR}"

if ! docker compose ps postgres >/dev/null 2>&1; then
    echo "[check-pricelist] FEHLER: Postgres-Container laeuft nicht." >&2
    exit 2
fi

set -a
[[ -f .env ]] && . ./.env
set +a
PGUSER="${POSTGRES_USER:-lvpuser}"
PGDB="${POSTGRES_DB:-lvpreisrechner}"

# Existenz-Check
EXISTS="$(docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -t -A \
    -c "SELECT 1 FROM lvp_supplier_pricelists WHERE id = '${PL_ID}'" 2>/dev/null \
    | tr -d '[:space:]')"
if [[ "$EXISTS" != "1" ]]; then
    echo "[check-pricelist] FEHLER: Pricelist ${PL_ID} nicht gefunden." >&2
    exit 3
fi

# Hauptzeile
docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -c "
SELECT
  id,
  status,
  is_active,
  entries_total,
  entries_reviewed,
  LEFT(COALESCE(parse_error, ''), 80) AS parse_error,
  COALESCE(jsonb_array_length(parse_error_details::jsonb), 0)
    AS batch_failures
FROM lvp_supplier_pricelists
WHERE id = '${PL_ID}';"

# Echte vs gemeldete Entry-Anzahl
docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -c "
SELECT entries_total AS reported,
       (SELECT COUNT(*) FROM lvp_supplier_price_entries
        WHERE pricelist_id = '${PL_ID}') AS actual
FROM lvp_supplier_pricelists WHERE id = '${PL_ID}';"

# Batch-Failures (falls vorhanden)
docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -c "
SELECT
  (e->>'batch_idx')::int AS batch,
  e->>'page_range' AS pages,
  (e->>'attempts')::int AS attempts,
  e->>'error_class' AS error_class,
  LEFT(e->>'error_message', 80) AS error_message
FROM lvp_supplier_pricelists pl,
     LATERAL jsonb_array_elements(COALESCE(pl.parse_error_details::jsonb, '[]'::jsonb)) e
WHERE pl.id = '${PL_ID}'
ORDER BY 1;"
