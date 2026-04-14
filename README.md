# LaneCore AI — Bauunternehmer-Cockpit

Automatisierte Bauplan-Analyse, Preisvergleich und Angebotserstellung für Trockenbauer.

**Pilot-Kunde:** Harun's Vater, führender Trockenbauer in Ulm (15 Festangestellte, ~60 Subunternehmer)

---

## Ziel

Trockenbauer verbringen heute 4–8 Stunden pro Ausschreibung mit manueller Massenermittlung aus Bauplänen. LaneCore AI reduziert das auf <30 Minuten durch:

1. **Säule 1 — Bauplan-Analyse** (MVP): PDF-Baupläne hochladen → KI ermittelt Raummaße, Wandlängen, Deckenhöhen, Gewerke
2. **Säule 2 — Preisvergleich** (v2): Lieferantenpreislisten importieren, automatisch aktuelle Materialpreise matchen
3. **Säule 3 — Angebotserstellung** (v2): VOB-konformes Angebot / LV-Positionen automatisch befüllen

---

## Tech-Stack

| Layer | Technologie |
|-------|------------|
| Backend | Python 3.12 / FastAPI |
| Frontend | Next.js 14 (App Router) + Tailwind CSS + shadcn/ui |
| Datenbank | PostgreSQL (Prisma ORM) |
| PDF-Analyse | Claude API (Opus 4 für komplexe Pläne, Sonnet 4.5 für Vorverarbeitung) |
| Auth | Clerk |
| Storage | S3-kompatibel (AWS S3 / Cloudflare R2) |
| Deployment | Vercel (Frontend), Railway (Backend) |

---

## Projektstruktur

```
├── backend/          FastAPI Backend (Python)
├── frontend/         Next.js Frontend
├── shared/           Geteilte Types & Schemas
├── prompts/          Claude-Prompt-Bibliothek
├── docs/             Spezifikationen, ADRs, Normen
└── .claude/
    ├── agents/       Sub-Agent-Definitionen
    └── skills/       Domänen-Skill-Bibliothek
```

---

## Schnellstart (lokal)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

## Roadmap

| Sprint | Zeitraum | Ziel |
|--------|----------|------|
| 1 | KW 17–18 | Backend-Grundstruktur, PDF-Upload, Claude-Integration |
| 2 | KW 19–20 | Bauplan-Analyse Engine, Validierung, Tests |
| 3 | KW 21–22 | Frontend Dashboard, Upload-UI, Ergebnis-Anzeige |
| 4 | KW 23 | End-to-End Tests, Pilot-Rollout Ulm |
| 5 | KW 24–26 | Feedback-Integration, Säule 2 Vorbereitung |

**MVP:** 26.05.2026 | **Vollversion:** 30.06.2026

---

## Kontakt

Ben (Feichtenbeiner) — LaneCore AI
