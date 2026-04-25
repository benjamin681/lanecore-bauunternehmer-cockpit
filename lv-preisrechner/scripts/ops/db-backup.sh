#!/usr/bin/env bash
#
# db-backup.sh — Strukturierter Postgres-Dump.
#
# Schreibt nach /home/appuser/backups/<timestamp>/db.sql (Prod-Pfad). In
# Test-Modi kann --dest-dir genutzt werden. Idempotent in dem Sinne, dass
# wiederholte Aufrufe einfach weitere Timestamp-Verzeichnisse anlegen,
# bestehende Backups bleiben unangetastet.
#
# Aufruf:
#   ./db-backup.sh [-h] [--dry-run] [--label LABEL] [--dest-dir DIR]
#
# Beispiele:
#   ./db-backup.sh
#   ./db-backup.sh --label pre_reparse
#   ./db-backup.sh --dry-run
#
# Exit-Codes:
#   0  Erfolg
#   2  Compose-Dir oder Postgres-Container nicht erreichbar
#   3  pg_dump fehlgeschlagen

set -euo pipefail

LABEL=""
DRY_RUN="false"
DEST_DIR="${HOME}/backups"

usage() {
    cat <<'USAGE'
db-backup.sh — Strukturierter Postgres-Dump fuer Kalkulane.

Optionen:
  -h, --help        Diese Hilfe.
  --label LABEL     Optionales Label im Verzeichnisnamen.
                    Default: nur Timestamp.
  --dest-dir DIR    Ziel-Basisverzeichnis. Default: ~/backups.
  --dry-run         Keine Aktion, nur Pfade ausgeben.

Aufruf-Voraussetzungen:
  - Aufruf entweder direkt auf dem Server (in /home/appuser/lvp/lv-preisrechner)
  - oder via ssh wrapper: ssh lvp-prod "<scriptpfad>"

Erzeugt:
  <DEST_DIR>/<label?>_<timestamp>/db.sql
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0;;
        --label) LABEL="$2"; shift 2;;
        --dest-dir) DEST_DIR="$2"; shift 2;;
        --dry-run) DRY_RUN="true"; shift;;
        *) echo "Unbekannte Option: $1" >&2; usage; exit 1;;
    esac
done

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
if [[ -n "$LABEL" ]]; then
    SUBDIR="${LABEL}_${TIMESTAMP}"
else
    SUBDIR="${TIMESTAMP}"
fi
TARGET="${DEST_DIR}/${SUBDIR}"
DUMP_FILE="${TARGET}/db.sql"

# Compose-Dir suchen: aktuelles Verzeichnis ODER Default-Pfad.
# Dry-Run laeuft auch ohne Compose-Dir (Smoke-Test-freundlich).
COMPOSE_DIR=""
if [[ -f "docker-compose.yml" ]]; then
    COMPOSE_DIR="$(pwd)"
elif [[ -f "/home/appuser/lvp/lv-preisrechner/docker-compose.yml" ]]; then
    COMPOSE_DIR="/home/appuser/lvp/lv-preisrechner"
fi

echo "[db-backup] target=${DUMP_FILE}"
echo "[db-backup] compose_dir=${COMPOSE_DIR:-<not-found>}"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "[db-backup] dry-run — keine Aenderung."
    exit 0
fi

if [[ -z "$COMPOSE_DIR" ]]; then
    echo "[db-backup] FEHLER: docker-compose.yml weder im aktuellen Dir noch /home/appuser/lvp/lv-preisrechner gefunden." >&2
    exit 2
fi

mkdir -p "${TARGET}"
cd "${COMPOSE_DIR}"

if ! docker compose ps postgres >/dev/null 2>&1; then
    echo "[db-backup] FEHLER: Postgres-Container laeuft nicht." >&2
    exit 2
fi

# .env optional — fuer User/DB-Override
set -a
[[ -f .env ]] && . ./.env
set +a
PGUSER="${POSTGRES_USER:-lvpuser}"
PGDB="${POSTGRES_DB:-lvpreisrechner}"

if ! docker compose exec -T postgres \
    pg_dump -U "${PGUSER}" --clean --if-exists "${PGDB}" \
    > "${DUMP_FILE}"; then
    echo "[db-backup] FEHLER: pg_dump fehlgeschlagen." >&2
    exit 3
fi

SIZE="$(du -h "${DUMP_FILE}" | cut -f1)"
echo "[db-backup] OK ${DUMP_FILE} (${SIZE})"
