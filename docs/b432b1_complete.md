# B+4.3.2b-1 Abschluss — Docker-Compose für Self-Hosted-Deployment

**Datum:** 22.04.2026
**Baseline:** `docs/b432b1_baseline.md`
**Architektur-Kontext:** `docs/b432a_deployment_architecture.md`
**Branch:** `claude/beautiful-mendel`

---

## Status

- Backend-Dockerfile: Multi-Stage + Non-root (`appuser`, UID 1000) +
  HEALTHCHECK auf `/api/v1/health`
- Frontend-Dockerfile: Multi-Stage + Next.js-`output: "standalone"` +
  Non-root (`nextjs`, UID 1001) + HEALTHCHECK auf `/`
- `docker-compose.yml`: Postgres 16-alpine + Backend + Frontend, alle
  drei Services orchestriert, Backend wartet auf Postgres-Health
- `.env.example`: alle benötigten Variablen mit Kommentaren, CORS als
  JSON-Array (pydantic-settings-Erwartung)
- `scripts/docker_compose_smoke.sh`: wiederholbarer Smoke-Test mit
  automatischem Cleanup via `trap`
- Lokal verifiziert: alle 3 Services healthy, Alembic-Migration läuft
  durch, Cross-Container-Zugriff (`frontend → backend`) funktioniert

## Image-Größen

| Image | Größe |
|---|---|
| `lvp-backend` (multi-stage) | **429 MB** |
| `lvp-frontend` (standalone) | **156 MB** |
| `postgres:16-alpine` (gepullt) | ~85 MB |
| **Gesamt-Footprint** | **~670 MB** (ohne Volume-Data) |

Zum Vergleich: ein naiver Single-Stage-Build lag bei geschätzt
~700 MB (Backend) + ~500 MB (Frontend) = 1,2 GB. Einsparung durch
Multi-Stage + standalone: ~500 MB.

## Neue / geänderte Dateien

| Datei | Art | Zeilen |
|---|---|---|
| `lv-preisrechner/backend/Dockerfile` | überschrieben (Single → Multi-Stage) | −16 / +76 |
| `lv-preisrechner/frontend/next.config.js` | erweitert um `output: "standalone"` | +6 |
| `lv-preisrechner/frontend/Dockerfile` | neu | 64 |
| `lv-preisrechner/frontend/.dockerignore` | neu | 16 |
| `lv-preisrechner/docker-compose.yml` | neu | 64 |
| `lv-preisrechner/.env.example` | neu | 53 |
| `lv-preisrechner/.dockerignore` | neu (Compose-Root) | 39 |
| `lv-preisrechner/scripts/docker_compose_smoke.sh` | neu (mode 755) | 68 |

## Gefundene und gelöste Stolpersteine

1. **CORS_ORIGINS muss JSON-Array-String sein** — pydantic-settings
   parst Listen nur als JSON, nicht als Komma-String. Im Dockerfile-
   Run-Test crashte der Container beim Boot mit
   `SettingsError: error parsing value for field "cors_origins"`.
   Fix: im `.env.example` klar dokumentiert und in Compose mit
   korrekter Escape-Syntax gesetzt.

2. **Frontend-HEALTHCHECK braucht `127.0.0.1` statt `localhost`** —
   BusyBox-wget in Alpine routet `localhost` über `[::1]` (IPv6),
   Next.js standalone bindet mit `HOSTNAME=0.0.0.0` aber nur IPv4.
   Ergebnis: Container `unhealthy` trotz funktionierendem Extern-
   Curl. Fix: HEALTHCHECK-URL auf `127.0.0.1` gezwungen.

3. **Next.js `output: "standalone"` + Vercel-Kompatibilität** —
   Laut Next.js-Docs und Vercel-Community-Discussion wird das Feld
   von Vercel transparent ignoriert (eigene Build-Pipeline). Keine
   Branch-Logik oder ENV-Switch nötig.

4. **Postgres-Host-Port-Kollision auf Dev-Rechner** — Port 5432
   war durch lokalen Host-Postgres belegt. Lösung: Compose-Postgres
   nur intern (kein Host-Mapping) — Backend erreicht ihn via
   Docker-Network-Hostname `postgres`.

5. **Frontend `public/`-Verzeichnis existiert nicht** —
   Standard-Dockerfile-Template aus Next.js-Doku copiert `public/`,
   das schlug fehl. Entfernt und dokumentiert.

