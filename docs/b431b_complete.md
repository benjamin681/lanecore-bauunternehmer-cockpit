# B+4.3.1b Abschluss — Near-Miss-Drawer

**Datum:** 22.04.2026
**Kontext-Doc:** `docs/b431b_near_miss_drawer_context.md`
**Baseline:** `docs/b431b_baseline.md`
**Branch:** `claude/beautiful-mendel`

---

## Status

- NearMissDrawer live in der LV-Detail-Page
- **Option A** aus Phase 4 umgesetzt (informativer Drawer +
  Gesamt-EP-Override, kein Material-granularer Takeover)
- **9 neue Frontend-Tests** grün
- Null Regressionen an Backend oder bestehenden Frontend-Flows
- Next.js-Build weiterhin grün (alle 12 Routen kompilieren)

## Feature-Zusammenfassung

Bei Klick auf die `StageBadge` einer Position öffnet sich ein
Side-Right-Drawer mit:

- Top-3 Kandidaten pro Material im Accordion (erstes Material
  standardmäßig offen)
- Pro Kandidat: Lieferantenname (pricelist_name), Produktname,
  Stage-Label (Wording-Guide-konform), Confidence-Übersetzung,
  Preis + Einheit, match_reason als italic Hinweis
- Klick auf eine Kandidaten-Zeile befüllt den EP-Input als
  Vorschlag (`candidate.price_net × required_amount`)
- EP-Input bleibt editierbar — letzter Klick gewinnt, keine
  Confirmation beim Überschreiben
- Submit → `PATCH /lvs/{id}/positions/{pos_id}` mit neuem EP →
  Toast „Preis übernommen" → Parent ruft `load()` → Drawer-Close

## Dateien hinzugefügt

| Datei | LOC | Zweck |
|---|---|---|
| `src/components/ui/drawer.tsx` | 225 | Side-Right-Primitive mit Portal, Focus-Trap, ESC, Slide-in |
| `src/components/ui/accordion.tsx` | 215 | Compound-API-Primitive, single-mode, ARIA-konform |
| `src/components/NearMissDrawer.tsx` | 310 | Business-Komponente: Fetch, Loading/Error/Loaded, Actions |
| `src/lib/candidatesApi.ts` | 94 | Fetcher + Types (Stage, Candidate, MaterialWithCandidates, PositionCandidates) |

Plus 4 neue Test-Dateien:

| Datei | Tests |
|---|---|
| `src/__tests__/ui-drawer.test.tsx` | 3 |
| `src/__tests__/ui-accordion.test.tsx` | 3 |
| `src/__tests__/candidatesApi.test.tsx` | 3 |
| `src/__tests__/near-miss-drawer.test.tsx` | 7 |

## Dateien erweitert

| Datei | Änderung |
|---|---|
| `src/app/dashboard/lvs/[id]/page.tsx` | Import + Drawer-State + `openDrawer`/`closeDrawer` + Drawer-Mount am Render-Ende |
| `PosRow` (in selber Datei) | StageBadge in Wrapper-`<button>` mit `aria-label`, hover, focus-ring |
| `src/__tests__/lv-detail.test.tsx` | +2 Integrations-Tests; candidatesApi-Mock + `fetchCandidates`/`updatePositionEp` in `mocks` |

## Test-Bilanz

| Suite | Tests | Laufzeit |
|---|---|---|
| Backend (pytest) | **412 passed** | ~40 s |
| Frontend (vitest) | **25 passed** | ~3,2 s |
| **Gesamt** | **437** | |

Frontend-Suite-Entwicklung: 7 (nach B+4.3.1a) → 25 (nach B+4.3.1b).

Bundle-Zuwachs `/dashboard/lvs/[id]`: **7,35 kB → 10,8 kB** (+3,45 kB).
Shared JS unverändert 87,2 kB.

## Wording-Migration (teilweise)

Die neue Near-Miss-Drawer-Komponente nutzt Wording-Guide-konforme
Labels:

- **Stage-Labels:** „Preis gefunden" / „Ähnlicher Artikel" /
  „Richtwert" statt `supplier_price` / `fuzzy` / `estimated`
- **Confidence-Übersetzung:** „fast sicher" (≥0,85) /
  „wahrscheinlich passend" (≥0,7) / „eher unsicher" (≥0,5) /
  „unsicher, bitte prüfen" (<0,5) — **keine Prozentzahlen im UI**
