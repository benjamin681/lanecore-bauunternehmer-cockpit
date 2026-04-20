# INVENTORY — LaneCore AI Bauunternehmer-Cockpit

Stand: 2026-04-20 · Branch: `claude/beautiful-mendel` · Letzter Commit: `f31c8fb`

> Das Projekt ist **zweigeteilt**. Zwei parallele Codebasen im selben Repo:
> - **`/lv-preisrechner/`** — aktives MVP, online, 39 Tests grün (Haupt-Fokus aktuell)
> - **`/backend/` + `/frontend/`** — älteres Cockpit (Bauplan-Analyse-Ansatz), Status unklar

---

## 1. STACK-ERKENNUNG

### 1.1 Aktives MVP: `lv-preisrechner/`

| Layer | Technologie | Datei-Referenz |
|---|---|---|
| **Backend-Sprache** | Python 3.12+ | `lv-preisrechner/backend/pyproject.toml` |
| **Backend-Framework** | FastAPI ≥0.115, Uvicorn ≥0.32 | `pyproject.toml` |
| **DB-ORM** | SQLAlchemy ≥2.0.36 (sync, **nicht** async) | `pyproject.toml` |
| **DB-Driver** | psycopg2-binary | `pyproject.toml` |
| **DB-Engine** | PostgreSQL (prod Render, shared mit Cockpit — Prefix `lvp_`) | `render.yaml`, `alembic.ini` |
| **Migrationen** | Alembic ≥1.14 | `lv-preisrechner/backend/alembic/versions/` |
| **Auth** | passlib+bcrypt, python-jose (JWT) | `pyproject.toml`, `app/services/auth_service.py` |
| **LLM** | `anthropic` ≥0.40 (Sonnet 4.6 primary, Opus 4.6 fallback) | `app/services/claude_client.py` |
| **PDF-Bibliotheken** | **pymupdf ≥1.24.14** (fitz), pdfplumber ≥0.11.4, Pillow ≥11 | `pyproject.toml` |
| **Frontend-Sprache** | TypeScript 5.6 | `lv-preisrechner/frontend/package.json` |
| **Frontend-Framework** | Next.js 14.2.15 (App Router) | `package.json` |
| **UI-Styling** | Tailwind 3.4.14, class-variance-authority, lucide-react | `package.json` |
| **Toasts** | sonner 1.5.0 | `package.json` |
| **Build/Deploy** | Render (Backend+DB) + Vercel (Frontend) | `render.yaml`, `vercel.json` |

**Tabellen-Prefix `lvp_`** um Kollision mit Cockpit-DB zu vermeiden (shared PostgreSQL).

### 1.2 Ältere Codebase: `backend/` + `frontend/`

| Layer | Technologie | Anmerkung |
|---|---|---|
| Backend | Python 3.12 / FastAPI | `backend/pyproject.toml` |
| ORM | SQLAlchemy 2.0 (async) + asyncpg | abweichend vom MVP (dort sync) |
| Storage | boto3 / aioboto3 (S3) | existiert im pyproject, Nutzung UNKLAR |
| PDF | pypdf ≥4.0, pdfplumber ≥0.11, pdf2image | andere Lib-Mischung als MVP |
| Frontend | Next.js 14.2.18 + Clerk-Auth, Sentry, TanStack Query, React Hook Form, Zod | deutlich komplexer als MVP |
| Auth | Clerk (SaaS) | MVP nutzt stattdessen eigenes JWT |
| DB (laut Root-README) | "PostgreSQL (Prisma ORM)" | **INKONSISTENZ**: im Code steht SQLAlchemy |

---

## 2. PROJEKT-ZUSTAND

### 2.1 Codegröße (ohne `.venv`, `node_modules`, `__pycache__`)

| Bereich | Dateien | Zeilen |
|---|---|---|
| `lv-preisrechner/backend/app/` (Python) | 50 | **4.139** |
| `lv-preisrechner/frontend/src/` (TS/TSX) | 23 | **2.550** |
| `backend/app/` (Python, Cockpit) | 52 | **6.259** |
| `frontend/src/` (TS/TSX, Cockpit) | 19 | **4.248** |
| `knowledge/` (JSON Wissensbasis) | 6 | — |
| `docs/` (Markdown) | 14 | — |

### 2.2 Tests