## Vercel / Render-Kompatibilität

- **Backend-Dockerfile** läuft weiterhin auf Render:
  - PORT-ENV-Variable bleibt, CMD-Signatur unverändert
  - `render.yaml` unverändert, kein Breaking-Change
- **Frontend `next.config.js`**:
  - `output: "standalone"` wird von Vercel ignoriert
  - `vercel.json` bleibt funktional, Vercel-Deploy unverändert
- **docker-compose.yml** ist ein **additives** Deployment-Target —
  keine Migration, keine Abkehr vom Render+Vercel-Plan

## Bekannte Follow-ups

### FU-D1 — Smoke-Skript Polling-Logik robuster

`docker compose ps --format json` produzierte in der Polling-
Schleife leeren Output (Formatting-Quirk der verwendeten Docker-
Version 29.4.0). Die curl-Checks am Ende lieferten trotzdem
verlässliche Ergebnisse, aber die Zwischen-Logs zeigen nur
Zeilennummern ohne Service-Status.

Follow-up: auf `docker inspect` per Container-Namen wechseln,
oder `docker compose ps --status running --quiet` nutzen.

### FU-D2 — Multi-Arch-Build-Strategie

Lokal gebaut auf Apple Silicon (arm64), Hetzner läuft x86_64.
Zwei Ansätze:

- **Option a:** `docker buildx build --platform linux/amd64` lokal
  (Cross-Compile via QEMU, langsam, aber unabhängig vom Server)
- **Option b:** Build direkt auf dem Hetzner-Server (per `git pull`
  + `docker compose up --build`)

Entscheidung wird in B+4.3.2c getroffen, sobald klar ist wie der
Deploy-Flow (manuell vs. CI) aussieht.

### FU-D3 — Production-`.env`-Hardening

Aktuelle `.env.example`-Defaults sind Dev-tauglich. Für Production
müssen:
- `SECRET_KEY` via `openssl rand -hex 32` (bereits im
  Kommentar dokumentiert)
- `POSTGRES_PASSWORD` via `openssl rand -base64 24`
- `ANTHROPIC_API_KEY` aus `console.anthropic.com`
- `CORS_ORIGINS` auf echte Frontend-Domain

…manuell gesetzt werden. Ein `scripts/generate_prod_env.sh` könnte
das automatisieren (Follow-up, nicht Teil dieses Blocks).

## Verbleibende Sub-Blöcke bis Pilot-Live

| Block | Inhalt | Blockiert durch |
|---|---|---|
| **B+4.3.2b-2** | Caddyfile für TLS + Reverse-Proxy | Domain-Entscheidung |
| **B+4.3.2c** | Hetzner-Server-Provisioning (CX32, SSH, Firewall, Docker) | — |
| **B+4.3.2d** | Domain + DNS + TLS-Live | Domain-Entscheidung |
| **B+4.3.2e** | Prod-E2E-Smoke gegen Live-URL | B+4.3.2d |

Geschätzter Gesamt-Rest: ~4–6 h Code/Doku + ~2–3 h Manual-Ops
(Hetzner-Account, Domain-DNS).

## Commit-Stack B+4.3.2b-1

```
(Abschluss-Doc folgt)
03892a5 feat(deploy): B+4.3.2b-1 docker-compose for self-hosted deployment
c26debb chore(frontend): B+4.3.2b-1 add Dockerfile for Hetzner deployment
3a60825 chore(backend): B+4.3.2b-1 prepare Dockerfile for Hetzner deployment
3fdb64c docs: B+4.3.2b-1 baseline — review existing Docker infrastructure
```

## Nächster logischer Block

**B+4.3.2c — Hetzner-Server-Provisioning** ist der nächste
kritische Schritt, weil er unabhängig von der Domain-Entscheidung
gestartet werden kann. Parallel kann die Domain-Frage geklärt
werden (welche Domain? bei welchem Registrar? Subdomain-Struktur?
— siehe offene Fragen in `docs/b432a_deployment_architecture.md`).

Alternativ: **B+4.3.2b-2 (Caddyfile)** kann auch vorher laufen,
weil Caddy rein deklarativ ist und Domain-agnostisch als Platzhalter
gebaut werden kann, bis die echte Domain feststeht.

Wenn du willst, kann ich danach direkt mit **B+4.3.2b-2** starten —
oder das hier ist ein natürlicher Break-Point.
