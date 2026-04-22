#!/usr/bin/env bash
#
# B+4.3.2c-1: Initial-Setup eines frischen Hetzner-Cloud-Servers
# (Ubuntu 24.04 LTS). Als root ausfuehren.
#
# Idempotent: mehrfach ausfuehren aendert nichts, das schon gemacht ist.
#
# Was dieses Skript macht:
#   1. apt update + upgrade
#   2. Essentials installieren (git curl ufw fail2ban unattended-upgrades)
#   3. Timezone auf Europe/Berlin
#   4. SSH-Hardening (PasswordAuth off, Root prohibit-password)
#   5. unattended-upgrades aktivieren (Security-Updates automatisch)
#   6. fail2ban starten
#
# Reboot erforderlich, falls Kernel-Update kam. Skript meldet das am Ende.

set -euo pipefail

# -----------------------------------------------------------------------
# 0. Pre-Check
# -----------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    echo "FEHLT: als root ausfuehren (oder mit sudo)." >&2
    exit 2
fi

echo "=== Schritt 1: apt update + upgrade ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

echo "=== Schritt 2: Essentials installieren ==="
apt-get install -y -qq \
    git \
    curl \
    wget \
    ufw \
    fail2ban \
    unattended-upgrades \
    apt-listchanges \
    ca-certificates \
    gnupg \
    lsb-release \
    htop \
    nano

echo "=== Schritt 3: Timezone ==="
timedatectl set-timezone Europe/Berlin
timedatectl | head -3

echo "=== Schritt 4: SSH-Hardening ==="
# /etc/ssh/sshd_config anpassen — aber idempotent.
SSHD_CONFIG=/etc/ssh/sshd_config
# Backup einmalig
if [ ! -f "${SSHD_CONFIG}.bak" ]; then
    cp "${SSHD_CONFIG}" "${SSHD_CONFIG}.bak"
fi

# Passwort-Auth abschalten
sed -i \
    -e 's|^#*PasswordAuthentication .*|PasswordAuthentication no|' \
    -e 's|^#*PermitRootLogin .*|PermitRootLogin prohibit-password|' \
    -e 's|^#*PubkeyAuthentication .*|PubkeyAuthentication yes|' \
    "${SSHD_CONFIG}"

# Sicherstellen dass die Zeilen ueberhaupt existieren (Idempotenz)
grep -qE '^PasswordAuthentication no$' "${SSHD_CONFIG}" \
    || echo "PasswordAuthentication no" >> "${SSHD_CONFIG}"
grep -qE '^PermitRootLogin prohibit-password$' "${SSHD_CONFIG}" \
    || echo "PermitRootLogin prohibit-password" >> "${SSHD_CONFIG}"

# SSH sauber neu laden — NICHT restart (bricht die Session)
systemctl reload ssh

echo "=== Schritt 5: unattended-upgrades aktivieren ==="
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# Nur Security-Updates automatisch ziehen
cat >/etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF

systemctl enable --now unattended-upgrades

echo "=== Schritt 6: fail2ban ==="
# Minimal jail.local fuer SSH
cat >/etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
EOF

systemctl enable --now fail2ban
systemctl reload fail2ban || true

echo ""
echo "=== Fertig ==="
if [ -f /var/run/reboot-required ]; then
    echo "HINWEIS: Reboot erforderlich (Kernel-Update). Jetzt 'reboot' ausfuehren."
else
    echo "Kein Reboot noetig. Weiter mit 02_create_user.sh."
fi
