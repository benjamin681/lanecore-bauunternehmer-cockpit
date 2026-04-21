# B+4.3.0 — Frontend-Discovery & Architektur-Vorschlag

**Stand:** 21.04.2026  |  **Branch:** `claude/beautiful-mendel`
**Zweck:** Bestandsaufnahme vor Bau des Pilot-UIs für Yildiz /
Bau-Cockpit. Null Code-Änderungen, nur Inventar + Plan.

---

## Phase 1 — Repo-Inventar

### Projekt-Ort

| Feld | Wert |
|---|---|
| Pfad | `lv-preisrechner/frontend/` |
| Framework | **Next.js 14.2.15** (App Router) |
| React | 18.3.1 |
| TypeScript | 5.6.3 (strict mode) |
| Paketmanager | **npm** (`package-lock.json`) |
| Path-Alias | `@/*` |
| Dev-Port | **3100** |

### Styling & UI-Library

| Stack | Konkret |
|---|---|
| **Tailwind** | v3, `tailwind.config.ts` mit custom Farben `bauplan-*`, `success-*`, `warning-*`, `danger-*` |
| **shadcn/ui** | Ja, in `src/components/ui/` |
| **Vorhandene UI-Bausteine** | `badge`, `button`, `card`, `dialog`, `input`, `label`, `select`, `table`, `pagination`, **`stage-badge`** |
| Globale Styles | `src/app/globals.css` (Tailwind-only) |

### State & Data

| Layer | Entscheidung |
|---|---|
| State-Management | **Keine Library** — React-Hooks lokal in Komponenten |
| Data-Fetching | **fetch** direkt, kein SWR/Query |
| API-Clients | `src/lib/api.ts` (Legacy + Auth) + `src/lib/pricingApi.ts` (neue Pricing-API) |
| Token | localStorage `lvp_token`, Bearer-JWT |
| Types | `src/lib/types/pricing.ts` (SupplierPriceList, Entry, Status-Meta) |

### Routes-Inventar (`src/app/**`)

| Route | Datei | Status |
|---|---|---|
| `/login`, `/register` | `src/app/{login,register}/page.tsx` | ✓ |
| `/dashboard` (Layout + Overview) | `src/app/dashboard/{layout,page}.tsx` | ✓ |
| `/dashboard/preislisten/*` | `src/app/dashboard/preislisten/**` | Legacy, bleibt |
| **`/dashboard/pricing`** | `src/app/dashboard/pricing/page.tsx` | ✓ neu (B+3) — Liste aller SupplierPriceLists |
| **`/dashboard/pricing/upload`** | `src/app/dashboard/pricing/upload/page.tsx` | ✓ neu (B+3) — Drop-Zone + Metadaten |
| **`/dashboard/pricing/[id]`** | `src/app/dashboard/pricing/[id]/page.tsx` | ✓ neu (B+3) — Detail + Parse-Trigger |
| **`/dashboard/pricing/[id]/review`** | `src/app/dashboard/pricing/[id]/review/page.tsx` + `ReviewEntryDialog.tsx` | ✓ neu (B+3.3) — Filter, Table, Edit-Dialog |
| `/dashboard/lvs` | `src/app/dashboard/lvs/page.tsx` | ✓ Liste |
| `/dashboard/lvs/neu` | `src/app/dashboard/lvs/neu/page.tsx` | ✓ Upload |
| **`/dashboard/lvs/[id]`** | `src/app/dashboard/lvs/[id]/page.tsx` | ✓ Detail mit StageBadge + `needs_price_review` |
| `/dashboard/einstellungen` | `src/app/dashboard/einstellungen/page.tsx` | ✓ Tenant-Config inkl. **`use_new_pricing`-Toggle** |
| `/dashboard/dev/components` | `src/app/dashboard/dev/components/page.tsx` | Dev-Showcase |

### Komponenten außerhalb `ui/`

- `src/components/Dropzone.tsx` — Drag & Drop
- `src/components/ProgressBar.tsx`
- `src/app/dashboard/pricing/[id]/review/ReviewEntryDialog.tsx` — 398 LOC Edit-Dialog mit Bundle-Preis-Helper

