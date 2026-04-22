# B+4.3.2b-1 — Docker-Compose-Baseline

**Stand:** 22.04.2026, vor Implementierung.
**Scope-Erinnerung:** Nur Docker-Paketierung + lokales docker-compose.
Kein Caddy, kein TLS, kein Server-Provisioning.

---

## 1. Ist-Zustand der Docker-Infrastruktur

### Backend — `lv-preisrechner/backend/Dockerfile`

**Status:** vorhanden, funktionsfähig, Render-kompatibel aber generisch.

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```

| Aspekt | Stand |
|---|---|
| Base-Image | `python:3.12-slim` ✓ |
| System-Deps | poppler-utils (PDF-Processing), libpq-dev (Postgres), gcc (Build), curl (für Healthcheck nutzbar) ✓ |
| Dependency-Install | `pip install .` aus pyproject.toml ✓ |
| CMD | `alembic upgrade head && uvicorn …` ✓ (Migrations beim Boot) |
| PORT-Variable | default 8000, per ENV überschreibbar ✓ |
| **Healthcheck (HEALTHCHECK-Directive)** | **fehlt** — gibt's nur auf Compose-Ebene |
| **Non-root User** | **fehlt** — läuft als root |
| **Multi-Stage-Build** | **fehlt** — alles in einem Layer, aber gcc ist Build-Only |
| Render-spezifische Annahmen | **keine** — `PORT` ist standard, Dockerfile ist portabel |

**Backend Health-Endpoint:** `GET /api/v1/health` existiert
(`app/main.py:82`), liefert `{"status":"ok","service":"lv-preisrechner","version":"0.1.0"}`.

**.dockerignore im Backend:** vorhanden, adequat (ignoriert `.venv/`,
`__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`,
`.mypy_cache/`, `data/`, `.env`, `.env.*`, `tests/`, `scripts/`).

### Frontend — kein Dockerfile

**Status:** Vercel-orientiert, kein Docker-Setup.

| Aspekt | Stand |
|---|---|
| Dockerfile | **fehlt** — muss in Phase 3 neu angelegt werden |
| `output: "standalone"` in `next.config.js` | **fehlt** — muss in Phase 3 ergänzt werden (reduziert Runtime-Image von ~500 MB auf ~150 MB) |
| Nebenwirkung auf Vercel | **keine** — Vercel akzeptiert `standalone`-Setting transparent, Vercel-Build läuft weiter |
| `.dockerignore` | **fehlt** — muss angelegt werden (sonst kopiert `node_modules` in Build-Context) |
| Vercel-Konfig (`vercel.json`) | vorhanden, bleibt unangetastet |

### Datenbank — keine Compose-Umgebung

**Status:** keine PostgreSQL-Konfiguration im Repo.

- Keine `docker-compose.yml` im aktiven Projekt (legacy im
  `_archive/cockpit-legacy/`, nicht relevant)
- Backend-Config fällt lokal auf SQLite zurück, in Prod erwartet
  `DATABASE_URL=postgresql://...`
- `DATABASE_URL` wird automatisch von `postgres://` auf
  `postgresql://` normalisiert (`app/core/config.py:62`) — Render-
  Kompatibilität

---

## 2. Änderungsbedarf für Hetzner-Deploy

### Backend-Dockerfile — Anpassungen für Phase 2

| Änderung | Begründung | Risiko |
|---|---|---|
| Multi-Stage-Build (Builder + Runtime) | reduziert Image-Größe (`gcc`, `libpq-dev` gehören nur in Builder); schneller Rebuild bei Code-Änderungen | niedrig — Render kann mit Multi-Stage umgehen |
| Non-root User `app` (UID 1000) | Defense-in-depth, Hetzner-Self-Hosting-Standard | niedrig — Render läuft sowieso privileged, wir brechen keine bestehende Annahme |
| `HEALTHCHECK`-Directive (`curl -f http://localhost:${PORT}/api/v1/health`) | Docker-native Health-Signal statt nur Compose-Level | niedrig |
| Keine sonstigen Render-spezifischen Rückbauten nötig | Dockerfile ist bereits portabel | — |

### Frontend-Dockerfile — Neu in Phase 3

| Komponente | Plan |
|---|---|
| Base | `node:20-alpine` (Builder + Runtime) |
| Multi-Stage | Stage 1 `deps` → npm ci; Stage 2 `builder` → `npm run build`; Stage 3 `runner` → nur standalone |
| Non-root User | `nextjs:nodejs` (UID 1001) |
| Healthcheck | HTTP GET auf `/` (Next.js liefert 200 bei Home-Page) |
| Port | 3000 |
| `next.config.js` Ergänzung | `output: "standalone"` — notwendig für funktionierenden Multi-Stage |

**Wichtig:** `output: "standalone"` ändert das Build-Artefakt, aber
nicht das Rendering-Verhalten. Die Vercel-Deployment-Pipeline
akzeptiert das Feld (Next.js unterstützt beides, Vercel macht intern
eh sein eigenes Standalone-Packaging). Kein Risiko für die
bestehende Vercel-Route.

### `.dockerignore`-Dateien

