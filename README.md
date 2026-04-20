# LaneCore AI — LV-Preisrechner

Automatisierter LV-Preisrechner für Trockenbauer: LV hochladen → Materialkosten aus eigener Händler-Preisliste matchen → ausgefülltes LV-PDF mit Einheits- und Gesamtpreisen als Download.

**Pilot-Kunde:** Harun's Vater, führender Trockenbauer in Ulm (15 Festangestellte, ~60 Subunternehmer).

**Aktiver Stand:** Live auf Render (Backend) + Vercel (Frontend).

---

## Aktive Codebase

Das Projekt läuft ausschließlich unter **`/lv-preisrechner/`**.

```
lv-preisrechner/
├── backend/     FastAPI + SQLAlchemy + PostgreSQL (Render)
├── frontend/    Next.js 14 App Router (Vercel)
├── README.md    Setup + Benutzerflow
└── DEPLOYMENT.md
```

Details: siehe [`lv-preisrechner/README.md`](lv-preisrechner/README.md).

---

## Tech-Stack

| Layer | Technologie |
|-------|-------------|
| Backend | Python 3.12 / FastAPI / SQLAlchemy (sync) |
| Datenbank | PostgreSQL auf Render (Tabellen-Prefix `lvp_`) |
| Migrationen | Alembic |
| Auth | JWT (eigener Flow, kein externer Provider) |
| LLM | Claude Sonnet 4.6 (primary) → Opus 4.6 (fallback) |
| PDF | PyMuPDF / pdfplumber / Pillow |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind |
| Deployment | Render (Backend + DB) + Vercel (Frontend) |

---

## Schnellstart (lokal)

```bash
# Backend
cd lv-preisrechner/backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8100

# Frontend
cd lv-preisrechner/frontend
npm install
npm run dev        # http://localhost:3100
```

---

## Repository-Struktur

```
├── lv-preisrechner/      ← AKTIVES MVP
├── knowledge/            Wissensbasis (Knauf-Systeme, Testpreislisten, LV-Beispiele)
├── docs/                 Spezifikationen, ADRs, Normen
├── prompts/              Claude-Prompt-Bibliothek (teilweise Legacy)
├── _archive/
│   └── cockpit-legacy/   Archivierte erste Version (Bauplan-Analyse-Ansatz)
└── .claude/
    ├── agents/           Sub-Agent-Definitionen
    └── skills/           Domänen-Skill-Bibliothek
```

**`_archive/cockpit-legacy/`** enthält den ersten Produkt-Ansatz (Bauplan-Analyse mit Clerk/Sentry/async-SQLAlchemy). Nach dem Kundengespräch am 17.04.2026 wurde auf den LV-Preisrechner-Ansatz gepivotet (siehe `docs/architektur-entscheidung-lv-preisrechner.md`, ADR-006). Der Legacy-Code bleibt im Archiv für Referenzzwecke, wird **nicht mehr gepflegt oder deployed**.

---

## Kontakt

Ben (Feichtenbeiner) — LaneCore AI
