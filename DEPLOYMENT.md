# LaneCore AI — Deployment Guide

## Übersicht

| Komponente | Plattform | Plan | Kosten |
|------------|-----------|------|--------|
| Frontend | Vercel | Free / Hobby | 0 EUR |
| Backend | Render.com | Free | 0 EUR |
| Datenbank | Render PostgreSQL | Free | 0 EUR |

**Gesamtkosten: 0 EUR/Monat** (Free Tier reicht für Demo + Pilot)

---

## Schritt 1: Backend + DB auf Render.com (5 Minuten)

### Option A: One-Click Deploy (empfohlen)

1. Gehe zu: **https://render.com/deploy**
2. Klicke "New Blueprint Instance"
3. Verbinde dein GitHub: `benjamin681/lanecore-bauunternehmer-cockpit`
4. Render erkennt automatisch die `render.yaml` und erstellt:
   - Web Service: `lanecore-backend` (Docker)
   - PostgreSQL: `lanecore-db`
5. **Wichtig:** Setze Environment Variable:
   - `ANTHROPIC_API_KEY` → dein Anthropic API Key

### Option B: Manuell

1. **https://render.com** → Sign up mit GitHub
2. **New → PostgreSQL** → Name: `lanecore-db`, Plan: Free → Create
3. Kopiere die **Internal Database URL**
4. **New → Web Service** → Connect repo `benjamin681/lanecore-bauunternehmer-cockpit`
   - Root Directory: `backend`
   - Runtime: Docker
   - Plan: Free
5. Environment Variables:
   ```
   DATABASE_URL = (kopierte Internal Database URL, ersetze postgres:// mit postgresql+asyncpg://)
   ANTHROPIC_API_KEY = sk-ant-...
   CORS_ORIGINS = https://lanecore-bauunternehmer-cockpit.vercel.app
   DEV_MODE = false
   ```
6. Deploy → Warte ~3 Minuten

**Backend-URL wird sein:** `https://lanecore-backend.onrender.com`

---

## Schritt 2: Frontend auf Vercel (3 Minuten)

1. Gehe zu: **https://vercel.com/new**
2. Import Git Repository: `benjamin681/lanecore-bauunternehmer-cockpit`
3. **Root Directory:** `frontend`
4. Framework: Next.js (automatisch erkannt)
5. Environment Variables:
   ```
   NEXT_PUBLIC_API_BASE_URL = https://lanecore-backend.onrender.com
   ```
6. Deploy → Fertig in ~1 Minute

**Frontend-URL wird sein:** `https://lanecore-bauunternehmer-cockpit.vercel.app`

---

## Schritt 3: CORS aktualisieren

Sobald du die tatsächliche Vercel-URL hast, gehe in Render Dashboard:
- Web Service → Environment → `CORS_ORIGINS`
- Setze auf die echte Vercel URL (z.B. `https://lanecore-xyz.vercel.app`)

---

## Nach dem Deployment

### Link teilen
Schicke einfach die Vercel-URL an andere:
```
https://lanecore-bauunternehmer-cockpit.vercel.app
```

### Hinweise
- **Free Tier Limits:** Render Free Web Service schläft nach 15 Min Inaktivität → erster Request dauert ~30 Sek (Cold Start)
- **Upgrade:** Render Starter ($7/Monat) → kein Cold Start mehr
- **Custom Domain:** Vercel und Render unterstützen eigene Domains (z.B. `app.lanecore.ai`)

---

## Schnell-Referenz

```bash
# Frontend lokal testen gegen Production Backend
cd frontend
NEXT_PUBLIC_API_BASE_URL=https://lanecore-backend.onrender.com npm run dev

# Backend lokal testen
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