| Ort | Stand | Aktion |
|---|---|---|
| `lv-preisrechner/backend/.dockerignore` | vorhanden | unverändert |
| `lv-preisrechner/frontend/.dockerignore` | fehlt | **neu anlegen** |
| Repo-Root-`.dockerignore` | fehlt | **neu anlegen** (für `docker compose` Build-Context) |

---

## 3. Environment-Variables-Liste

### Backend (required in Production)

| Key | Typ | Quelle heute | Beschreibung |
|---|---|---|---|
| `APP_ENV` | str | `production` | Umschaltet Dev/Prod-Verhalten |
| `DATABASE_URL` | str | manuell | Postgres-URL (`postgresql://user:pw@host:5432/db`) |
| `ANTHROPIC_API_KEY` | str | Secret | Claude-API |
| `SECRET_KEY` | str | Secret | JWT-Signatur |
| `CORS_ORIGINS` | JSON-String | bspw. `["https://app.example.de"]` | Erlaubte Frontend-Origins |
| `CLAUDE_MODEL_PRIMARY` | str | `claude-sonnet-4-6` | Default |
| `CLAUDE_MODEL_FALLBACK` | str | `claude-opus-4-6` | Fallback |
| `PORT` | int | 8000 | Uvicorn-Port |

### Frontend (required)

| Key | Typ | Beschreibung |
|---|---|---|
| `BACKEND_URL` | URL | Server-Side-Rewrite in `next.config.js` |
| `NEXT_PUBLIC_BACKEND_URL` | URL | Client-Side direct calls in `api.ts` (kann identisch zu `BACKEND_URL` sein) |
| `PORT` | int | default 3000 |

### Compose-Internals (nur für docker-compose)

| Key | Typ | Beschreibung |
|---|---|---|
| `POSTGRES_DB` | str | z. B. `lv_preisrechner` |
| `POSTGRES_USER` | str | z. B. `lvp` |
| `POSTGRES_PASSWORD` | str | starkes Passwort |

---

## 4. Service-Abhängigkeiten

```
          ┌──────────────┐
          │   postgres   │ (healthcheck: pg_isready)
          └──────┬───────┘
                 │ DATABASE_URL (intern: postgres:5432)
                 ▼
          ┌──────────────┐
          │   backend    │ (healthcheck: curl /api/v1/health)
          │  port 8000   │
          └──────┬───────┘
                 │ BACKEND_URL (intern: http://backend:8000)
                 ▼
          ┌──────────────┐
          │  frontend    │ (healthcheck: curl /)
          │  port 3000   │
          └──────────────┘
```

**Port-Mapping lokal (für Phase 4):**

- Postgres: intern 5432, nicht exposed (optional `127.0.0.1:5432:5432`
  für lokale Admin-Tools)
- Backend: `127.0.0.1:8000:8000` (nur localhost, später Caddy davor)
- Frontend: `127.0.0.1:3000:3000` (nur localhost, später Caddy davor)

Bei lokalen Port-Konflikten (z. B. Dev-Server läuft auf 3100 aus
`.claude/launch.json`, Backend-Dev auf 8100): Docker-Compose-Ports
sind 3000/8000 und damit frei.

---

## 5. Phasen-Plan (Reminder)

| Phase | Inhalt | Zeit |
|---|---|---|
| 1 | **diese Baseline-Doc** | 15 min ✓ |
| 2 | Backend-Dockerfile Multi-Stage + Non-root + HEALTHCHECK | 30 min |
| 3 | Frontend-Dockerfile (neu) + `next.config` standalone | 40 min |
| 4 | `docker-compose.yml` + Root `.env.example` + `.dockerignore` + lokaler Build-Test | 60 min |
| — | (Docs + Push) | später in Phase 5 oder separat |

---

## 6. Autonome Entscheidungen (dokumentiert für die nächsten Phasen)

- **Postgres-Version:** `postgres:16-alpine` (Alpine für Size,
  v16 als aktuelle Stable; Backend nutzt keine v17-Features)
- **Node-Version:** `node:20-alpine` (Next.js 14 offiziell
  unterstützt)
- **Image-Tags:** nur `latest` für lokalen Build; Tags für Prod
  kommen erst wenn Registry-Push dazu kommt (nicht Teil dieses
  Blocks)
- **Kein Redis** — Backend nutzt es nicht (kein Import, kein
  Queue-System)
- **Volume-Naming:** `lvp_postgres_data` (Präfix für Collision mit
  anderen Projekten)

---

## 7. Offene Risiken

| Risiko | Wahrscheinlichkeit | Gegenmassnahme |
|---|---|---|
| `next.config.js` `output: standalone` bricht Vercel-Build | niedrig — Next.js 14 unterstützt das offiziell, Vercel akzeptiert | vor Phase 3-Commit Vercel-Docs prüfen |
| Backend `pip install .` langsam bei Image-Rebuilds | mittel | Multi-Stage mit separatem dependency-Layer |
| Docker-Compose-Ports lokal belegt | niedrig (3000/8000 unüblich für Dev) | STOPP-Regel aus Prompt greift |
| Alembic-Migrationen bei frischem Postgres laufen nicht durch | niedrig — sie laufen bereits in dev grün | Healthcheck wartet auf Backend-Ready, Compose `depends_on.healthy` |

---

**Status:** STOPP 1. Warte auf Freigabe für Phase 2 (Backend-
Dockerfile).
