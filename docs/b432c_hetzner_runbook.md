# B+4.3.2c — Hetzner-Provisioning-Runbook

**Stand:** 22.04.2026
**Zweck:** Schritt-für-Schritt-Anleitung für einen frischen Hetzner-
Cloud-Server, der den LV-Preisrechner-Stack (Postgres + Backend +
Frontend, aus B+4.3.2b-1) in Produktion bedient. Optional mit Caddy
als Reverse-Proxy (kommt in B+4.3.2b-2).

**Scope dieses Doks:** nur Provisioning + erster Deploy. TLS/Domain-
Setup folgt separat. Dieses Runbook liefert einen funktionierenden
Stack auf einem gehärteten Server, erreichbar über die öffentliche
IP unter Port 80 (TLS später).

**Voraussetzungen:**
- Benjamin hat / erstellt einen Hetzner-Cloud-Account
  (accounts.hetzner.com)
- Ein GitHub-Deploy-Key oder Personal-Access-Token für den
  privaten Klon (falls das Repo private ist)
- `ANTHROPIC_API_KEY` aus console.anthropic.com

**Ausführungszeit (realistisch, mit Pausen):**
- Server-Anlage + SSH-Key + erster Login: 10 min
- Skripte 01–04 (Hardening/Firewall/Docker): 15 min
- Skripte 05 (Deploy): 10–15 min
- Verifikation: 5–10 min
- **Gesamt: 40–50 min** für einen Durchlauf

---

## 1. Server-Anlage im Hetzner-Dashboard

### 1.1 Server-Spezifikation (empfohlen für Pilot)

| Option | Pflicht | Wert |
|---|---|---|
| Type | ja | **CX32** (4 vCPU, 8 GB RAM, 80 GB SSD) |
| OS | ja | **Ubuntu 24.04 LTS** |
| Location | ja | **Nürnberg (nbg1)** oder **Falkenstein (fsn1)** — DSGVO |
| Firewall | ja | Neue Cloud-Firewall anlegen (siehe §1.2) |
| Backups | empfohlen | **aktivieren** (+20 % = +1,33 €/Monat) |
| IPv4 | empfohlen | **ja** (+0,60 €/Monat, sonst nur IPv6) |
| SSH Key | ja | Dein Public-Key hochladen (siehe §2) |
| Name | frei | z. B. `lvp-prod-1` |

**Monatliche Kosten (Pilot, Stand 04/2026):** ca. **8–9 €** (CX32 +
Backups + IPv4).

### 1.2 Hetzner Cloud-Firewall (erste Verteidigungslinie)

**Defense-in-Depth-Strategie:** Cloud-Firewall als erste Schicht
**plus** `ufw` auf dem Server als zweite. Wenn eine Schicht
Fehlkonfiguration hat, fängt die andere ab.

**Cloud-Firewall-Regeln:**

