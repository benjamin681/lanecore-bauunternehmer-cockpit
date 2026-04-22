# B+4.3.1c — Katalog-Lücken-Tab: Baseline

**Stand:** 22.04.2026
**Kontext-Doc:** `docs/b431c_catalog_gaps_tab_context.md`
**Abhängigkeiten:** B+4.3.0c (Gaps-Endpoint live), B+4.3.1b
(Near-Miss-Drawer).

---

## 1. Scope

Neuer Tab in der LV-Detail-Page für Katalog-Lücken. Der Handwerker
sieht auf einen Blick, welche Materialien noch einen Preis brauchen,
und kann direkt per Klick den bestehenden NearMissDrawer für die
betroffene Position öffnen.

- Datenquelle: `GET /api/v1/lvs/{lv_id}/gaps?include_low_confidence=bool`
  (live seit B+4.3.0c)
- UI: zwei `<button>`-Tabs über der Positions-Tabelle, umschaltet
  zwischen „Ergebnis" und „Katalog-Lücken"
- Re-Use: Klick auf Lücken-Eintrag ruft bestehendes
  `openDrawer(position)` in der Page auf → NearMissDrawer aus
  B+4.3.1b öffnet
- Refetch-Token wird vom Parent nach jedem Drawer-Save hochgezählt
  → Panel aktualisiert Gap-Count automatisch

---

## 2. Design-Entscheidungen

### a) UI-Pattern: **Variante A** — zwei Header-Buttons als Tab-Switch

**Begründung:** Keine neue Tab-Primitive nötig, zwei
`<button aria-pressed>` mit Tailwind reichen. Kompakte Anzeige
direkt über der Positions-Tabelle, kein Route-Wechsel. Pfad zu
Unter-Route (Variante B) bleibt offen — State-Flag kann später
durch URL-Query ersetzt werden.

### b) `include_low_confidence`-Toggle: **Default off**, entspricht API

**Begründung:** Backend-Default ist `false`. Der Pilot soll
zunächst echte Lücken (`missing` + `estimated`) sehen; die
unsicheren supplier_price-Matches sind „ein bisschen wackelig" aber
nicht Blocker — Opt-in passt.

Toggle-Styling: native `<input type="checkbox">` mit Tailwind,
wie in `einstellungen/page.tsx` etabliert.

### c) Severity-Darstellung: **Badge + Wording-Guide-Labels**

| Severity | Badge-Variante | Label |
|---|---|---|
| `missing` | `danger` | „Fehlt im Katalog" |
| `low_confidence` | `warning` | „Unsicher, bitte prüfen" |
| `estimated` | `default` | „Richtwert" |

Labels und Farbkodierung aus `docs/ui_wording_guide.md`. Keine
Prozentzahlen im UI.

### d) Listen-Interaktion: **Klick öffnet NearMissDrawer**

**Brückenschlag zu B+4.3.1b.** Position-Lookup via
`lv.positions.find(p => p.id === gap.position_id)` (kein extra
API-Call). Fällt der Lookup fehl (z. B. weil das LV nach Reload
eine andere Position-Sequenz hat), wird der Klick als No-Op
behandelt und ein Fallback-Toast gezeigt.

**Sortierung:** Backend liefert bereits sortiert
(`missing > low_confidence > estimated`, innerhalb nach
`position_oz`). Backend-Reihenfolge **1:1 übernehmen**.

### e) Zähler: **`gaps_count` als Tab-Badge**, Breakdown im Panel

- Tab-Label: „Katalog-Lücken 126" (Count aus aktuellem Report)
- Panel-Header: „126 Lücken · 64 fehlen · 62 Richtwerte · 0
  unsicher"

### f) Details-Button-Label: **„Kandidaten prüfen"** + ArrowRight-Icon

**Wording-Guide-Recherche:** Der Guide hat keinen expliziten Button-
Eintrag für „Details öffnen". Stilprägende Patterns:

- „Preis gefunden" / „Richtwert" (aktive Labels)
- „bitte prüfen vor Abgabe" (explizite Aktion)
- „Ähnliche Artikel, die passen könnten" (beschreibend)

**Entscheidung: „Kandidaten prüfen"** — konkreter als „Details",
aktiv formuliert, lehnt sich an das Guide-Pattern „prüfen" an.
ArrowRight-Icon macht klar, dass eine neue Ansicht aufgeht.

### Zusatz-UX: Refetch-Token nach Drawer-Update

In `page.tsx`:

