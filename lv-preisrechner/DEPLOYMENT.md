# Deployment — LV-Preisrechner

Ziel: LV-Preisrechner so online stellen, dass Harun's Vater (und später weitere Kunden)
unter einer festen URL einen Account anlegen, ihre Preislisten hochladen und LVs
kalkulieren können.

**Stack:** Render (Backend + Postgres) + Vercel (Frontend)

**Kosten:** Free-Tier funktioniert für den Pilot:
- Render Backend Free: 750h/Monat, Kaltstart ~60s nach 15min Idle
- Render Postgres Free: 90 Tage lifetime, danach $7/Monat
- Vercel Hobby: unbegrenzt für private Nutzung

**Produktions-Upgrade** (nach Pilot): Render Starter ($7 Backend + $7 Postgres = $14/Monat) = keine Kaltstarts, 1GB DB.

---

## Voraussetzungen

- GitHub-Repo (privat reicht) mit diesem Code
- Render.com Account
- Vercel Account
- Anthropic API-Key (Console → API Keys)

---

## Schritt 1 — Code auf GitHub pushen

Das `lv-preisrechner/`-Verzeichnis muss Teil eines GitHub-Repos sein (kann dasselbe Repo
sein wie das bestehende Cockpit — Render deployt nur den Unterordner).

```bash
cd /Users/benundsasifeichtenbeiner/Bauunternehmer-Cockpit/.claude/worktrees/beautiful-mendel
git add lv-preisrechner/
git commit -m "feat: LV-Preisrechner MVP (Backend + Frontend + Infra)"
git push origin claude/beautiful-mendel
```

Oder PR zu `main` mergen, dann wird produktiv gebaut.

---

## Schritt 2 — Render: Postgres + Backend

### 2.1 Blueprint anwenden

1. Render Dashboard → **New** → **Blueprint**
2. Repository verbinden (falls noch nicht: GitHub-Berechtigung erteilen)
3. Blueprint-Datei-Pfad: `lv-preisrechner/render.yaml`
4. Render liest die Datei und zeigt eine Vorschau:
   - 1 Postgres-DB: `lv-preisrechner-db`
   - 1 Web-Service: `lv-preisrechner-backend`
5. **Apply**

Render beginnt: Database anlegen, Image bauen (`lv-preisrechner/backend/Dockerfile`),
Container starten. Dauer beim ersten Deploy ca. 5–10 Minuten.

### 2.2 Secrets setzen

Der Blueprint markiert zwei Variablen als `sync: false` — die musst du manuell setzen.
Im Render-Dashboard → Service `lv-preisrechner-backend` → **Environment**:

| Key                 | Wert                                                |
|---------------------|-----------------------------------------------------|
| `ANTHROPIC_API_KEY` | dein `sk-ant-api03-...`-Key                         |
| `SECRET_KEY`        | (Render erzeugt automatisch — nichts eintragen)     |
| `DATABASE_URL`      | (Render verknüpft automatisch mit der DB)           |

Nach dem Save: Render redeployt automatisch.

### 2.3 Backend-URL merken

Render vergibt eine URL wie: `https://lv-preisrechner-backend.onrender.com`
(Service-Settings → **Custom Domain** für eigene Domain später).

**Test:**
```bash
curl https://lv-preisrechner-backend.onrender.com/api/v1/health
# → {"status":"ok","service":"lv-preisrechner","version":"0.1.0"}
```

---

## Schritt 3 — Vercel: Frontend

### 3.1 Import

1. Vercel Dashboard → **Add New** → **Project**
2. GitHub-Repo importieren
3. **Root Directory** setzen: `lv-preisrechner/frontend`
4. Framework: **Next.js** (automatisch erkannt)

### 3.2 Environment Variables

Bei **Configure Project** → Environment Variables:

| Key            | Wert                                                      |
|----------------|-----------------------------------------------------------|
| `BACKEND_URL`  | `https://lv-preisrechner-backend.onrender.com`            |

Kein `NEXT_PUBLIC_`-Prefix nötig — Rewrites laufen auf Server-Side (Edge-Proxy).

