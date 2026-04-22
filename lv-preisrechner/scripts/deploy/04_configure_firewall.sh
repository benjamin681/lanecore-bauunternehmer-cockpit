#!/usr/bin/env bash
#
# B+4.3.2c-1: ufw als zweite Firewall-Schicht (Hetzner Cloud-Firewall
# ist die erste, siehe Runbook §1.2).
#
# Idempotent — mehrfaches Ausfuehren ist sicher.
#
# Als root / sudo.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "FEHLT: als root ausfuehren." >&2
    exit 2
fi

if ! command -v ufw >/dev/null 2>&1; then
    echo "FEHLT: ufw ist nicht installiert. Erst 01_initial_setup.sh laufen lassen." >&2
    exit 3
fi

echo "=== Schritt 1: Default-Policies ==="
ufw --force default deny incoming
ufw --force default allow outgoing

echo "=== Schritt 2: SSH (Port 22) ==="
ufw allow 22/tcp comment 'SSH'

echo "=== Schritt 3: HTTP (Port 80) ==="
# Port 80 bleibt offen, auch nach TLS-Setup — Caddy nutzt ihn fuer
# Let's Encrypt ACME HTTP-01 Challenges und fuer http -> https Redirect.
ufw allow 80/tcp comment 'HTTP / ACME / Redirect'

echo "=== Schritt 4: HTTPS (Port 443) ==="
ufw allow 443/tcp comment 'HTTPS'

echo "=== Schritt 5: ufw aktivieren ==="
# --force bestaetigt die Warnung dass SSH-Sessions abbrechen koennten.
# Weil 22/tcp in Schritt 2 allowed ist, sollte das aber nicht passieren.
ufw --force enable

echo ""
echo "=== Verifikation ==="
ufw status verbose

echo ""
echo "=== Fertig ==="
echo "Weiter mit Repo-Clone + 05_deploy_app.sh als appuser."
