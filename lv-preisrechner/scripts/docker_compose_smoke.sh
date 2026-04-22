#!/usr/bin/env bash
#
# B+4.3.2b-1: Lokaler Smoke-Test des docker-compose-Stacks.
#
# Baut alle drei Services frisch, startet sie, prueft Health-Endpoints
# aus Host- und Container-Sicht, raeumt am Ende auf. Exit 0 bei Erfolg.
#
# Voraussetzung: lv-preisrechner/.env existiert (aus .env.example kopiert
# und mit SECRET_KEY + ANTHROPIC_API_KEY befuellt).
#
# Usage (vom Repo-Worktree-Root):
#   ./lv-preisrechner/scripts/docker_compose_smoke.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${COMPOSE_DIR}"

if [ ! -f .env ]; then
    echo "FEHLT: ${COMPOSE_DIR}/.env — bitte vorher 'cp .env.example .env' und ausfuellen." >&2
    exit 2
fi

cleanup() {
    echo "--- Cleanup ---"
    docker compose down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "--- Build + Start ---"
docker compose up -d --build

echo "--- Warte auf Health (max 90 s) ---"
for i in $(seq 1 18); do
    sleep 5
    status=$(docker compose ps --format json | python3 -c '
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try: obj = json.loads(line)
    except Exception: continue
    print(f"{obj.get(\"Service\",\"?\")}:{obj.get(\"Health\", obj.get(\"State\",\"?\"))}")' 2>/dev/null || true)
    echo "  [${i}] ${status}"
    if echo "${status}" | grep -qE "backend:(healthy|running)" \
        && echo "${status}" | grep -qE "postgres:(healthy|running)" \
        && echo "${status}" | grep -qE "frontend:(healthy|running)"; then
        # Prueft nur dass alle drei Services irgendwie up sind; die
        # richtigen Health-Checks kommen als echte curl-Tests danach.
        break
    fi
done

echo "--- Backend Health ---"
curl -fsS http://localhost:8000/api/v1/health
echo ""

echo "--- Frontend reachable ---"
curl -fsSIo /dev/null -w "HTTP %{http_code}\n" http://localhost:3000/

echo "--- Backend reachable from frontend-container ---"
docker compose exec -T frontend wget -qO- http://backend:8000/api/v1/health
echo ""

echo ""
echo "Smoke test passed."
