# Architektur-Übersicht — LaneCore AI

## System-Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                         Nutzer-Browser                          │
│                    (Next.js 14, Vercel CDN)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Clerk (Auth-Service)                         │
│              JWT-Token-Ausstellung und -Validierung             │
└────────────────────────────┬────────────────────────────────────┘
                             │ Bearer Token
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Railway)                       │
│                                                                 │
│  /api/v1/bauplan/upload  ──►  BackgroundTask (Analyse-Job)     │
│  /api/v1/bauplan/{id}/status                                    │
│  /api/v1/bauplan/{id}/result                                    │
│  /api/v1/projekte/...                                           │
│                                                                 │
│  ┌─────────────────┐    ┌───────────────────────────────────┐  │
│  │  BauplanService  │───►│ Claude Vision API (Anthropic)     │  │
│  │  (Orchestration) │    │ Opus 4 (komplex) / Sonnet (einfach)│ │
│  └─────────────────┘    └───────────────────────────────────┘  │
│           │                                                     │
│           ▼                                                     │
│  ┌────────────────────────┐    ┌──────────────────────────┐   │
│  │   PostgreSQL (Railway) │    │  S3 / Cloudflare R2       │   │
│  │   Projekte, Jobs,      │    │  PDF-Dateien              │   │
│  │   Analyse-Ergebnisse   │    │  (verschlüsselt)          │   │
│  └────────────────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Daten-Flow: Bauplan-Analyse

```
1. Nutzer wählt PDF aus (Frontend)
     ↓
2. Multipart-Upload → POST /api/v1/bauplan/upload
     ↓
3. Backend: PDF validieren (Größe, Typ, Seiten)
     ↓
4. PDF nach S3 hochladen (async)
     ↓
5. Analyse-Job in DB erstellen (Status: "pending")
     ↓
6. HTTP 202 → Frontend (Job-ID)
     ↓
7. [BackgroundTask] PDF von S3 lesen
     ↓
8. PDF → Bilder konvertieren (pdf2image, 200 DPI)
     ↓
9. Pro Seite:
   a) [Sonnet] Ist es ein Grundriss?
   b) Ja → [Opus] Detail-Analyse mit Vision-Prompt
   c) JSON aus Antwort extrahieren + validieren
     ↓
10. Alle Seiten zusammenführen, Gesamtergebnis berechnen
     ↓
11. Ergebnis in DB speichern, Status: "completed"
     ↓
12. Frontend pollt /status → "completed" → /result abrufen
     ↓
13. Ergebnis anzeigen
```

---

## Komponenten-Grenzen (Modul-Isolation)

```
┌─ Säule 1: Bauplan-Analyse ─────────────────────────────┐
│  backend/app/services/bauplan_service.py               │
│  backend/app/api/routes/bauplan.py                     │
│  prompts/bauplan-analyse.md                            │
└────────────────────────────────────────────────────────┘

┌─ Säule 2: Preisvergleich (v2) ─────────────────────────┐
│  backend/app/services/preislisten_service.py           │
│  backend/app/api/routes/preislisten.py                 │
└────────────────────────────────────────────────────────┘

┌─ Säule 3: Angebotserstellung (v2) ─────────────────────┐
│  backend/app/services/angebot_service.py               │
│  backend/app/api/routes/angebote.py                    │
└────────────────────────────────────────────────────────┘

┌─ Shared ────────────────────────────────────────────────┐
│  backend/app/core/  (Auth, Config, DB)                 │
│  backend/app/models/ (ORM-Modelle)                     │
│  shared/types/      (geteilte TS-Typen)                │
└────────────────────────────────────────────────────────┘
```

---

## Deployment

| Service | Provider | Plan |
|---------|----------|------|
| Frontend | Vercel | Hobby → Pro bei Launch |
| Backend API | Railway | Starter → Pro |
| PostgreSQL | Railway | Managed PostgreSQL |
| Storage | Cloudflare R2 | Pay-as-you-go (~kostenlos im MVP) |
| Auth | Clerk | Free (bis 10.000 MAU) |

### Umgebungen
- `development`: Lokal, .env-Datei, lokale PostgreSQL
- `staging`: Railway Preview-Environment (optional)
- `production`: Vercel + Railway Production