| Suite | Status |
|---|---|
| **LV-PR Backend** | ✅ **39 passed** (pytest, 4.22s) |
| LV-PR Frontend | Keine Test-Scripts in `package.json` |
| Cockpit Backend | UNKLAR — `python` im PATH nicht gefunden beim Inventory-Run |
| Cockpit Frontend | Keine Test-Scripts sichtbar |

**LV-PR Test-Dateien:**
- `test_auth.py`
- `test_dna_matcher.py`
- `test_e2e_habau.py`
- `test_materialrezepte.py`
- `test_normalize.py`
- `test_rezepte_ausbau.py`
- `test_tenant_settings.py`

### 2.3 READMEs

| Datei | Inhalt (kurz) |
|---|---|
| `README.md` (Root) | Bauunternehmer-Cockpit — 3 Säulen (Bauplan-Analyse, Preisvergleich, Angebotserstellung). Nennt "Prisma ORM" + "Railway" — **passt nicht zum aktuellen Stand** |
| `lv-preisrechner/README.md` | Korrekt: FastAPI + SQLite/Postgres + JWT + Claude + Next.js + shadcn/ui |
| `CLAUDE.md` | Projekt-Kontext, ADRs, Domain-Begriffe, Code-Conventions — ADR-006 erklärt Pivot auf LV-Preisrechner |
| `DEPLOYMENT.md` (Root) | UNKLAR — nicht im Detail gelesen |
| `lv-preisrechner/DEPLOYMENT.md` | Render + Vercel Anleitung, Free-Tier-Hinweise |

### 2.4 Letzte Commits (letzte 10)

| Commit | Zusammenfassung |
|---|---|
| `f31c8fb` | feat(pdf): Original-LV direkt ausfuellen statt nur Anlage |
| `d0f6086` | fix(ehrlichkeit): Schein-Fallback-Preise entfernt, harte manuell-Kennzeichnung |
| `9dfdddd` | feat(rezepte): 10 neue Systeme aus Stuttgart Omega Sorg LV |
| `16093b5` | fix(major): 10 Schwachstellen aus 5-Agenten-Analyse behoben |
| `33255b1` | fix(kalkulation): 7 Schwachstellen aus LV-PDF-Analyse behoben |
| `a6e75b7` | fix(robustness): Batch-Skip bei Claude-Empty-Response + Opus-Fallback |
| `a7a1238` | ci: force rebuild |
| `29fa8ee` | feat(mobile): Viewport, Responsive Sidebar, Direct-Upload, 401-Handler |
| `26c9176` | feat(stabilitaet): PDFs in DB, Zombie-Cleanup, Memory-Streaming, Auto-Poll |
| `6963a94` | feat(retry): Retry-Parse-Endpoints + UI-Button |

**Letzter nachweislich funktionierender Stand:** Commit `f31c8fb` (heute). Tests 39/39 grün.

---

## 3. LV-SPEZIFISCH

### 3.1 PDF-Parsing-Strategie

**Datei:** `lv-preisrechner/backend/app/services/lv_parser.py` (169 Z.) + `jobs.py` (385 Z.)

Zwei-stufiger Prozess:

1. **PDF → Bilder** via `pymupdf` (`page.get_pixmap()`) in `pdf_utils.py` (142 Z.)
   - Render in DPI-anpassbarer Qualität
   - **Kein OCR** — nur native PDF-Text + Vision-basiertes Lesen durch LLM
2. **Bilder → strukturierte JSON-Positionen** via **Claude Vision**
   - Primärmodell: Claude Sonnet 4.6 (`claude-sonnet-4-6`)
   - Fallback: Claude Opus 4.6 (`claude-opus-4-6`) bei leerer/fehlerhafter Antwort
   - Batch-weise Verarbeitung mehrerer Seiten pro API-Call
   - Schema: `{ "positionen": [{ oz, titel, kurztext, menge, einheit, erkanntes_system, feuerwiderstand, plattentyp, leit_fabrikat, konfidenz }] }`

**Kein OCR für reine Scan-PDFs**: Wenn das PDF keinen Text-Layer hat, versucht Claude Vision das Bild direkt zu lesen. Bei handschriftlichen oder sehr schlecht gescannten Dokumenten: UNKLAR — nicht systematisch getestet.

### 3.2 Erwartete LV-Struktur