### Auth-Flow

- Login `POST /api/v1/auth/login` → Token in `localStorage.lvp_token`
- Dashboard-Layout (`"use client"`) ruft `GET /auth/me`, redirected ohne Token zu `/login`
- 401 → `api.ts` räumt Token auf + Redirect
- Tenant ist implizit im JWT (`tid`), nichts im Frontend zu verwalten

### Tests

**0 Tests** im Frontend. Kein Vitest, kein Jest, kein Playwright.
`tsc --noEmit` via `npm run typecheck` ist der einzige Automat-Check.

### Build

| Script | Zweck |
|---|---|
| `npm run dev` | Dev-Server Port 3100 |
| `npm run build` | Produktions-Build |
| `npm run lint` | Next-ESLint |
| `npm run typecheck` | `tsc --noEmit` (streng) |

**Keine CI-Pipeline** im Repo (`.github/workflows` fehlt).

**Vercel-Config:** `vercel.json` mit `/api/*`-Rewrite auf Backend. Große
Uploads (>4,5 MB) gehen via `NEXT_PUBLIC_BACKEND_URL` direkt ans
Backend — Pattern ist in `pricingApi.uploadPricelist()` bereits
umgesetzt.

---

## Phase 2 — Backend-API-Exposure

### Root

| Feld | Wert |
|---|---|
| Prefix | `/api/v1` |
| OpenAPI | default `/docs` (Swagger) + `/openapi.json` |
| Health | `GET /api/v1/health` |

### Pricing (`app/api/pricing.py`)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/pricing/readiness` | Check vor `use_new_pricing=True` |
| POST | `/pricing/upload` | Upload + optional auto-parse |
| GET | `/pricing/pricelists` | Liste (Filter: status, supplier, active) |
| GET | `/pricing/pricelists/{id}` | Detail (opt. entries) |
| POST | `/pricing/pricelists/{id}/activate` | aktiviert, deaktiviert andere des Suppliers |
| DELETE | `/pricing/pricelists/{id}` | Soft-Delete (→ ARCHIVED) |
| POST | `/pricing/pricelists/{id}/parse` | Parse-Trigger |
| GET | `/pricing/pricelists/{id}/review-needed` | needs_review=True, sortiert |
| PATCH | `/pricing/pricelists/{id}/entries/{entry_id}` | Korrektur |
| GET / POST / DELETE | `/pricing/overrides` | Tenant-Overrides |
| GET / POST / DELETE | `/pricing/discount-rules` | Rabatt-Regeln |

### LVs (`app/api/lvs.py`)

| Methode | Pfad | Zweck |
|---|---|---|
| POST | `/lvs/upload-async` | Async, Job-ID |
| POST | `/lvs/upload` | Sync |
| POST | `/lvs/{id}/retry-parse` | Neustart |
| GET | `/lvs` | Liste |
| GET | `/lvs/{id}` | Detail inkl. Positionen |
| PATCH | `/lvs/{id}/positions/{position_id}` | Manuelle Korrektur |
| POST | `/lvs/{id}/kalkulation` | EP/GP berechnen |
| POST | `/lvs/{id}/export` | Ausgefülltes PDF erzeugen |
| GET | `/lvs/{id}/download` | PDF-Download |
| DELETE | `/lvs/{id}` | Löschen |

### Auth (`app/api/auth.py`)

| Methode | Pfad | Zweck |
|---|---|---|
| POST | `/auth/register` | Registrierung |
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Me (inkl. `use_new_pricing`) |
| PATCH | `/auth/me/tenant` | Tenant-Config (inkl. `use_new_pricing` mit Readiness-Gate) |

### Jobs (`app/api/jobs.py`)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/jobs/{id}` | Polling (queued/running/done/error) |

### Near-Miss & Katalog-Lücken

**Near-Miss:** Kein dedizierter Endpoint. Kandidaten-Trail landet im
`Position.materialien[*].source_description` + `lookup_details`-JSON.
Die Top-3-Alternativen gibt es **nur implizit**, ein UI-Drawer müsste
eine neue Route konsumieren.