- **Action-Label:** „Preis selbst eintragen" (statt „Manual
  Override")
- **Toasts:** „Preis übernommen" / „Fehler: …" / „Bitte einen
  gültigen Preis eingeben."

Bestehende Komponenten sind **nicht** migriert:
- `StageBadge`-Globale Labels (in Tabelle `/dashboard/lvs/[id]`):
  „Lieferantenpreis" / „Schätzwert" / „Altpreis" / „Keine
  Preisquelle" (pre-B+4.3.1b)
- Upload-Seiten (`/dashboard/lvs/neu`, `/dashboard/pricing/upload`)
- Generische Error-Messages

Globale Migration = **FU-D**, separater Block nach Pilot-Feedback.

## Follow-ups

### FU-A — Material-granulare Overrides mit Audit-Trail

- Neuer Backend-Endpoint
  `POST /lvs/{id}/positions/{pos_id}/override-material`
- Audit-Model (`position_material_overrides`-Tabelle) für
  Nachvollziehbarkeit: welcher Kandidat wurde wann gewählt
- Frontend-Anpassung: „Übernehmen"-Button pro Material statt nur
  Gesamt-EP-Input
- Trigger: wenn Pilot-Feedback zeigt, dass der aktuelle Drawer-Flow
  nicht reicht

### FU-B — `materialien`-JSON-Konsistenz bei EP-Override

- Aktuell: `PATCH { ep }` aktualisiert das persistierte
  `materialien`-JSON einer Position **nicht** — es bleibt der
  letzte Kalkulations-Stand stehen
- Ziel: atomares Update von `materialien` + `ep`, sodass die
  Detail-Ansicht konsistent mit dem EP ist
- Aktueller Blocker: nicht sichtbar im Pilot (User sieht EP,
  Materialien-Details sind sekundär); wird relevant mit FU-A

### FU-C — Touch-Device-Support für Drawer-Trigger

- `StageBadge`-Wrapper hat Hover-State + `cursor-pointer` — auf
  Touch unsichtbar
- Separater Block für Mobile-UX, wenn Pilot-Nutzer auf mobile
  Geräte gehen

### FU-D — Globale Wording-Migration

- Bestehende Strings (StageBadge, Error-Messages, Upload-Flows)
  auf Wording-Guide-Standard bringen
- Block **B+4.3.1d** nach Pilot-Feedback

## Pilot-Readiness

B+4.3.1b ist **pilot-tauglich als Feature**:

- User kann Preise nachvollziehen („Warum dieser Preis?"
  beantwortet durch Kandidaten-Liste)
- User kann EP manuell überschreiben mit Orientierungshilfe durch
  Kandidaten
- Daten aus Backend-API live (kein Mock) — Candidates-Endpoint
  (B+4.3.0b) und `PATCH Position` (bestehend) arbeiten

**Offene Blöcke bis Pilot-ready im engeren Sinne (Hetzner-Live):**
- B+4.3.1c Katalog-Lücken-Tab (Konsumiert `/lvs/{id}/gaps`, live
  seit B+4.3.0c)
- Hetzner-Deployment-Setup
- Basic-Monitoring (Sentry / Uptime-Kuma)
- AVV + TOM + Onboarding-Doc

## Commit-Stack B+4.3.1b (6)

```
(7. docs-commit folgt direkt nach dieser Datei)
ec45e0e feat(frontend): B+4.3.1b integrate NearMissDrawer into LV detail page
34b5a1a feat(frontend): B+4.3.1b NearMissDrawer component
6d6c640 feat(frontend): B+4.3.1b candidates API client and types
653768b feat(frontend): B+4.3.1b add drawer and accordion primitives
0a16069 docs: B+4.3.1b baseline and design decisions for near-miss drawer
```

## Nächster Block

**B+4.3.1c — Katalog-Lücken-Tab**
- Konsumiert `GET /api/v1/lvs/{id}/gaps` (live seit B+4.3.0c)
- Liste der `missing` / `estimated` (/ optional `low_confidence`)
  Materialien pro LV
- Separater Tab oder Section in der LV-Detail-Page
- UI-Pattern: Tabelle mit Filter (Severity), pro Zeile Link zurück
  zur Position + „Preis selbst eintragen"-Shortcut (nutzt
  bestehenden Drawer oder inline-Input, Entscheidung in
  B+4.3.1c-Baseline)

Frontend-Smoke-Infrastruktur aus B+4.3.1a bleibt die Grundlage.
