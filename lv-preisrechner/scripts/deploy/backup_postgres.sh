#!/usr/bin/env bash
#
# B+4.3.2c-1: Taeglicher Postgres-Dump.
#
# Schreibt nach /home/appuser/backups/lvp-YYYY-MM-DD.sql.gz, loescht
# Dumps aelter als 14 Tage.
#
# Einmalig in cron eintragen:
#   crontab -e
#   0 2 * * * /home/appuser/lvp/lv-preisrechner/scripts/deploy/backup_postgres.sh \
#             >> /home/appuser/backups/backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${HOME}/backups"
RETENTION_DAYS=14
TIMESTAMP="$(date +%F)"
DUMP_FILE="${BACKUP_DIR}/lvp-${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

# Finde das Compose-Verzeichnis (Script liegt darunter in scripts/deploy/)
COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${COMPOSE_DIR}"

if ! docker compose ps postgres >/dev/null 2>&1; then
    echo "[$(date -Is)] FEHLT: Postgres-Container laeuft nicht." >&2
    exit 2
fi

# .env lesen, um POSTGRES_USER / _DB zu haben
# shellcheck disable=SC1091
set -a
[ -f .env ] && . .env
set +a

if [ -z "${POSTGRES_USER:-}" ] || [ -z "${POSTGRES_DB:-}" ]; then
    echo "[$(date -Is)] FEHLT: POSTGRES_USER / POSTGRES_DB nicht gesetzt." >&2
    exit 3
fi

echo "[$(date -Is)] Starte Dump nach ${DUMP_FILE}"

docker compose exec -T postgres \
    pg_dump -U "${POSTGRES_USER}" --clean --if-exists "${POSTGRES_DB}" \
    | gzip > "${DUMP_FILE}"

ls -lh "${DUMP_FILE}"

echo "[$(date -Is)] Loesche Dumps aelter als ${RETENTION_DAYS} Tage"
find "${BACKUP_DIR}" -maxdepth 1 -name "lvp-*.sql.gz" -mtime +${RETENTION_DAYS} -print -delete

echo "[$(date -Is)] Backup fertig."
