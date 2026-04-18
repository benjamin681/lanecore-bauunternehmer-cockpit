#!/usr/bin/env bash
# Startet Backend + Frontend im Entwicklungs-Modus.
# Erwartet: ANTHROPIC_API_KEY als ENV-Var gesetzt.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Backend ---------------------------------------------------------------
(
  cd backend
  if [ ! -d .venv ]; then
    echo "[setup] Lege Python venv an…"
    python3 -m venv .venv
  fi
  source .venv/bin/activate
  pip install -q -e ".[dev]"
  python -m app.core.database
  exec uvicorn app.main:app --reload --port 8100 --host 127.0.0.1
) &
BACKEND_PID=$!

# --- Frontend --------------------------------------------------------------
(
  cd frontend
  if [ ! -d node_modules ]; then
    echo "[setup] Lege node_modules an…"
    npm install
  fi
  exec npm run dev
) &
FRONTEND_PID=$!

cleanup() {
  echo "Stoppe Backend ($BACKEND_PID) und Frontend ($FRONTEND_PID)…"
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "  Backend:  http://127.0.0.1:8100/api/v1/health"
echo "  Frontend: http://127.0.0.1:3100"
echo ""
echo "  STRG+C zum Beenden."
echo ""

wait