| Direction | Protocol | Port | Source | Beschreibung |
|---|---|---|---|---|
| Inbound | TCP | 22 | `0.0.0.0/0`, `::/0` | SSH (später optional auf Benjamin-IP beschränken) |
| Inbound | TCP | 80 | `0.0.0.0/0`, `::/0` | HTTP (für Let's Encrypt-ACME) |
| Inbound | TCP | 443 | `0.0.0.0/0`, `::/0` | HTTPS (nach TLS-Setup aktiv) |
| Outbound | * | * | `0.0.0.0/0` | alles erlaubt (Updates, Anthropic-API) |

### 1.3 Alternative Server-Größen (für späteres Scaling)

| Type | vCPU / RAM / SSD | €/Monat | Einsatz |
|---|---|---|---|
| CX22 | 2 / 4 GB / 40 GB | ~4 | zu klein für PDF-Processing + Postgres |
| **CX32** | **4 / 8 GB / 80 GB** | **~7** | **Pilot-Default** |
| CX42 | 8 / 16 GB / 160 GB | ~15 | 5–10 parallele Tenant |
| CX52 | 16 / 32 GB / 320 GB | ~30 | Enterprise-Rollout |

---

## 2. SSH-Key-Setup

### 2.1 Key generieren (lokal, einmal)

```bash
# Falls noch kein SSH-Key:
ssh-keygen -t ed25519 -C "benjamin@lanecore" -f ~/.ssh/lvp_hetzner_ed25519
# Passphrase setzen (empfohlen)
```

### 2.2 Public-Key in Hetzner hochladen

`~/.ssh/lvp_hetzner_ed25519.pub` im Hetzner-Dashboard →
**Security** → **SSH Keys** → **Add SSH key**.

### 2.3 SSH-Config lokal (optional, komfortabel)

```bash
# ~/.ssh/config
Host lvp-prod
    HostName <hetzner-ip>
    User root
    IdentityFile ~/.ssh/lvp_hetzner_ed25519
```

Danach: `ssh lvp-prod` statt `ssh -i ... root@<ip>`.

---

## 3. Initial-Login + System-Hardening

Nach Server-Anlage steht die IP im Hetzner-Dashboard.

### 3.1 Erster Login

```bash
ssh root@<server-ip>
# oder: ssh lvp-prod
```

**Host-Key-Warnung:** erwartet beim ersten Mal. Mit `yes` bestätigen
und im SSH-Known-Hosts verankern.

### 3.2 Skript 01 ausführen

Lade das Skript aus dem Repo (das Repo ist noch nicht geklont,
deshalb per `curl`):

```bash
curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/lv-preisrechner/scripts/deploy/01_initial_setup.sh -o 01_initial_setup.sh
# Review lohnt:
less 01_initial_setup.sh
chmod +x 01_initial_setup.sh
./01_initial_setup.sh
```

Alternativ: Skript per `scp` hochschieben, wenn das Repo privat
ist und keinen Deploy-Key am Server hat.

**Was das Skript macht (siehe §4):**
1. `apt update && apt upgrade`
2. Essentials (`git`, `curl`, `ufw`, `fail2ban`, `unattended-upgrades`)
3. Timezone auf `Europe/Berlin`
4. SSH-Hardening (Password off, Root prohibit-password)
5. `unattended-upgrades` für Security-Updates aktivieren
6. `fail2ban` starten

**Reboot-Bedarf:** wahrscheinlich ja, wenn Kernel-Update kam. Das
Skript prüft `/var/run/reboot-required` und meldet es.

---

## 4. User-Setup (non-root `appuser`)

### 4.1 Skript 02 ausführen

```bash
# Als root:
./02_create_user.sh
```

**Was das Skript macht:**
1. `appuser` anlegen (UID **1000**, passend zu den Dockerfile-UIDs)
2. SSH-Key von `root` kopieren (`~/.ssh/authorized_keys`)
3. Optional: `sudo`-Rechte ohne Passwort (falls gewünscht)
4. `/home/appuser/app/` anlegen (Deploy-Target)

### 4.2 Ab jetzt nur noch als `appuser` einloggen

```bash
# lokal, neu einloggen:
ssh appuser@<server-ip>
```

SSH-Root-Login bleibt ab jetzt verschlossen (`PermitRootLogin
prohibit-password` aus Skript 01 erlaubt nur Key, nicht Passwort;
Skript 02 dokumentiert die Empfehlung, Root-Login ganz zu deaktivieren
sobald verifiziert ist dass `appuser` funktioniert).

---

## 5. Firewall (ufw als zweite Schicht)

### 5.1 Skript 04 ausführen

```bash
# Als appuser mit sudo ODER als root:
sudo ./04_configure_firewall.sh
```

**Was das Skript macht:**
1. `ufw default deny incoming`
2. `ufw default allow outgoing`
3. `ufw allow 22/tcp` (SSH)
4. `ufw allow 80/tcp` (HTTP, für Let's Encrypt + Caddy später)
5. `ufw allow 443/tcp` (HTTPS)
6. `ufw enable` (mit `--force`, damit keine SSH-Session bricht)
7. `ufw status verbose` zur Verifikation

**Warnung:** Skript 04 **muss** erst ausgeführt werden, nachdem
Skript 01 gelaufen ist (ufw installiert). Sonst Fehler.

---

## 6. Docker-Install

### 6.1 Skript 03 ausführen

```bash
sudo ./03_install_docker.sh
```

**Was das Skript macht:**
1. Docker-CE via offiziellem Repo (keine Ubuntu-snap-Version)
2. Docker-Compose-Plugin
3. `appuser` zur `docker`-Gruppe hinzufügen
4. `/etc/docker/daemon.json` mit Log-Rotation (max 3 Dateien à 10 MB)
5. Docker-Service starten + enable
6. Verifikation: `docker version`, `docker compose version`

**Nach Install:** User-Session neu einloggen, damit `docker`-Gruppe
greift (`sudo usermod -aG docker appuser` braucht Logout/Login).

---

## 7. Repository-Pull + `.env`-Setup

### 7.1 Repo klonen

Als `appuser`:

```bash
cd ~
git clone https://github.com/<org>/<repo>.git lvp
cd lvp/lv-preisrechner
```

Falls das Repo **privat** ist: Deploy-Key oder HTTPS-Token.

### 7.2 `.env` aus Template

```bash
cp .env.production.example .env
# Editieren und echte Werte eintragen:
nano .env
```

**Pflichtfelder füllen** (aus `.env.production.example` ersichtlich):
- `POSTGRES_PASSWORD` mit `openssl rand -base64 24`
- `SECRET_KEY` mit `openssl rand -hex 32`
- `ANTHROPIC_API_KEY` aus console.anthropic.com
- `CORS_ORIGINS` auf die finale Frontend-URL (vorerst die Server-IP,
  nach TLS-Setup die Domain)

**Permissions hart setzen:**

```bash
chmod 600 .env
```

---

## 8. Erster Deploy via `docker-compose`

### 8.1 Skript 05 ausführen

```bash
./scripts/deploy/05_deploy_app.sh
```

**Was das Skript macht:**
1. `docker compose pull` (postgres-Image)
2. `docker compose build` (backend + frontend)
3. `docker compose up -d`
4. 30 s warten
5. Health-Checks: `curl` auf Backend und Frontend (intern)
6. `docker compose ps` zur Verifikation

**Erwartung:**
- Postgres → **healthy** nach 10–15 s
- Backend → nach Alembic-Migration uvicorn up (30–40 s)
- Frontend → Next.js standalone bootet (5–10 s)

### 8.2 Manuelle Verifikation von außen

Temporär ist nur Port 80 offen (HTTP). Direkt auf die Container-Ports
(8000/3000) wird aus Sicherheitsgründen **nicht** von außen
zugegriffen — Compose bindet sie nur auf `127.0.0.1`.

Das heißt: bis Caddy da ist (B+4.3.2b-2), werden Smoke-Tests **per
SSH-Tunnel** gemacht:

```bash
# Lokaler Terminal:
ssh -L 8000:127.0.0.1:8000 -L 3000:127.0.0.1:3000 appuser@<server-ip>
# Dann im Browser auf http://localhost:8000/api/v1/health
# und http://localhost:3000/
```

---

## 9. Verifikation + Troubleshooting

### 9.1 Erwarteter gesunder Zustand

```bash
docker compose ps
# Alle drei: State "running", Health "healthy"
```

```bash
# Alle Logs ansehen:
docker compose logs -f --tail 50

# Einzelner Service:
docker compose logs backend -f
```

### 9.2 Häufige Probleme

| Symptom | Ursache | Fix |
|---|---|---|
| Backend `unhealthy` | `DATABASE_URL` falsch / Postgres noch nicht ready | `docker compose logs postgres` prüfen; Migration lief evtl. noch |
| Frontend `unhealthy` | `HOSTNAME`/`PORT` nicht gesetzt | `.env` auf Compose-Defaults prüfen |
| `CORS_ORIGINS` Parse-Error | nicht als JSON-Array | `.env`: `CORS_ORIGINS=["https://..."]` (mit Array-Brackets) |
| `docker compose build` langsam (>5 min) | Image-Pull / npm install | einmaliger Build, ab Commit-2 cached |
| Port 80 von außen nicht erreichbar | ufw/Cloud-Firewall | `sudo ufw status`; Hetzner-Dashboard prüfen |

### 9.3 Log-Locations

| Service | Log |
|---|---|
| Docker-Container | `docker compose logs <service>` |
| System | `journalctl -u docker -f` |
| SSH-Attacks | `journalctl -u fail2ban -f` |
| System-Updates | `/var/log/unattended-upgrades/unattended-upgrades.log` |

---

## 10. Backup

### 10.1 Hetzner Cloud-Backups (automatisch)

Wenn in §1.1 **aktiviert**: Hetzner macht tägliche VM-Snapshots
(7-Tage-Retention, inkl. Disk-Image + Postgres-Volume).

### 10.2 Zusätzlicher Postgres-Dump (Script)

Das Skript `scripts/deploy/backup_postgres.sh` macht täglich einen
`pg_dump` in `/home/appuser/backups/` mit 14-Tage-Retention.

**Cron-Install (einmalig):**

```bash
# Als appuser:
crontab -e
# Zeile einfügen:
0 2 * * * /home/appuser/lvp/lv-preisrechner/scripts/deploy/backup_postgres.sh >> /home/appuser/backups/backup.log 2>&1
```

Läuft 02:00 Uhr nachts. Retention 14 Tage (deletes älter Dumps
automatisch).

### 10.3 Off-Server-Backup (Follow-up)

Aktuell liegen Dumps nur lokal auf dem Server. Für echte
Disaster-Recovery: sync nach Hetzner Storage Box oder extern (S3,
Backblaze B2). Separater Block, nicht Teil von B+4.3.2c-1.

---

## 11. Rollback

### 11.1 Code-Rollback (kein DB-Schema-Break)

Als `appuser` im Repo-Verzeichnis:

```bash
docker compose down
git fetch origin
git checkout <previous-commit-sha>
docker compose up -d --build
docker compose logs -f backend  # Prüfen dass alles bootet
```

### 11.2 DB-Rollback (nur bei Migration-Issue)

Alembic-Migrations sollten reversibel sein (`downgrade()`
implementiert). Manueller Rollback:

```bash
docker compose exec backend alembic downgrade -1
# Oder auf spezifische Revision:
docker compose exec backend alembic downgrade <revision>
```

**Bei Daten-Korruption:** Hetzner Cloud Snapshot zurückspielen
(§10.1) oder aus lokalem `pg_dump` (§10.2):

```bash
docker compose exec -T postgres psql -U lvpuser lvpreisrechner < /home/appuser/backups/dump-YYYY-MM-DD.sql
```

---

## 12. Nach-dem-Runbook-Checkliste

- [ ] Server läuft, `docker compose ps` zeigt alle 3 Services healthy
- [ ] SSH-Tunnel-Smoke: Backend `/api/v1/health` antwortet 200
- [ ] SSH-Tunnel-Smoke: Frontend-Landing liefert 200
- [ ] `.env` hat `chmod 600`
- [ ] Cron-Entry für `backup_postgres.sh` eingetragen
- [ ] Hetzner Cloud Backups aktiviert (falls bestellt)
- [ ] fail2ban läuft (`sudo fail2ban-client status`)
- [ ] `ufw status` zeigt 22/80/443 allow
- [ ] Non-Root-Login mit `appuser` funktioniert
- [ ] Root-SSH-Login kann jetzt deaktiviert werden (optional,
      empfohlen)

**Nächster Sub-Block:** §13 TLS + Domain aktivieren.

---

## 13. TLS + Domain aktivieren (nach Caddy-Integration)

Ab Commit `feat(deploy): add Caddy reverse proxy with Let's Encrypt TLS`
ist der Caddy-Service Teil des Stacks. Port 80/443 sind public, 8000/3000
nur intern im Docker-Netzwerk. Workflow:

**(a) DNS-Eintrag setzen.** A-Record der gewählten Subdomain auf die
Server-IP (z. B. `kalkulane.lanecore-ai.de` → `178.104.229.191`) beim
Registrar (Squarespace, Hetzner DNS, Cloudflare, …). Propagation ~5–30 min,
prüfbar mit `dig +short <domain>`.

**(b) Caddyfile auf die Domain anpassen.** Im Host-Block die Domain
eintragen und unter `{ email ... }` die ACME-Kontakt-Adresse:

```
{
    email admin@deine-domain.de
}

deine-domain.de {
    encode zstd gzip
    @api path /api/*
    reverse_proxy @api backend:8000
    reverse_proxy frontend:3000
    header { ... }
    request_body { max_size 50MB }
}
```

**(c) `.env` auf https umstellen** (auf dem Server, als `appuser`):

```
CORS_ORIGINS=["https://deine-domain.de"]
NEXT_PUBLIC_BACKEND_URL=https://deine-domain.de
```

`BACKEND_URL=http://backend:8000` bleibt unverändert — das ist der
interne Docker-Hostname.

**(d) Rebuild + Restart:**

```bash
docker compose down
docker compose build --no-cache frontend   # bake neue Public-URL ein
docker compose up -d
```

`--no-cache frontend` ist wichtig, weil `NEXT_PUBLIC_BACKEND_URL` zur
Build-Zeit in die JS-Bundles eingefroren wird.

**(e) Zertifikat holt Caddy automatisch** via Let's Encrypt TLS-ALPN-01
(Port 443). Dauer 5–20 s. Logs: `docker compose logs caddy`. Auto-Renewal
läuft eigenständig (alle 60 Tage).

**(f) Health-Check:**

```bash
curl -I https://deine-domain.de/
# → HTTP/2 200, strict-transport-security header sichtbar
curl -fsS https://deine-domain.de/api/v1/health
# → {"status":"ok","service":"lv-preisrechner",...}
```

Ab hier kein SSH-Tunnel mehr nötig, der Stack ist live.
