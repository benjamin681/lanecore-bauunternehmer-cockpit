# B+4.3.1c Abschluss — Katalog-Lücken-Tab

**Datum:** 22.04.2026
**Kontext-Doc:** `docs/b431c_catalog_gaps_tab_context.md`
**Baseline:** `docs/b431c_baseline.md`
**Branch:** `claude/beautiful-mendel`

---

## Status

- `CatalogGapsPanel` live als zweiter Tab in der LV-Detail-Page
- 9 neue Frontend-Tests grün (3 gapsApi + 6 CatalogGapsPanel)
- 2 zusätzliche Integrations-Tests in `lv-detail.test.tsx`
- Route-Zuwachs `/dashboard/lvs/[id]`: **10,8 kB → 12 kB** (+1,2 kB)
- Shared JS unverändert 87,2 kB
- Null Regressionen an Backend oder bestehenden Frontend-Flows

## Feature-Zusammenfassung

Die LV-Detail-Page hat jetzt zwei Tabs:

- **„Ergebnis"** (default): bestehende Positions-Tabelle aus
  B+4.3.1a/b (unverändert)
- **„Katalog-Lücken"**: neuer Tab mit Gaps-Übersicht

Der Gaps-Tab zeigt:

- Header: `{gaps_count} Lücken` + Severity-Breakdown
  („X fehlen · Y unsicher · Z Richtwerte")
- Toggle „Unsichere Matches einbeziehen" (Default off)
- Liste der Lücken, pro Eintrag:
  - Severity-Badge (`Fehlt im Katalog` / `Unsicher, bitte prüfen`
    / `Richtwert`)
  - Position-OZ + Position-Name + Material-Name
  - Button „Kandidaten prüfen" → öffnet `NearMissDrawer` für die
    betroffene Position (Re-Use aus B+4.3.1b)
- Empty-State: grünes Success-Panel mit `CheckCircle2`-Icon und
  „Alle Materialien haben einen Preis."

**Refetch nach Drawer-Action:**

1. User öffnet Drawer via „Kandidaten prüfen"
2. User setzt neuen EP im Drawer
3. `PATCH /lvs/{id}/positions/{pos_id}` läuft
4. Parent-`handleDrawerUpdated` → `await load()` + `setDataToken(t+1)`
5. `CatalogGapsPanel` re-fetched via `useEffect`-Dep auf `dataToken`
6. Lücke verschwindet aus der Liste, falls sie jetzt gelöst ist

## Dateien hinzugefügt

| Datei | LOC | Zweck |
|---|---|---|
| `src/lib/gapsApi.ts` | 73 | Types (1:1 zu `backend/app/schemas/gaps.py`) + `fetchGaps(lvId, includeLowConfidence=false)` |
| `src/components/CatalogGapsPanel.tsx` | ~220 | Panel: Toggle + Counter-Header + Liste + Empty + Error + Skeleton |

Plus 2 neue Test-Dateien:

| Datei | Tests |
|---|---|
| `src/__tests__/gapsApi.test.tsx` | 3 |
| `src/__tests__/catalog-gaps-panel.test.tsx` | 6 |

## Dateien erweitert

| Datei | Änderung |
|---|---|
| `src/app/dashboard/lvs/[id]/page.tsx` | Tab-State (`activeTab`, `dataToken`), `handleDrawerUpdated`, `handleGapsOpenPosition`, Tab-Switcher mit `role="tablist"`, Conditional Render Tabelle vs. Panel, Drawer-`onUpdated` auf `handleDrawerUpdated` umgestellt |
| `src/__tests__/lv-detail.test.tsx` | +2 Integrations-Tests (Tab-Switch + Gap-Click → Drawer), `fetchGaps` in `mocks`, `@/lib/gapsApi` partial-mock via `importActual` |

## Test-Bilanz

| Suite | Tests | Laufzeit |
|---|---|---|
| Backend (pytest) | **412 passed** | ~40 s |
| Frontend (vitest) | **36 passed** | ~4 s |
| **Gesamt** | **448** | |

Frontend-Entwicklung: 25 (nach B+4.3.1b) → **36** (nach B+4.3.1c).

## Wording-Implementation (Zusammenfassung)

Neue Panel-Komponente vollständig nach `ui_wording_guide.md`:

| Kontext | Label |
|---|---|
| Tab 1 | „Ergebnis" |
| Tab 2 | „Katalog-Lücken" |
| Severity missing | „Fehlt im Katalog" (Badge `danger`) |
| Severity low_confidence | „Unsicher, bitte prüfen" (Badge `warning`) |
| Severity estimated | „Richtwert" (Badge `default`) |
| Button | „Kandidaten prüfen" (+ ArrowRight-Icon) |
| Toggle | „Unsichere Matches einbeziehen" |
| Empty-State | „Alle Materialien haben einen Preis." |
| Error | „Lücken konnten nicht geladen werden." + Retry |
| Position-Miss-Toast | „Position nicht gefunden — bitte Seite neu laden." |

## Follow-ups

### FU-C1 — Tab-Badge mit `gaps_count`

- Panel gibt aktuellen Count via Callback hoch, Tab-Label zeigt
  „Katalog-Lücken (15)"
- Scope: ~20 min, nach Pilot-Feedback prüfen ob Nutzer es
  wirklich brauchen (sonst Rauschen)

### FU-C2 — Roving-Tabindex für Tab-Keyboard-Navigation

- Left/Right Arrow zwischen Tabs (ARIA-Best-Practice)
- Aktueller Stand: nur Focus + Enter (ARIA-konform aber nicht
  Best-in-Class)
- Scope: ~30 min, Accessibility-Feinschliff

### FU-C3 — URL-State für Deep-Links

- `?tab=gaps` persistiert Tab-Auswahl
- Ermöglicht Teilen von Links, Browser-Back-Navigation, Bookmarks
- Scope: ~45 min

## Pilot-Readiness nach B+4.3.1c

**Pilot-UI-Feature-Set ist komplett:**

| Feature | Block | Status |
|---|---|---|
| LV-Upload | bestand | ✓ |
| Preisliste-Upload | bestand | ✓ |
| Kalkulation mit Ergebnis-Tabelle | bestand | ✓ |
| Stage-Badges pro Position | B+4.2 / B+4.3.1a | ✓ |
| Near-Miss-Drawer mit Kandidaten | B+4.3.1b | ✓ |
| **Katalog-Lücken-Tab** | **B+4.3.1c (heute)** | **✓** |

### Nächste Schritte bis Pilot-live

| Block | Geschätzter Aufwand |
|---|---|
| Hetzner-Deployment-Setup (Infrastruktur, Secrets, Domain, TLS) | 4–6 h |
| Basic-Monitoring (Sentry / Uptime-Kuma / Access-Logs) | 2–3 h |
| AVV + TOM + Onboarding-Doc | 3–4 h |
| Pilot-Onboarding-Test (Benjamin macht Dry-Run) | 2 h |
| **Gesamt bis Pilot-Live** | **~11–15 h** |

Feature-seitig ist der Pilot bereit. Offene Blöcke sind
Infrastruktur + Dokumentation.

## Session-Commit-Stack B+4.3.1c

```
(Abschluss-Doc-Commit folgt direkt)
28cb78f feat(frontend): B+4.3.1c integrate CatalogGapsPanel as tab in LV detail page
1d01d5e feat(frontend): B+4.3.1c CatalogGapsPanel component
a67f730 feat(frontend): B+4.3.1c gaps API client and types
cbe6bdf docs: B+4.3.1c baseline and design decisions for catalog gaps tab
```

## Nächster logischer Block

**Feature-Arbeit an der Pilot-UI ist fertig.** Der nächste
sinnvolle Block ist **nicht** ein weiterer UI-Block, sondern:

**B+4.3.2 — Deployment-Vorbereitung**
- Hetzner-Setup (Backend + Frontend)
- Secrets-Management (ANTHROPIC_API_KEY, JWT_SECRET, DB)
- Reverse-Proxy + TLS
- Healthcheck-Endpoints
- Monitoring-Skelett

Sobald das läuft, kann Benjamin einen Pilot-Account seed-en und
den Stuttgart-LV-Flow end-to-end durchspielen.
