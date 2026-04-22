#!/usr/bin/env bash
#
# B+4.3.2c-1: Legt den Deploy-User `appuser` an (UID 1000, passt zu
# den Dockerfile-UIDs), kopiert den SSH-Key von root, setzt sudo-
# Rechte und bereitet das Deploy-Verzeichnis vor.
#
# Idempotent: mehrfaches Ausfuehren bleibt sicher.
#
# Als root ausfuehren (oder mit sudo).

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "FEHLT: als root ausfuehren." >&2
    exit 2
fi

APP_USER="appuser"
APP_UID="1000"
APP_HOME="/home/${APP_USER}"
DEPLOY_DIR="${APP_HOME}/lvp"

echo "=== Schritt 1: User ${APP_USER} anlegen (falls nicht vorhanden) ==="
if id -u "${APP_USER}" >/dev/null 2>&1; then
    echo "  User ${APP_USER} existiert bereits (UID $(id -u ${APP_USER}))"
else
    # Ubuntu 24.04: useradd mit expliziter UID/GID 1000.
    # 'ubuntu'-Default-User belegt auf Cloud-Images teilweise UID 1000 —
    # in diesem Fall UID 1001 nehmen und im .env dokumentieren.
    if getent passwd 1000 >/dev/null; then
        echo "  WARNUNG: UID 1000 ist belegt durch $(getent passwd 1000 | cut -d: -f1)"
        echo "  Lege ${APP_USER} mit naechster freier UID an."
        useradd --create-home --shell /bin/bash "${APP_USER}"
    else
        useradd --create-home --shell /bin/bash --uid "${APP_UID}" "${APP_USER}"
    fi
    echo "  ${APP_USER} angelegt (UID $(id -u ${APP_USER}))"
fi

echo "=== Schritt 2: SSH-Key uebernehmen ==="
mkdir -p "${APP_HOME}/.ssh"
if [ -f /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys "${APP_HOME}/.ssh/authorized_keys"
    echo "  SSH-Key aus /root/.ssh/authorized_keys kopiert"
else
    echo "  HINWEIS: /root/.ssh/authorized_keys fehlt."
    echo "  SSH-Key manuell in ${APP_HOME}/.ssh/authorized_keys eintragen."
fi
chmod 700 "${APP_HOME}/.ssh"
chmod 600 "${APP_HOME}/.ssh/authorized_keys" 2>/dev/null || true
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/.ssh"

echo "=== Schritt 3: Sudo ohne Passwort (optional, fuer Deploy-Komfort) ==="
# Nur Basics fuer Service-Management + Docker. Kein volles sudo.
cat >/etc/sudoers.d/90-appuser <<EOF
${APP_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart docker, /usr/bin/systemctl status docker, /usr/bin/ufw, /usr/bin/apt-get update
EOF
chmod 440 /etc/sudoers.d/90-appuser

echo "=== Schritt 4: Deploy-Verzeichnis vorbereiten ==="
mkdir -p "${DEPLOY_DIR}"
mkdir -p "${APP_HOME}/backups"
chown -R "${APP_USER}:${APP_USER}" "${DEPLOY_DIR}" "${APP_HOME}/backups"

echo ""
echo "=== Fertig ==="
echo ""
echo "Naechste Schritte:"
echo "  1. Login-Test von deinem lokalen Rechner:"
echo "       ssh ${APP_USER}@<server-ip>"
echo "  2. Weiter auf dem Server mit 03_install_docker.sh."
echo ""
echo "Sicherheits-Hinweis (optional): sobald ${APP_USER} funktioniert,"
echo "kannst du Root-SSH-Login ganz verbieten:"
echo "  sed -i 's|^PermitRootLogin .*|PermitRootLogin no|' /etc/ssh/sshd_config"
echo "  systemctl reload ssh"