| Eigenschaft | Erwartet | Status |
|---|---|---|
| **Format** | PDF (gedruckt/digital) | ✅ unterstützt |
| **Sprache** | Deutsch | ✅ |
| **GAEB X83 / X84** | Erwähnt in `render.yaml`-Kommentaren, **nicht implementiert** | ❌ |
| **OZ-Schema** | Mehrstufig (`610.1`, `1.9.1.1.10`, `02.03.01`) | ✅ funktioniert für Habau + Gross-LVs |
| **Anbieter-spezifisch** | Getestet mit: Habau (Koblenz), Gross (Stuttgart Omega Sorg) | 🟡 weitere Anbieter UNKLAR |

### 3.3 Kalkulations-Logik

**Einstiegspunkt:** `lv-preisrechner/backend/app/services/kalkulation.py`
- Funktion `kalkuliere_lv(db, lv_id, tenant_id)` (öffentlich) → iteriert Positionen → ruft `_kalkuliere_position()`
- `_kalkuliere_position(db, tenant, price_list, position)`:
  1. `resolve_rezept(erkanntes_system, feuerwiderstand, plattentyp)` — aus `materialrezepte.py`
  2. Pro `MaterialBedarf` im Rezept → `find_best_match(db, tenant_id, price_list_id, dna_pattern)` aus `dna_matcher.py`
  3. Wenn Match: `teilpreis = menge_pro_einheit * preis_pro_basis`, summiert zu `material_ep`
  4. Wenn kein Match und Pflicht-Material: `fehlende_pflicht_materialien.append(...)` → Position wird als `konfidenz=0`, `ep=0`, `gp=0` markiert
  5. `lohn_ep = rezept.zeit_h_pro_einheit * tenant.stundensatz_eur`
  6. `zuschlaege_ep = (material_ep + lohn_ep) * (BGK + AGK + W+G) / 100`
  7. `ep = material_ep + lohn_ep + zuschlaege_ep`, `gp = ep * position.menge`
  8. `angebotenes_fabrikat` aus erstem Material-Match (Hersteller+Produktname) oder `leit_fabrikat`

**Daten-Flüsse:**
- **Rezepte:** `materialrezepte.py` (566 Z.) — Python-Dict mit ~25 Rezepten (W112, W115, W116, W118, W131, W135, W135_Stahlblech, W623, W625, W625S, D112, D113, OWA_MF, Aquapanel, Tueraussparung, WC_Trennwand, Verkleidung, Deckenschürze, Revisionsklappe, Streckmetalldecke, Deckensegel, Wandabsorber, Deckenschott, Streckmetall_Zulage, Wandanschluss, Kabeldurchfuehrung_F90, Deckensprung, Aufdopplung_geklebt, Verstaerkungsprofil, Zulage, Regiestunde, Fugenversiegelung, Aussparung, Installationsloch, Eckschiene)
- **Matcher:** `dna_matcher.py` (141 Z.) — Token-Scoring mit Hard-Match für spezifische Profile-Codes (UA, CW50/75/100, UW50/75/100, CD60, UD, Fireboard, Diamant, Silentboard, Aquapanel)
- **Normalisierer:** `price_list_parser.py` (288 Z.) — wandelt Gebinde-Preise in €/lfm, €/m², €/Stk

### 3.4 Wissensbasis

**`knowledge/`** (6 JSON-Dateien):
- `knauf-systeme-w11-d11.json` — W111-W116 + D111-D116
- `knauf-systeme-brandschutz-fireboard.json` — Brandwände, Fireboard-Systeme, K21, D131
- `knauf-systeme-w61-vorsatzschalen.json` — W623/W625/W626/W628/W631
- `knauf-systeme-w62-w63-schachtwaende.json` — Schachtwände einseitig/zweiseitig
- `kemmler-preise-042026.json` — Testpreisliste Trockenbau-Großhändler
- `habau-koblenz-lv-beispiel.json` — vollständiges LV mit 76 Positionen als Referenz-Trainingsdatensatz

**Wichtiger Hinweis aus Agent-Reports:** Die Knauf-JSONs wurden "aus Modellwissen rekonstruiert, Validierung gegen offizielle Knauf-Detailblätter ausstehend". Nicht 1:1 gegen offizielle Knauf-PDFs verifiziert.

### 3.5 API-Endpunkte (LV-PR Backend)

**Auth:** `/api/v1/auth/` — register, login, me, PATCH /me/tenant

**LVs:** `/api/v1/lvs/`
- `POST /upload-async` — LV-Upload mit Background-Parsing
- `POST /upload` — synchrone Variante (Legacy)
- `GET` — Liste
- `GET /{id}` — Detail
- `PATCH /{id}/positions/{pos_id}` — manuelle Korrektur einer Position
- `POST /{id}/retry-parse` — erneutes Parsing
- `POST /{id}/kalkulation` — Preise berechnen
- `POST /{id}/export` — ausgefülltes PDF generieren
- `GET /{id}/download` — PDF herunterladen
- `DELETE /{id}`

