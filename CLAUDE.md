# CLAUDE.md — LaneCore AI Bauunternehmer-Cockpit

Dieser Kontext gilt für alle Claude-Code-Sessions in diesem Projekt.

---

## Projekt-Kontext

**Was:** KI-gestütztes Cockpit für Trockenbauer — automatische Massenermittlung aus Bauplänen, Preisvergleich, Angebotserstellung.

**Wer:** Pilot-Kunde ist Harun's Vater, größter Trockenbauer in Ulm (15 Angestellte + 60 Subunternehmer). Enterprise-Rollout nach erfolgreichem Pilot.

**Warum:** Massenermittlung aus Bauplänen dauert heute 4–8h manuell. Claude-API kann das in <5min automatisieren.

**MVP-Fokus (aktualisiert 04/2026):** Nach Kundengespräch vom 17.04.2026 ist der sofortige Bedarf klar:
- Harun's Vater bekommt LVs (Leistungsverzeichnisse) als PDF vom Auftraggeber
- Er will seine Kemmler-Einkaufspreise dagegen matchen
- Er will ein zu 100% ausgefülltes LV als PDF zurückbekommen
- **Das neue MVP ist der LV-Preisrechner** — nicht Bauplan-Analyse, sondern LV-Bepreisung
- LV-Preisrechner wird als **separates Projekt** gebaut (docs/architektur-entscheidung-lv-preisrechner.md)
- Time-to-Revenue: ~1 Woche vs ~4 Wochen für Cockpit-Integration

---

## Architektur-Entscheidungen (ADRs)

### ADR-001: Python/FastAPI für Backend
- PDF-Processing-Bibliotheken (pypdf, pdfplumber) sind in Python besser
- Claude SDK ist in Python first-class
- Async-fähig für lange PDF-Analyse-Jobs

### ADR-002: Next.js 14 mit App Router
- Server Actions für Form-Handling ohne extra API-Endpunkte
- RSC für performance-kritische Seiten
- shadcn/ui für konsistentes UI ohne eigene Component-Library

### ADR-003: Claude Opus 4 für komplexe Baupläne
- Pläne haben oft handschriftliche Notizen, schlechte Qualität, Sonderschriften
- Opus ist akkurater bei Maßketten und Legende-Interpretation
- Sonnet für Pre-Processing (OCR-Validierung, einfache Grundrisse)
- Cost-Optimierung: erst Sonnet, bei Unsicherheit Opus-Fallback

### ADR-004: PostgreSQL mit Prisma
- Relationale Daten: Projekte → Pläne → Analyse-Ergebnisse → Positionen
- Prisma für typsichere Queries
- Migrations via `prisma migrate`

### ADR-005: Modulare Säulen-Architektur
- Säule 1, 2, 3 sind unabhängige Module
- Shared: Auth, Storage, DB-Verbindung
- Jedes Modul hat eigenes Service-Layer

---

## Code-Conventions

### Python (Backend)
- Python 3.12+, type hints überall
- Pydantic v2 für alle Schemas (kein dict-typing)
- `async/await` für alle I/O-Operationen
- Services-Layer zwischen Router und DB: `app/services/`
- Fehler via custom Exception-Klassen in `app/core/exceptions.py`
- Tests in `tests/` mit pytest + pytest-asyncio
- Naming: `snake_case` für alles

### TypeScript (Frontend)
- Strict-Mode aktiv
- App Router: Server Components by default, Client Components nur wenn nötig
- Server Actions für Formulare (kein separater API-Call)
- Zod für alle Schema-Validierungen
- Naming: `camelCase` für Variablen, `PascalCase` für Komponenten
- Keine `any` ohne Kommentar

### API-Design
- REST: `/api/v1/{resource}`
- Response immer: `{ data: T, meta?: {...} }` oder `{ error: string, details?: {...} }`
- HTTP-Status korrekt nutzen (201 für Create, 422 für Validation, 404 für Not Found)
- Bearer-Token Auth via Clerk