### 3.3 Deploy

**Deploy** klicken. Build dauert ~1–2 Minuten.

Vercel vergibt URL wie: `https://lv-preisrechner.vercel.app` (ggf. mit Team-Suffix).

---

## Schritt 4 — CORS auf echte Frontend-URL setzen

Im Render-Dashboard → Backend → Environment → `CORS_ORIGINS` anpassen:

```json
["https://lv-preisrechner.vercel.app","https://deine-eigene-domain.de"]
```

Dann **Save** → Backend redeployt. Der vorkonfigurierte Regex `https://.*\.vercel\.app`
erlaubt automatisch alle Preview-Deployments von Vercel, eigene Domains müssen ins
Array.

---

## Schritt 5 — Smoke-Test online

1. https://lv-preisrechner.vercel.app öffnen → Landing-Page sollte laden
2. **Kostenlos starten** → Account anlegen
3. Kleine Preisliste (1–2 Seiten) hochladen → Fortschrittsbalken, nach ~30s fertig
4. LV hochladen → Kalkulieren → PDF downloaden

Falls Fehler auftreten:
- Render Dashboard → **Logs** (Backend)
- Vercel Dashboard → **Deployments** → letzter Deploy → **Runtime Logs** (Frontend)

---

## Schritt 6 — Eigene Domain (optional)

### Backend unter `api.deine-domain.de`
1. Render → Backend-Service → **Settings** → **Custom Domain**
2. `api.deine-domain.de` eintragen
3. Render gibt CNAME an → bei deinem Domain-Provider eintragen
4. Warten auf SSL-Zertifikat (1–5 Min)

### Frontend unter `app.deine-domain.de` oder `www.deine-domain.de`
1. Vercel → Project → **Settings** → **Domains**
2. Domain eintragen → Vercel zeigt DNS-Einträge
3. Nach DNS-Propagation: automatisches SSL

Dann in Render `BACKEND_URL` und `CORS_ORIGINS` auf die neuen Domains aktualisieren.

---

## Häufige Probleme

### "database is locked" (nur in lokaler Entwicklung)
SQLite hat Schreib-Lock-Probleme bei Background-Tasks. Lokal bereits via WAL-Modus
gefixt. In Produktion nicht relevant — Postgres hat keine Locks.

### Free-Tier Kaltstart
Nach 15 Min Idle schläft der Render-Backend-Service ein. Erste Anfrage dauert dann
~60s, danach wieder schnell. Für den Pilot OK, für Produktion auf **Starter** upgraden.

### Vercel-Rewrite-Timeout
Lange Vision-Calls (>60s) bei großen PDFs können auf Vercel Hobby abbrechen. Wir haben
`proxyTimeout: 300_000` gesetzt — das reicht für Vercel Pro. Auf Hobby ggf.
Batch-Größe in `CLAUDE_PAGES_PER_BATCH` (Render-ENV) auf 3 reduzieren.

### CORS-Fehler im Browser
- `CORS_ORIGINS` prüfen (muss JSON-Array sein, z.B. `["https://x.vercel.app"]`)
- Vercel-Preview-URLs matchen via `cors_origin_regex` automatisch

### Key nicht geladen
Render injiziert ENV-Vars direkt — kein `.env` nötig. Wenn der Key im Dashboard gesetzt
ist, aber das Backend trotzdem nicht weiß: **Manual Redeploy** klicken.

---

## Kosten-Hochrechnung nach Pilot

| Plan                                      | €/Monat | Features                                 |
|-------------------------------------------|--------:|------------------------------------------|
| Render Backend Free + DB Free (90 Tage)   |     0 € | Kaltstart, DB-Ablauf                     |
| Render Backend Starter + DB Free          |     7 € | Kein Kaltstart, DB noch 90 Tage          |
| Render Backend Starter + DB Starter       |    14 € | Prod-ready, 1GB DB, Backups              |
| + Vercel Pro (optional, für 300s-Timeout) |    28 € | pro Member                               |

Harun's Vater Pilot kann **Free** laufen, solange DB nicht aus Free-Tier fällt.
