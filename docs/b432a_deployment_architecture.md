# B+4.3.2a — Deployment-Architektur: Kontext & Plan

**Stand:** 22.04.2026
**Zweck:** Vor-Analyse + Weichenstellung. Kein Code, kein Commit.
**Vorab-Warnung:** Der User-Prompt skizziert Hetzner. Das Repo hat
aber **bereits** eine komplette Render + Vercel-Strategie. Die
Diskrepanz muss vor jeglicher Implementierung aufgelöst werden.

---

## 1. Ist-Zustand im Repo

### Vorhandene Deployment-Artefakte

| Datei | Zweck |
|---|---|
| `lv-preisrechner/DEPLOYMENT.md` | **Vollständige Deploy-Anleitung** für Render + Vercel, inklusive Blueprint-Apply, Secrets, Custom Domains, Kosten-Tabelle |
| `lv-preisrechner/render.yaml` | Render-Blueprint: 1 Web-Service (Backend, Docker-Build) + 1 Postgres-DB |
| `lv-preisrechner/backend/Dockerfile` | Python 3.12-slim, poppler-utils, uvicorn, `alembic upgrade head` im CMD |
| `lv-preisrechner/frontend/vercel.json` | Framework=Next.js, Region `fra1` (Frankfurt) |
| `lv-preisrechner/frontend/next.config.js` | Kommentare dokumentieren `BACKEND_URL=https://lv-preisrechner-backend.onrender.com` als Vercel-Prod-Config |
| `lv-preisrechner/backend/.env.example` | Enthält `SECRET_KEY`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL_PRIMARY/FALLBACK` |
| `.env.example` (root) | Kanzlei-LLM / Cockpit-Legacy — enthält S3/R2-Keys, NICHT LV-Preisrechner-spezifisch |

### Deploy-Ziel laut bestehendem Plan

- **Backend:** Render.com (Docker-Build)
- **Frontend:** Vercel (Next.js-Default, Region Frankfurt)
- **Datenbank:** Render Postgres (Managed, im Blueprint verknüpft)
- **Secrets:** Render Environment Variables (SECRET_KEY auto-generated)
- **TLS:** automatisch via Render und Vercel
- **Custom Domain:** optional, beschrieben aber nicht live
- **Monitoring:** Render Logs + Vercel Runtime Logs (basic)
- **Kosten-Plan:** 0 €/Monat Free-Tier für Pilot; 14 €/Monat Production
  (Render Starter Backend + Starter DB)

### Was **fehlt** trotz bestehendem Plan

- **Live-Deploy-Status unklar:** Die DEPLOYMENT.md liest sich wie
  eine How-To, nicht wie eine Post-Mortem. Es ist nicht klar, ob
  der Blueprint bereits auf Render applied wurde.
- **Kein Frontend-Dockerfile** — wird auf Vercel auch nicht
  gebraucht, nur wenn Eigenbau-Hosting gewünscht.
- **Keine Backup-Strategie** dokumentiert außer dem impliziten
  Render-DB-Backup (Starter-Plan: Daily-Backups inklusive).
- **Kein externes Monitoring** (Sentry / Uptime-Kuma / Better-Stack).
- **Keine Pre-Deploy-Checkliste** für den ersten echten Deploy.
- **Keine CI/CD** — Render deployed automatisch bei Push auf `main`,
  aber es gibt keinen Test-Gate davor (pytest/vitest wird nicht
  geprüft vor Merge).

---

## 2. Die Weichenstellung — Hetzner vs. Render+Vercel

**Der Prompt schlägt Hetzner-Eigenbau vor. Das ist eine andere
Architektur als der bestehende Plan.** Hier die drei Optionen:

### Option X — Bestehenden Plan umsetzen (Render + Vercel)

**Was es bedeutet:**

- `lv-preisrechner/DEPLOYMENT.md` ist der Leitfaden
- `render.yaml`-Review auf aktuellen Stand bringen
- Manuelle Schritte auf Render + Vercel (Accounts, Blueprint,
  Secrets) — Claude Code kann das nicht selbst machen
- Code-seitiger Block reduziert sich auf:
  - Health-Check-Endpoint (falls fehlt) verifizieren
  - `render.yaml` prüfen: alle B+4.x-Module + Alembic-Migrationen
    laufen mit
  - Pre-Deploy-Smoke-Checkliste
  - Post-Deploy-Smoke-Skript (curl gegen die Prod-URL)
  - Monitoring-Stub (Sentry-SDK integrieren, optional)
  - Backup-Dokumentation

**Aufwand (Code):** 2–3 h
**Aufwand (Manual Ops bei dir):** 1–2 h (Render/Vercel-Dashboard)
**Kosten laufend:** 0 € (Free) bis 14 €/Monat (Production)
**Kontrolle:** mittel (Vendor-Lock-in bei Render+Vercel)

### Option Y — Hetzner-Migration (wie im Prompt vorgeschlagen)

**Was es bedeutet:**

- Kompletter Infra-Neubau
- Hetzner CX22/CX32 Cloud-VM (4–6 €/Monat) bestellen
- `docker-compose.yml` bauen (Backend + PostgreSQL + Caddy)
- Caddyfile für TLS + Reverse-Proxy
- Systemd-Unit oder einfaches `compose up -d`
- PostgreSQL als Container statt Managed
- Secrets in `.env` auf Server (600-Permissions)
- Daily-Backup-Cronjob (pg_dump nach Hetzner Object Storage)
- Deploy-Skript: SSH + `git pull` + `docker compose up -d`

**Aufwand (Code):** 6–8 h (Dockerfile-Frontend, compose, Caddyfile,
Deploy-Skript, Backup-Script, CI-Integration optional)
**Aufwand (Manual Ops bei dir):** 2–3 h (Server bestellen, DNS,
initial deploy)
**Kosten laufend:** ~6 €/Monat (CX22) + DNS
**Kontrolle:** hoch (eigene Infra, keine Cold Starts)
**Risiko:** mehr Ops-Verantwortung (OS-Updates, Monitoring,
Incident-Response)

### Option Z — Hybrid (Frontend Vercel, Backend Hetzner)

**Was es bedeutet:**

- Frontend bleibt auf Vercel (schnell, CDN, kein Server-Management)
- Backend auf Hetzner (volle Python-Env-Kontrolle, keine
  Serverless-Timeouts, PostgreSQL lokal)
- CORS zwischen beiden konfiguriert

**Aufwand:** ähnlich Option Y minus Frontend-Docker (≈5–6 h Code)
**Kosten:** ~6 €/Monat Hetzner + 0 € Vercel Hobby
**Kontrolle:** hoch wo's wichtig ist (Backend), unkompliziert wo's
nicht wichtig ist (Frontend)

---

## 3. Empfehlung

**Option X — Bestehenden Plan umsetzen.**

### Begründung

1. **Der Plan existiert bereits vollständig** und scheint durchdacht
   (DEPLOYMENT.md + render.yaml + vercel.json + CORS-Regex für
   Preview-URLs + Kosten-Kalkulation). Ihn zu verwerfen wäre
   Sunk-Cost-Ignoranz.
2. **Render + Vercel sind produktionsreif für einen 1-Kunden-Pilot.**
   Cold-Start auf Free-Tier ist nach 14 €/Monat-Upgrade weg. Kein
   Infra-Know-how auf deiner Seite nötig für Ops.
3. **Time-to-Pilot ist kürzer:** ~2 h Setup vs. 6–8 h Hetzner-Bau.
4. **Migration später möglich:** Wenn Render zu teuer wird oder
   Benjamin eigene Infra-Kontrolle will, kann der Docker-basierte
   Backend 1:1 nach Hetzner umziehen (Dockerfile ist bereits da).

**Option Y/Z empfehle ich nur, wenn:**

- Benjamin hat explizit eine Hetzner-Präferenz (z. B. wegen
  Daten-Souveränität-Zertifizierungen, anderer LaneCore-Systeme auf
  Hetzner)
- Free-Tier-Kaltstart ist ein NoGo (dann direkt Render Starter statt
  Hetzner — weniger Aufwand)
- Render.com ist aus Compliance-Gründen ausgeschlossen
  (ISO 27001 / AVV / TOM)

---

## 4. Offene Fragen an Benjamin (vor Implementierung)

### Kritisch (blockiert Entscheidung)

1. **Warum Hetzner im Prompt?** Ist das eine bewusste Abkehr vom
   bestehenden DEPLOYMENT.md-Plan? Wenn ja: aus welchen Gründen
   (Compliance, Kosten, Kontrolle)?
2. **Ist der bestehende Plan bereits teilweise live?** Gibt es schon
   einen Render-Account, einen Vercel-Account, eine `vercel.app`-URL
   oder `onrender.com`-Backend, die aktuell laufen?
3. **Wo läuft die „Kanzlei-LLM auf GEX44"?** Falls auf eigener
   Hetzner-Infra: wäre LV-Preisrechner als Nachbar dort sinnvoll
   (Shared-Server) oder bewusst separat?

### Wichtig (beeinflusst Scope)

4. **Domain-Strategie:** Gibt es eine Domain (`lanecore.ai`,
   `harun-bau.de`, andere)? Oder bleibt es bei `vercel.app`-Subdomain
   für Pilot?
5. **Pilot-Kunden-Anzahl:** 1 Kunde (Harun's Vater) für die nächsten
   3–6 Monate oder schnelles Onboarding weiterer Kunden geplant?
   Bei 1 Kunde: Free-Tier reicht. Bei 3+: direkt Production.
6. **Monitoring-Anforderung:** Nur Render/Vercel-Logs reichen, oder
   Sentry / Uptime-Kuma / Better-Stack gewünscht?
7. **Backup-SLA:** Daily Postgres-Dumps reichen, oder gibt es
   Retention-Anforderungen aus AVV/TOM (z. B. 30 Tage)?

### Nice-to-have

8. **CI/CD:** Soll vor Deploy (auf Render) automatisch `pytest` +
   `vitest` laufen? Via GitHub Actions (kein bestehender Workflow
   im Repo)?
9. **Staging-Env:** Ein zweiter Render-Service für Preview-Branches,
   oder reichen Vercel-Previews für Frontend und Production-only
   fürs Backend?

---

## 5. Implementierungs-Plan — Option X (falls bestätigt)

### B+4.3.2b — Render-/Vercel-Pre-Deploy-Check (1–1,5 h)

- `render.yaml` lesen und gegen aktuellen Code-Stand abgleichen
  (neue ENV-Vars? Worker-Services? Migrationen?)
- Backend-Health-Endpoint verifizieren (existiert `/api/v1/health`?)
- Frontend-Build lokal reproduzieren mit `BACKEND_URL=...` Dummy
- Pre-Deploy-Checkliste in `docs/b432b_predeploy_checklist.md`

### B+4.3.2c — Manual-Deploy (Benjamin + Claude-Doku, ~2 h)

- Benjamin: Render-Account, Blueprint apply, Secrets setzen
- Benjamin: Vercel-Account, Import, ENV-Vars
- Benjamin: Smoke-Test gegen Live-URL
- Claude: Deploy-Log-Doc schreiben (was ging, was brach, wie gefixt)

### B+4.3.2d — Post-Deploy-Smoke + Monitoring-Stub (1–1,5 h)

- `scripts/smoke_live.py`: curl gegen Live-URL (health, auth,
  LV-Upload, Pricing-Upload) — wiederholbar
- Optional: Sentry-SDK im Backend (5 LOC + DSN als ENV-Var)
- Optional: Uptime-Kuma als Third-Party-Ping (kostenlos,
  self-hosted oder Better-Stack Free-Tier)

### B+4.3.2e — Backup-Doku + Incident-Runbook (1 h)

- Render's integriertes Postgres-Backup dokumentieren
- Manueller `pg_dump` als Fallback-Skript
- Kurzes Incident-Runbook: „Render Service down → X", „500-Errors
  häufig → Y", „Migration failed → Z"

**Gesamt Option X:** 5–6 h Code/Doku + 2 h Manual-Ops von Benjamin.

### Aufwand Option Y (nur falls Hetzner bestätigt)

- Mindestens 6–8 h Code + 2–3 h Manual-Ops
- Dominiert von: Caddyfile, docker-compose.prod.yml, Deploy-Skript,
  Backup-Cronjob, Frontend-Dockerfile, systemd-Unit

---

## 6. Aufwandsschätzung (Summary)

| Option | Code | Manual | Laufende Kosten | Time-to-Pilot |
|---|---|---|---|---|
| **X** (Render + Vercel, empfohlen) | 5–6 h | 2 h | 0–14 €/Monat | ~1 Tag |
| Y (Hetzner Eigenbau) | 6–8 h | 2–3 h | ~6 €/Monat | ~1,5 Tage |
| Z (Hybrid) | 5–6 h | 2 h | ~6 €/Monat | ~1,5 Tage |

Kosten dieser Planungs-Phase (2a): 0 €, ~20 min.

---

## 7. Deliverable

Nach Entscheidung durch Benjamin:

- Bei **Option X:** 4 Sub-Blöcke B+4.3.2b–e wie in §5 skizziert
- Bei **Option Y:** neuer Implementierungs-Plan, der den
  DEPLOYMENT.md-Pfad explizit verwirft und Hetzner-Infra von Null
  aufsetzt
- Bei **Option Z:** Mischform, Frontend bleibt Vercel, Backend
  Hetzner

---

## 8. Meine explizite Rückfrage zum Weiterbauen

**Bitte vor weiterem Code-Schreiben klären:**

1. **Option X, Y oder Z?**
2. **Ist Render+Vercel bereits teilweise live?** Falls ja: URLs
   und aktueller Betriebszustand mir mitteilen.
3. **Scope-Bestätigung:** die 4 Sub-Blöcke in §5 (B+4.3.2b–e)
   decken Pre-Deploy + Smoke + Backup + Runbook ab. Ist das der
   Scope, oder willst du mehr/weniger?

Sobald diese drei Punkte geklärt sind, starte ich B+4.3.2b
(Pre-Deploy-Check).