### Git
- Branches: `feature/`, `fix/`, `chore/`
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`)
- Kein direkter Push auf `main`

---

## Wichtige Domain-Begriffe (Trockenbau)

- **Massenermittlung**: Berechnung der benötigten Materialmengen aus dem Bauplan
- **LV**: Leistungsverzeichnis (strukturiertes Angebotsformat nach VOB)
- **VOB**: Vergabe- und Vertragsordnung für Bauleistungen (Regelwerk)
- **CW/UW-Profile**: Metall-Ständer und Boden/Deckenanschlüsse für Trockenwände
- **GK / GKF / GKFi**: Gipskarton / Gipskarton-Feuerschutz / Feuerschutz imprägniert
- **W112**: Standard-Trennwand (1x beplankt, 1-lagig)
- **W115**: Erhöhter Schallschutz (1x beplankt, 2-lagig)
- **W118**: Brandschutzwand (2x beplankt, GKF)
- **Maßkette**: Bemaßung in Bauplänen (z.B. 3.45 + 1.20 + 2.30 = Gesamtlänge)
- **Grundriss**: 2D-Draufsicht des Geschosses
- **Schnitt**: Vertikaler Querschnitt durch das Gebäude
- **Legende**: Erklärung der Planzeichen
- **Maßstab**: z.B. 1:100, 1:50, 1:20

---

## Skill-Bibliothek

Alle domänen-spezifischen Skills sind in `.claude/skills/` dokumentiert:

- `bauplan-analyse/` — Baupläne interpretieren
- `trockenbau-kalkulation/` — Materialmengen berechnen
- `preislisten-import/` — Preislisten verarbeiten
- `angebots-erstellung/` — LV und Angebote erstellen
- `frontend-ui-ux/` — UI-Design für Handwerker
- `fastapi-backend/` — FastAPI-Patterns
- `nextjs-frontend/` — Next.js App Router
- `pdf-processing/` — PDF-Analyse
- `claude-api-integration/` — Claude-API richtig nutzen

---

## Sub-Agents

Spezialisierte Agents in `.claude/agents/`:

- `bauplan-experte` — Für Domänen-Fragen zu Trockenbau
- `code-reviewer` — Code-Qualität und Security
- `ui-designer` — UI/UX für Bauunternehmer
- `api-architect` — Backend-Architektur-Entscheidungen
- `test-engineer` — Test-Strategie und -Implementierung

---

## Kritische Qualitäts-Anforderungen

1. **Bauplan-Analyse-Genauigkeit**: Abweichung <2% zu manueller Messung
2. **Performance**: PDF-Analyse <3 Minuten für Standard-Grundriss
3. **Fehler-Transparenz**: Wenn Claude unsicher ist, MUSS das angezeigt werden (kein silent failure)
4. **Audit-Trail**: Jede Analyse muss nachvollziehbar sein (welcher Prompt, welches Modell, welche Konfidenz)

---

## Was NICHT gebaut wird (für MVP)

- BIM/IFC-Integration (kommt in v3)
- Mobile App (Desktop-first)
- Multi-Tenant (erst nach Pilot)
- Eigene OCR (Claude Vision reicht)
- Anbindung an DATEV / Buchhaltung

---

## LV-Preisrechner (Neues MVP — separates Projekt)

Siehe `docs/lv-preisrechner-spec.md` für vollständige Spezifikation.

**Kern-Flow:**
1. Input: LV als PDF (Hauptfall), GAEB X83, oder Excel
2. Claude extrahiert Positionen (OZ, Menge, Einheit, Kurztextbeschreibung)
3. Matching: Leistungstext → Materialrezept → Kemmler-Preise
4. EP-Kalkulation: Material + Lohn + Zuschläge (BGK/AGK/W+G)
5. Output: Ausgefülltes Original-PDF mit EP und GP

**Matching-Prinzip (Produkt-DNA):**
- NICHT über Artikelnummern, sondern: Hersteller + Kategorie + Produktname + Abmessungen + Variante
- Diese Kombination ist bei jedem Händler gleich — nur Artikelnummer und Preis unterscheiden sich

**Bekannte Preisdaten:** `knowledge/kemmler-preise-042026.json`

**Offene Fragen an Kunde:** `docs/offene-fragen-harun.md`

**Proof of Concept:** `docs/proof-of-concept-ergebnisse.md` (Habau GmbH, 58 Seiten, 16/16 Positionen erfolgreich)