```ts
const [dataToken, setDataToken] = useState(0);

async function onDrawerUpdated() {
  await load();              // LV neu laden (bestehend)
  setDataToken(t => t + 1);  // Gaps-Panel zur Refetch animieren
}
```

`CatalogGapsPanel` erhält `dataToken` als Prop, hat es im
`useEffect`-Dependency-Array. Token-Increment → Refetch, kein
imperativer Ref nötig.

---

## 3. Komponenten-Plan

### Neue Dateien

| Datei | LOC (grob) | Zweck |
|---|---|---|
| `src/lib/gapsApi.ts` | ~50 | Types + `fetchGaps(lvId, includeLowConfidence=false)` |
| `src/components/CatalogGapsPanel.tsx` | ~200 | Panel: Toggle + Header-Stats + Liste + Empty-State |

### Erweiterte Dateien

| Datei | Änderung |
|---|---|
| `src/app/dashboard/lvs/[id]/page.tsx` | `activeTab`-State, `dataToken`-State, Tab-Switch-Buttons, Conditional Render, Panel-Mount, Token-Increment in `onDrawerUpdated` |

### Unberührt bleiben

- `NearMissDrawer`, `drawer.tsx`, `accordion.tsx`, `candidatesApi.ts`
- `StageBadge` (global in der Positions-Tabelle weiterhin aktiv)
- Backend-Routen und -Schemas
- Alle bestehenden Tests

---

## 4. API-Integration

### `src/lib/gapsApi.ts`

```ts
import { api } from "@/lib/api";

export type GapSeverity = "missing" | "low_confidence" | "estimated";

export interface CatalogGapEntry {
  position_id: string;
  position_oz: string;
  position_name: string;
  material_name: string;
  material_dna: string;
  required_amount: number;
  unit: string;
  severity: GapSeverity;
  price_source: string;
  match_confidence: number | null;
  source_description: string;
  needs_review: boolean;
}

export interface LVGapsReport {
  lv_id: string;
  total_positions: number;
  total_materials: number;
  gaps_count: number;
  missing_count: number;
  estimated_count: number;
  low_confidence_count: number;
  gaps: CatalogGapEntry[];
}

export async function fetchGaps(
  lvId: string,
  includeLowConfidence: boolean = false,
): Promise<LVGapsReport> {
  const q = includeLowConfidence ? "?include_low_confidence=true" : "";
  return api<LVGapsReport>(`/lvs/${lvId}/gaps${q}`);
}
```

Types 1:1 aus `backend/app/schemas/gaps.py`.

### Datenfluss

1. Tab-Switch zu „Katalog-Lücken" → Panel mountet → `fetchGaps` mit
   aktuellem Toggle-State.
2. Toggle-Click → lokaler State-Wechsel → `useEffect`-Refetch.
3. Klick auf Listen-Eintrag → `onOpenDrawer(position)` der Parent-
   Page → NearMissDrawer öffnet.
4. Drawer-Save → Parent-`onDrawerUpdated` → `load()` + Token-
   Increment → Panel refetched Gaps.

---

## 5. UI-Layout (Skizze)

```
┌ LV-Detail ───────────────────────────────────────────┐
│ Kopfzeile: Projektname + Summe                        │
│ Parsing-Hinweis (falls stuck/error)                   │
│ Action-Bar: [Kalkulieren] [PDF exportieren] ...       │
├──────────────────────────────────────────────────────┤
│ [ Ergebnis (102) ]  [ Katalog-Lücken 126 ]            │   <-- Tab-Switch
├──────────────────────────────────────────────────────┤
│  wenn activeTab=results:                              │
│    <Positions-Tabelle />                              │
│  wenn activeTab=gaps:                                 │
│    <CatalogGapsPanel />                               │
├──────────────────────────────────────────────────────┤
│ <NearMissDrawer /> (unverändert)                      │
└──────────────────────────────────────────────────────┘
```

### `CatalogGapsPanel` intern

```
┌──────────────────────────────────────────────────────┐
│ 126 Lücken · 64 fehlen · 62 Richtwerte · 0 unsicher   │
│                                                       │
│ [×] Unsichere Matches einbeziehen                     │
├──────────────────────────────────────────────────────┤
│ Pos.   Material              Severity      Aktion    │
├──────────────────────────────────────────────────────┤
│ 01.02  Fireboard 12.5   [Fehlt im K.]  Kandidaten... │
│ 01.03  Dämmung 40mm     [Richtwert]    Kandidaten... │
│ ...                                                   │
└──────────────────────────────────────────────────────┘
```