**Preislisten:** `/api/v1/price-lists/` — analog LV (Upload, List, Detail, Retry, Entries-PATCH, Activate)

**Jobs:** `/api/v1/jobs/{id}` — Progress-Polling für async Jobs

---

## 4. AMPEL-BEWERTUNG

### 🟢 GRÜN — funktioniert nachweislich

| Komponente | Nachweis |
|---|---|
| LV-PR Backend: Grundfunktionen | 39/39 Tests grün (`test_auth`, `test_dna_matcher`, `test_materialrezepte`, `test_normalize`, `test_rezepte_ausbau`, `test_tenant_settings`, `test_e2e_habau`) |
| LV-PR Frontend-Build | `package.json` vollständig, letzte Deploys erfolgreich laut Commit-Historie |
| Claude-Vision-Parsing (Sonnet 4.6 → Opus 4.6 Fallback) | Commit `a6e75b7` dokumentiert funktionierenden Fallback-Mechanismus |
| Auth (JWT) | Test `test_auth.py` grün, Service `auth_service.py` |
| Material-DNA-Matching (Basis) | Test `test_dna_matcher.py` grün |
| Gebinde-Normalisierung | Test `test_normalize.py` grün |
| PDF-Deckblatt + Kalkulations-Anlage | in jedem aktuellen Export enthalten |
| Original-LV direkt ausfüllen | Seit Commit `f31c8fb` — Roundtrip-Test gegen Stuttgart-LV zeigt `45,20` EP + `3.435,20` GP in den leeren Dot-Feldern |
| Deployment (Render Backend + Vercel Frontend) | Blueprints vorhanden, letzte Deploys laut Commit-Historie erfolgreich |
| Multi-Tenant-Schema | `lvp_`-Prefix, isoliert pro `tenant_id` |
| Ehrliche Fallback-Politik | Seit Commit `d0f6086` — kein Schein-Preis mehr, klare "manuell"-Kennzeichnung |

### 🟡 GELB — existiert, aber Qualität oder Robustheit UNKLAR

| Komponente | Warum gelb |
|---|---|
| Rezept-Abdeckung | ~25 Rezepte. Deckt Standard-Systeme ab (W112, OWA-Rasterdecke, Vorsatzschalen), aber Einzelfälle wie "Streckmetalldecke Lindner LMD ST 215", "Deckensegel Strähle 7300", "Wandabsorber DUR SONIC Quad" wurden erst am 2026-04-20 hinzugefügt und **nicht mit echten Preisen getestet** |
| Knauf-Knowledge-JSONs | Laut Agent-Report "aus Modellwissen rekonstruiert, Validierung gegen offizielle Knauf-Detailblätter ausstehend" |
| Kemmler-Testpreisliste | Nur Test-Fixture — reale Einkaufspreise des Pilot-Kunden fehlen |
| Original-LV-Ausfüll-Heuristik | Regex-basiert (`"..........  ......"` → EP+GP). Funktioniert für Habau, Gross. Andere LV-Layouts UNKLAR |
| Mobile-UI | Responsive umgesetzt (Commit `29fa8ee`), aber kein automatisierter Mobile-Test |
| DNA-Matcher-Score-Threshold | Fixed 0.5 — laut Agent-Report kann bei vielen leeren Pattern-Feldern ein fast leeres Pattern die Schwelle zufällig überschreiten |
| Preis-Normalisierer (Paket/Bündel) | Mehrere Regex-Lücken dokumentiert (z.B. "Pal. 40 Stk", "9 lfm/Bund") laut Agent-Bug-Report |
| Cockpit (`/backend`, `/frontend`) | Existiert, unklar ob deployt oder nur Legacy. Nutzt anderen Stack (async SQLAlchemy, Clerk, Sentry) |
| Root-README vs. tatsächlicher Stack | Root-README spricht von "Prisma ORM" und "Railway" — im Code SQLAlchemy + Render |
| Frontend-Tests | **Keine** vorhanden |

### 🔴 ROT — fehlt oder kaputt

