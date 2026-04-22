#!/usr/bin/env bash
#
# B+4.3.2c-1: Docker CE + Compose Plugin via offiziellem Docker-Repo.
# Snap-Version wird NICHT verwendet (inkompatibel mit vielen Compose-
# Features).
#
# Idempotent.
#
# Als root / sudo.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "FEHLT: als root ausfuehren." >&2
    exit 2
fi

echo "=== Schritt 1: alte Docker-Versionen entfernen ==="
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
    apt-get remove -y -qq "$pkg" 2>/dev/null || true
done

echo "=== Schritt 2: Docker GPG-Key + Repo ==="
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
fi

. /etc/os-release
cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable
EOF

echo "=== Schritt 3: Docker + Compose installieren ==="
apt-get update -qq
apt-get install -y -qq \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

echo "=== Schritt 4: daemon.json mit Log-Rotation ==="
# Verhindert, dass Container-Logs die Disk fuellen (haeufige Hetzner-
# Issue bei langlaufenden Services ohne Rotation).
mkdir -p /etc/docker
cat >/etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true
}
EOF

systemctl restart docker
systemctl enable docker

echo "=== Schritt 5: appuser zur docker-Gruppe ==="
if id -u appuser >/dev/null 2>&1; then
    usermod -aG docker appuser
    echo "  appuser ist jetzt in der docker-Gruppe."
    echo "  WICHTIG: appuser muss sich einmal aus- und einloggen, damit die"
    echo "  Gruppenzugehoerigkeit aktiv wird."
else
    echo "  appuser existiert noch nicht — vorher 02_create_user.sh laufen lassen."
    exit 3
fi

echo "=== Schritt 6: Verifikation ==="
docker --version
docker compose version
docker run --rm hello-world >/dev/null 2>&1 \
    && echo "  hello-world-Test erfolgreich" \
    || echo "  WARNUNG: hello-world-Run schlug fehl — Netz/Registry pruefen"

echo ""
echo "=== Fertig ==="
echo "Weiter mit 04_configure_firewall.sh."