**Katalog-Lücken:** Kein Endpoint. Heuristik ist im Frontend zu bauen
(Filter auf `Position.needs_price_review=True` + Suche in
`materialien[*].price_source in ('estimated','not_found')`).

---

## Phase 3 — Gap-Analyse

| Feature | Frontend-Stand | Backend-API | Aufwand B+4.3.1 |
|---|---|---|---|
| **LV-Upload** | ✓ voll da (`/dashboard/lvs/neu`) | ✓ `POST /lvs/upload[-async]` | 0 |
| **Preisliste-Upload** | ✓ voll da (`/dashboard/pricing/upload`, Direct-Backend-Fallback für >4,5 MB) | ✓ `POST /pricing/upload` | 0 |
| **Ergebnis-Tabelle mit Stage-Badges** | ✓ da (`/dashboard/lvs/[id]`, `stage-badge.tsx`, `price_source_summary` + `needs_price_review`) | ✓ `GET /lvs/{id}` liefert alle Felder | 0 (ggf. Politur) |
| **Near-Miss-Drawer (Top-3 Kandidaten)** | ✗ nicht vorhanden | ✗ **kein Endpoint** | **M** (Endpoint + Drawer) |
| **Manual-Override** | teilweise — Position-Edit gibt es indirekt via Review-Dialog *für Pricelist-Entries*, aber nicht für LV-Positionen-Overrides-Workflow | ✓ `PATCH /lvs/{id}/positions/{pid}` + `POST /pricing/overrides` | **S** (Button + Modal) |
| **Katalog-Lücken-Report** | ✗ | ✗ (rein frontend-aggregierbar oder neuer Endpoint) | **S–M** (je nach Ansatz) |

**Erkenntnis:** 3 der 6 Kernfunktionen sind bereits vollständig.
Die Lücken liegen bei Near-Miss, Manual-Override-UX und Lücken-Report.

---

## Phase 4 — Architektur-Vorschlag

### Wo lebt das Pilot-UI?

**Klar: Erweiterung des bestehenden Frontends in `lv-preisrechner/frontend/`.**
Kein neues Projekt. Gründe:

- Next.js + Tailwind + shadcn/ui + Auth + API-Client stehen.
- Die kritischen Seiten (`/dashboard/pricing/*`, `/dashboard/lvs/[id]`,
  `/dashboard/einstellungen`) sind **heute schon produktiv**.
- Pilot-Kunde klickt durch dieselben Routen, die Entwickler nutzen.

### Neue Komponenten vs. Erweiterungen

| Bereich | Anfassen | Typ |
|---|---|---|
| `/dashboard/lvs/[id]/page.tsx` | **erweitern** — Position-Zeile klickbar, öffnet Near-Miss-Drawer; pro Position ein „Preis manuell überschreiben"-Button | Refactor |
| `src/components/NearMissDrawer.tsx` | **neu** — Sheet/Dialog mit Top-3 Kandidaten und Button „Diesen Preis übernehmen" | Neu |
| `src/components/ManualOverrideDialog.tsx` | **neu** — Preis-Eingabe + optional „als Tenant-Override speichern" (triggert `POST /pricing/overrides`) | Neu |
| `/dashboard/lvs/[id]/gaps/page.tsx` | **neu** — Katalog-Lücken-Report als Tab/Seite: alle Positionen mit `needs_price_review=True`, gruppiert nach System | Neu |
| `src/lib/pricingApi.ts` | **erweitern** — `createOverride()`, `getLookupCandidates(lvId, posId)` (wenn Endpoint kommt) | Update |

### Neue Backend-Endpoints (Pflicht für Pilot)

1. **`GET /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates`**
   Für Near-Miss-Drawer. Liefert Top 3 `SupplierPriceEntry`-Kandidaten
   pro Position-Material — wiederverwendet `price_lookup.lookup_price`
   intern, liefert aber **alle** Stage-2c-Kandidaten mit
   Token-Coverage-Score statt nur den Gewinner.
   Aufwand: S (2 h). Logik liegt bereits in `price_lookup._best_fuzzy`.

