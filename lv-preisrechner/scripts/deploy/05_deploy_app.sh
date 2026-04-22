#!/usr/bin/env bash
#
# B+4.3.2c-1: Deploy-Schritt. Als `appuser` im Compose-Verzeichnis
# ausfuehren (lvp/lv-preisrechner/).
#
# Voraussetzungen (werden im Skript geprueft):
#   - docker + docker compose installiert (via 03_install_docker.sh)
#   - User ist in der docker-Gruppe
#   - ./docker-compose.yml vorhanden
#   - ./.env vorhanden (aus .env.production.example kopiert + gefuellt)
#
# Idempotent: kann zum Redeployen beliebig oft laufen.

set -euo pipefail

# -----------------------------------------------------------------------
# Pre-Checks
# -----------------------------------------------------------------------
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
# Jetzt sind wir in lv-preisrechner/

if [ ! -f docker-compose.yml ]; then
    echo "FEHLT: docker-compose.yml — bist du im lv-preisrechner/-Verzeichnis?" >&2
    exit 2
fi

if [ ! -f .env ]; then
    echo "FEHLT: .env" >&2
    echo "  Kopiere .env.production.example nach .env und trage die Secrets ein:" >&2
    echo "    cp .env.production.example .env" >&2
    echo "    nano .env" >&2
    echo "    chmod 600 .env" >&2
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "FEHLT: docker — erst 03_install_docker.sh laufen lassen." >&2
    exit 3
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "FEHLT: docker compose plugin." >&2
    exit 3
fi

if ! docker info >/dev/null 2>&1; then
    echo "FEHLT: docker-Daemon nicht erreichbar — bist du in der docker-Gruppe?" >&2
    echo "  Neu einloggen und erneut versuchen (Gruppenzugehoerigkeit aktiviert sich erst dann)." >&2
    exit 3
fi

# -----------------------------------------------------------------------
# Deploy
# -----------------------------------------------------------------------
echo "=== Schritt 1: Image-Pulls (postgres) ==="
docker compose pull

echo "=== Schritt 2: Build Backend + Frontend ==="
docker compose build

echo "=== Schritt 3: Services starten ==="
docker compose up -d

echo "=== Schritt 4: Warte auf Health (max 90 s) ==="
for i in $(seq 1 18); do
    sleep 5
    all_ok=$(docker compose ps --format json 2>/dev/null | python3 -c '
import json, sys
services = []
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try: obj = json.loads(line)
    except Exception: continue
    name = obj.get("Service", "?")
    health = obj.get("Health", "")
    state = obj.get("State", "?")
    ok = (health == "healthy") or (state == "running" and not health)
    services.append((name, state, health or "-", ok))
ok_count = sum(1 for s in services if s[3])
print(f"{ok_count}/{len(services)}|" + " ".join(f"{n}:{s}/{h}" for n,s,h,_ in services))
' 2>/dev/null || echo "0/0|parse-error")
    echo "  [${i}] ${all_ok}"
    if echo "${all_ok}" | grep -qE '^3/3\|'; then
        break
    fi
done

echo ""
echo "=== Schritt 5: Compose-Status ==="
docker compose ps

echo ""
echo "=== Schritt 6: Health-Checks (via 127.0.0.1) ==="
echo -n "Backend: "
curl -fsS http://127.0.0.1:8000/api/v1/health || echo "FAIL"
echo ""
echo -n "Frontend: "
curl -fsSIo /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:3000/ || echo "FAIL"

echo ""
echo "=== Fertig ==="
echo ""
echo "Bis Caddy + TLS eingerichtet sind, ist der Stack nur per SSH-Tunnel"
echo "erreichbar:"
echo "  Lokal: ssh -L 8000:127.0.0.1:8000 -L 3000:127.0.0.1:3000 appuser@<server-ip>"
echo "  Dann: http://localhost:3000 (Frontend) / http://localhost:8000 (Backend)"
echo ""
echo "Logs live: docker compose logs -f"
echo "Stoppen:   docker compose down"