### Empty-State (gaps_count == 0)

```
┌──────────────────────────────────────────────────────┐
│ ✓ Alle Materialien haben einen Preis.                 │
└──────────────────────────────────────────────────────┘
```

Positiv konnotiert, Success-Grün, ohne CTA.

---

## 6. Wording-Mapping (Zusammenfassung)

| Kontext | Label |
|---|---|
| Tab „Ergebnis" | „Ergebnis" + `({positionen_gesamt})` |
| Tab „Katalog-Lücken" | „Katalog-Lücken" + `({gaps_count})` |
| Panel-Header | „{N} Lücken · {M} fehlen · {E} Richtwerte · {LC} unsicher" |
| Toggle | „Unsichere Matches einbeziehen" |
| Severity Badge | wie §2c |
| Listen-Action | „Kandidaten prüfen" + ArrowRight |
| Empty-State | „Alle Materialien haben einen Preis." |
| Loading | Skeleton-Pulse-Blöcke (wie NearMissDrawer) |
| Error | „Lücken konnten nicht geladen werden. [Erneut versuchen]" |
| Fallback-Toast (Position-Lookup fehlgeschlagen) | „Position nicht mehr verfügbar — bitte Seite neu laden." |

Bestehende Strings außerhalb des neuen Tabs bleiben **unverändert**
(globale Wording-Migration = B+4.3.1d).

---

## 7. Test-Strategie

### Phase 2 — `gapsApi.ts` (2 Tests)

- `fetchGaps` mit Default (ohne `?`-Query)
- `fetchGaps` mit `includeLowConfidence=true`
  (`?include_low_confidence=true`)

### Phase 3 — `CatalogGapsPanel` (4–5 Tests)

- Loading-Skeleton sichtbar während fetch
- Geladene Liste rendert Severity-Badges + Labels
- Empty-State bei `gaps_count=0`
- Toggle-Click triggert Refetch mit `true`
- Details-Button-Click ruft `onOpenDrawer(position_id)` auf

### Phase 4 — LV-Detail Tab-Integration (1–2 Tests)

- Tab-Switch rendert Panel statt Tabelle (und zurück)
- Token-Increment nach Drawer-Save triggert Gaps-Refetch

Mock-Strategie wie B+4.3.1b: `vi.hoisted()` für shared Mocks,
`@/lib/gapsApi` partial-gemockt, `openDrawer`-Stub.

---

## 8. Phasen-Plan + Aufwand

| Phase | Inhalt | Zeit |
|---|---|---|
| 1 | Baseline-Doc (dieser Doc-Commit) | 15 min |
| 2 | `gapsApi.ts` + 2 Unit-Tests | 15 min |
| 3 | `CatalogGapsPanel.tsx` + 4–5 Smoke-Tests | 40 min |
| 4 | Tab-Switch in `lvs/[id]/page.tsx` + 1–2 Tests | 20 min |
| 5 | Abschluss-Doc + Full Build + Push | 10 min |
| **Gesamt** | | **~1h 40min** |

Pufferung: wenn Tab-Switch State-Koordination mit Drawer komplex
wird (eine Kollision zwischen `activeTab`-State und `drawerOpen`-
State wäre denkbar), Phase 4 +15 min.

Kosten: 0 $.

---

## 9. Verifikations-Kriterien (Abschluss)

- Frontend-Tests: 25 (bestehend) + 7–9 (neu) = 32–34 grün
- Backend-Tests: 412 unverändert grün
- `npx tsc --noEmit` grün
- Next.js-Build grün, `/dashboard/lvs/[id]` wächst moderat
  (geschätzt +2 kB)
- Preview-Dev-Server rendert unverändert (vor Activation des Tabs)

---

## 10. Follow-ups (nicht in B+4.3.1c)

- **Deep-Link / URL-State:** `?tab=gaps` als Query-Param, damit
  Links zu Gaps-Sicht geteilt werden können (Variante B-Migration).
- **Inline-Preis-Eingabe pro Gap** ohne Drawer-Detour — aktuell
  geht jeder Fix über NearMissDrawer. Für häufige „nur schnell
  einen Preis eintragen"-Fälle könnte ein Inline-Input im Gaps-
  Panel schneller sein (Pilot-Feedback abwarten).
- **Export der Lücken-Liste** als PDF oder Excel für Einkauf.
- **Benachrichtigung** wenn neue Preislisten hochgeladen werden und
  dadurch einzelne Gaps verschwinden könnten.
