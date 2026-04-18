# LV-Preisrechner

MVP für Trockenbauer: LV hochladen → System matcht gegen kunden-eigene Preisliste → ausgefülltes LV-PDF zurück.

## Architektur

- **Backend:** FastAPI (Python 3.12), SQLite, JWT-Auth, Claude Sonnet 4.6 + Opus 4.6 Fallback
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui
- **Isolation:** Separates Projekt (ADR-006) — kein Clerk, keine externe DB, kein K8s

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m app.core.database  # Schema anlegen
uvicorn app.main:app --reload --port 8100
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:3100
```

## Benutzer-Flow

1. **Registrieren / Login** — Ein User = ein Mandant (Trockenbau-Betrieb)
2. **Preisliste hochladen** — PDF/Excel mit Einkaufspreisen (eigene Konditionen)
3. **System parst** → Produkt-DNA, Review-UI zur Korrektur
4. **LV hochladen** — Das LV vom Auftraggeber (PDF)
5. **System kalkuliert** — Material + Lohn + Zuschläge pro Position
6. **Ausgefülltes PDF** als Download

## Ordnerstruktur

```
lv-preisrechner/
├── backend/
│   ├── app/
│   │   ├── core/         # Config, DB, Security
│   │   ├── models/       # SQLAlchemy Tabellen
│   │   ├── schemas/      # Pydantic DTOs
│   │   ├── api/          # FastAPI Routes
│   │   └── services/     # Business-Logik
│   ├── tests/
│   └── data/             # SQLite + Upload-Storage
└── frontend/
    └── src/app/
        ├── (auth)/       # Login/Register
        └── (dashboard)/  # Geschützte Bereiche
```

## Tech-Entscheidungen siehe

- `docs/architektur-entscheidung-lv-preisrechner.md` (ADR-006)
- `docs/architektur-entscheidung-preisliste-upload.md` (ADR-007)