2. *(optional)* **`GET /api/v1/lvs/{lv_id}/gaps`**
   Fasst alle `needs_price_review`-Positionen + `not_found`-Materialien
   zu einem Report zusammen. Für v1 rein frontend-seitig aggregierbar
   (siehe Position.materialien-JSON).
   Aufwand: XS wenn frontend-only, S wenn Backend.

### Sidebar-Ergänzung (Sehr klein)

- neuer Menüpunkt „Offene Preise" (Count-Badge aus
  `/lvs/{id}/gaps`-Ergebnis).
- „Overrides" und „Rabatt-Regeln" brauchen für Pilot noch kein eigenes
  Menü — sind Power-User-Features, bleiben erst mal API-only.

### Zeitschätzung für B+4.3.1

| Szenario | Zeit | Inhalt |
|---|---|---|
| **Best Case** | 4 h | Near-Miss-Drawer + Manual-Override-Dialog (beide neu), Position-Zeile klickbar, frontend-only Gaps-Tab. Candidates-Endpoint existiert (oder wird mit-drin gebaut). |
| **Realistisch** | 6–8 h | Wie oben plus neuer Backend-Endpoint `/candidates` (2 h) + Integration-Tests (1 h) + Visual-Polish (1 h) + eine unvorhergesehene Frontend-Type-Hürde (1 h). |
| **Worst Case** | 10–12 h | Zusätzlich: Override-Persist-Logik braucht Schema-Erweiterung (es gibt aktuell kein Feld „Override gilt nur für diese Position") + Migration + UI-Zustand (lokal vs. persistent) entwirren. |

### Risiken / Unbekannte

1. **Candidates-Endpoint-Performance**: `price_lookup` iteriert bei
   Stage 2c ggf. über 327 Kemmler-Entries. Bei 102 Positionen ×
   6 Materialien × 327 Candidates = ~200 k Vergleiche pro LV. Cache
   nötig, wenn das UI live nachlädt — oder Endpoint nur on-demand bei
   Drawer-Öffnung (aktueller Plan, damit unkritisch).

2. **Override-UX**: Soll ein Manual-Override nur diese eine Position
   betreffen (inline) oder als permanenter `TenantPriceOverride` in
   die Datenbank? User-Entscheidung — beide Varianten sind leicht
   bauzbar, aber Modell-Implikationen unterscheiden sich.

3. **Katalog-Lücken-Report-Scope**: „Fehlt im Katalog" vs. „Matcher
   schlägt fehl" sind zwei verschiedene Dinge. Der Frontend-Bericht
   kann das nicht unterscheiden, ohne Backend-Metadaten. → Pilot-v1
   zeigt beides zusammen, Power-User-v2 trennt es.

4. **Kein Test-Setup im Frontend**: Für eine Pilot-Demo unkritisch,
   für Yildiz-Rollout längerfristig sollte mindestens ein Smoke-Test
   mit Playwright stehen. Nicht Teil von B+4.3.1.

---

## Empfehlung für B+4.3.1

**Scope:**

1. `GET /lvs/{id}/positions/{pos_id}/candidates` im Backend neu (S, 2 h)
2. `NearMissDrawer` als Client-Component (S, 2 h)
3. `ManualOverrideDialog` als Client-Component, schreibt optional in
   `POST /pricing/overrides` (S, 1,5 h)
4. `/dashboard/lvs/[id]` erweitern: Klick auf Position-Zeile öffnet
   Drawer; Dropdown-Button „Preis überschreiben" (M, 1,5 h)
5. Optional: `/dashboard/lvs/[id]/gaps` als schneller Tab mit
   frontend-aggregierter Liste (S, 1 h)

**Zeit-Ziel:** 6–8 h realistisch.

**Abbruch-Bedingungen:** Frontend-Build oder -Typecheck scheitert an
Erweiterung der Position-Type → stopp, nicht raten. Backend-Endpoint
Performance > 2 s pro Position → stopp, nachbessern bevor UI-Integration.

**Nicht in B+4.3.1:** Test-Infrastruktur, Redesign der bestehenden
Tabellen, PDF-Vorschau-Pane, Bulk-Override-Editor.