| Komponente | Fehlend/Defekt |
|---|---|
| **GAEB X83/X84 Parsing** | Nicht implementiert, LVs müssen als PDF vorliegen |
| **OCR für Scan-PDFs ohne Text-Layer** | Kein Fallback — Claude Vision kann zwar Bilder lesen, aber schlechte Scans / Handschrift werden nicht geprüft/gewarnt |
| **Plausibilitäts-Check nach Kalkulation** | Es gibt **keine** Prüfung, ob die errechneten EPs im Marktbereich liegen. EP 3.038 €/Stk für Türaussparung wurde erst durch User-Feedback, nicht automatisch, erkannt |
| **Bedarfspositionen-Erkennung** | "*** Bedarfsposition ohne GB" im Stuttgart-LV: wird derzeit **voll in Angebotssumme einbezogen** statt ausgenommen |
| **Alternativ-Positionen-Handling** | "Alternativprodukt" wird als normale Position kalkuliert, nicht als Alternative |
| **Lern-Fähigkeit / Memory** | Manuelle Korrekturen des Users werden pro-Position gespeichert (`manuell_korrigiert`-Flag), aber **nicht übertragen** auf andere Positionen oder zukünftige LVs |
| **LV-Gutachter-Agent** | Kein Vor-Durchlauf, der das LV vor der Kalkulation einschätzt (Projekttyp, Risiken, Gewerk-Mix) |
| **Intelligenter Rezept-Wähler** | Derzeit starres Regex+Alias — kein LLM-basierter Classifier für Position → Rezept |
| **Frontend-Tests** | keine Test-Scripts, keine Vitest/Playwright-Config |
| **Systematischer Mobile-Test** | UNKLAR ob echter iOS-/Android-Check stattfand |
| **Hersteller-Preislisten außer Kemmler** | Lindner, Strähle, DUR, Rigips, Siniat, Fermacell: keine Testdaten |
| **Original-Bauplan-Analyse-Pipeline (/backend Cockpit)** | UNKLAR ob noch funktioniert — wurde seit Pivot auf LV-Preisrechner nicht mehr im Fokus |

---

## UNKLAR-Liste (systematisch offene Fragen für weitere Prüfung)

- **UNKLAR:** Ist `/backend` (Cockpit) noch deployed oder nur Code-Artefakt?
- **UNKLAR:** Läuft `/frontend` (Cockpit) mit eigener Vercel-URL oder wurde es durch LV-Preisrechner-Frontend ersetzt?
- **UNKLAR:** Welcher Anteil der 23+ Knauf-System-Spezifikationen in `knowledge/knauf-systeme-*.json` ist tatsächlich mit offiziellen Knauf-AbZ/AbP-Prüfzeugnissen abgeglichen?
- **UNKLAR:** Haben Kalkulationsergebnisse auf den getesteten LVs (Habau, Stuttgart Omega) tatsächlich die Markterwartung getroffen? Es gibt **keine Referenz-Angebote** des Pilot-Kunden zum Vergleich.
- **UNKLAR:** Funktioniert das Original-LV-Ausfüllen robust bei nicht-getesteten LV-Layouts (z.B. Word-erzeugte LVs mit Tabellen statt Dot-Linien)?
- **UNKLAR:** Wie reagiert das System auf GAEB-XML-Dateien? Rejection-Pfad vorhanden?
- **UNKLAR:** DATEV-/Buchhaltung-Export gelistet in CLAUDE.md als "NICHT im MVP" — existiert in `/backend` aber `kalkulation_service.py` + `excel_export.py`. Werden die vom LV-Preisrechner mitgenutzt? (Nein, vermutlich Legacy — aber UNKLAR)

---

## Zusammenfassung

**Kernprodukt = `/lv-preisrechner/`**: ein funktionsfähiges, online deploytes MVP mit 39/39 Backend-Tests grün, durchgängigem Flow (Registrieren → Preisliste-Upload → LV-Upload → Kalkulation → PDF-Download) und seit dem heutigen Commit (`f31c8fb`) auch Original-LV-Befüllung.

**Hauptrisiken:**
1. Knowledge-Base ist modellgeneriert, nicht herstellerverifiziert.
2. Keine automatische Plausibilitätsprüfung — Fehlkalkulationen werden nur durch Nutzer-Review entdeckt.
3. Bedarfs-/Alternativ-Positionen sind falsch in der Angebotssumme.
4. Original-LV-Befüllung ist regex-heuristisch und nicht gegen breites LV-Spektrum getestet.

**Größter Hebel für Qualitätsgewinn:** "Intelligenter Rezept-Wähler" (Claude-basierter Per-Position-Classifier statt Regex) — nicht gebaut, in Planung.
