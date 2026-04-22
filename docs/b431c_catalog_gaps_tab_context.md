# B+4.3.1c — Katalog-Lücken-Tab: Kontext & Plan

**Stand:** 22.04.2026
**Zweck:** Vor-Analyse + Design-Entscheidungen. Kein Code, kein Commit.
**Abhängigkeit:** B+4.3.0c (Gaps-Endpoint live), B+4.3.1b (Near-Miss-Drawer).

---

## 1. Bestehende LV-Detail-Struktur

Datei: `src/app/dashboard/lvs/[id]/page.tsx` (~420 LOC nach B+4.3.1b)

### Aktuelle Sections

```
<div class="space-y-6">
  <div>...Kopfzeile mit projekt_name + Summe...</div>
  {/* Parsing-Hinweis bei stuck/error */}
  {stuckOrError && <div class="rounded-xl ...">...</div>}
  {/* Action-Bar */}
  <div class="rounded-xl ...">
    <Button onClick={runKalkulation}>Kalkulieren</Button>
    <Button onClick={exportPdf}>Als PDF exportieren</Button>
    ...
  </div>
  {/* Positions-Tabelle */}
  <div class="rounded-xl bg-white border ..."><table>...</table></div>
  {/* Near-Miss-Drawer (B+4.3.1b) */}
  <NearMissDrawer ... />
</div>
```

**Keine Tabs, keine Sub-Routes, keine Scroll-Navigation** heute. Die
Page ist flach aufgebaut. Das neue Gaps-UI kann an zwei Stellen
landen:

- **Zwischen Action-Bar und Positions-Tabelle** als eigener
  Switch/Tab-Bereich
- **Unterhalb der Positions-Tabelle** als Collapsible Section

### Navigations-Pattern im Projekt

Keine zentrale Tabs-Komponente. Das einzige Tabs-ähnliche Element
ist der Seitenleisten-Menüpunkt („Lieferanten-Preise (Beta)") —
gewöhnliche Navigation.

**Konsequenz:** Tab-Primitive müsste neu gebaut werden — oder wir
nutzen einen leichteren Ansatz.

---

## 2. Tab-Pattern-Entscheidung

### Bewertung

| Option | Pro | Contra |
|---|---|---|
| **A — Tabs innerhalb der Page** (Ergebnis / Katalog-Lücken) | Nah an der Kalkulation, keine Route-Änderung, kompakt | Neue Tabs-Primitive oder zwei Buttons mit state-flag |
| B — Unter-Route `/dashboard/lvs/[id]/gaps` | Saubere URLs, Deep-Link-fähig | Extra Routing, doppelte LV-Datenlad-Logik, für Pilot Overkill |
| C — Collapsible Section unter der Tabelle | Minimal, keine neue Primitive | Lücken sind unter dem Fold, User muss scrollen, schlechter Signal-Wert |

### Empfehlung: **Variante A** — zwei Header-Buttons als Tab-Switch

**Begründung:**
- Kein neues Tab-Primitive nötig. Zwei `<button>`-Elemente mit
  `aria-pressed` und dynamischer Tailwind-Klasse reichen für
  Pilot-Qualität.
- Sichtbarer Einstiegspunkt oben in der Page — User sieht auf einen
  Blick „X Positionen gematcht, Y Lücken".
- Count-Badge am Tab-Label („Katalog-Lücken 126") liefert Signal
  ohne zusätzliches UI-Element.
- Pfad zur Deep-Link-fähigen Sub-Route (Variante B) bleibt offen —
  State-Flag kann später durch URL-Query ersetzt werden.

**UI-Skizze:**

```
┌──────────────────────────────────────────────────┐
│ [Ergebnis (102)] [Katalog-Lücken 126]            │
├──────────────────────────────────────────────────┤
│ ... aktive Section (Tabelle ODER Gaps-Liste) ... │
└──────────────────────────────────────────────────┘
```

Die Count-Zahlen kommen aus dem LV (`positionen_gesamt`) bzw. aus
der ersten Gaps-API-Response (`gaps_count`).

---

## 3. Komponenten-Inventar

### Vorhanden (wiederverwendbar)

| Komponente | Nutzung in B+4.3.1c |
|---|---|
| `Button` | Tab-Header-Buttons |
| `Badge` | Severity-Darstellung + Count-Chips am Tab |
| `NearMissDrawer` | **Klick auf Gap-Eintrag öffnet den Drawer** — eleganter Brückenschlag zu B+4.3.1b |
| `StageBadge` | nicht benötigt (Gaps haben eigene Severity-Enum) |
| nativer Checkbox-Style (siehe `einstellungen/page.tsx`) | Toggle „Unsichere Matches einbeziehen" |

### Zu bauen

| Komponente | LOC (grob) |
|---|---|
| `src/lib/gapsApi.ts` (Types + Fetcher) | ~40 |
| `src/components/CatalogGapsPanel.tsx` — Panel mit Toggle, Counter-Badges, Liste | ~200 |

Keine neue UI-Primitive (keine Tabs, kein Switch) — alles über
vorhandene Bausteine + Tailwind.

---

## 4. API-Integration

### Neuer Client `src/lib/gapsApi.ts`

```ts
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

export async function fetchLVGaps(
  lvId: string,
  includeLowConfidence = false
): Promise<LVGapsReport>;
```

Signatur gespiegelt aus `backend/app/schemas/gaps.py` (live seit
B+4.3.0c). `include_low_confidence` default `false` — wie
Backend-API.

### Datenfluss

1. Panel mountet (Tab wird geöffnet) → `fetchLVGaps(lvId, false)`
2. Toggle „Unsichere Matches einbeziehen" → refetch mit `true`
3. Klick auf Gap-Eintrag → Parent-State setzt `drawerPosId` →
   NearMissDrawer öffnet für betroffene Position
4. Nach PATCH im Drawer (EP-Override) → LV-`load()` → zusätzlich
   Gaps-Refetch (damit Count-Badge aktualisiert)

---

## 5. UI-Layout-Skizze

```
┌ CatalogGapsPanel ────────────────────────────────────┐
│ ┌─────────────────────────┐ ┌───────────────────┐   │
│ │ 126 Lücken gefunden     │ │ [×] Unsichere     │   │
│ │ · Fehlt: 64             │ │     Matches       │   │
│ │ · Richtwert: 62         │ │     einbeziehen   │   │
│ │ · Unsicher: 0           │ │                   │   │
│ └─────────────────────────┘ └───────────────────┘   │
├──────────────────────────────────────────────────────┤
│ Pos.    Material           Severity      Aktion     │
├──────────────────────────────────────────────────────┤
│ 01.02   Fireboard 12.5     [Fehlt im K.] [Details]  │
│ 01.03   Dämmung 40mm       [Richtwert]   [Details]  │
│ 01.05   GKF-Platte         [Fehlt im K.] [Details]  │
│ ...                                                  │
└──────────────────────────────────────────────────────┘
```

### Wording (aus `ui_wording_guide.md`)

| Severity | Label |
|---|---|
| `missing` | „Fehlt im Katalog" (rot/danger) |
| `low_confidence` | „Unsicher, bitte prüfen" (orange/warning) |
| `estimated` | „Richtwert" (gelb/warning oder grau/default) |

Toast bei erfolgreichem EP-Override im Drawer bleibt wie B+4.3.1b:
„Preis übernommen". Gaps-Panel refetched automatisch nach
LV-`load()`.

### Leerer Zustand

```
┌──────────────────────────────────────────────────────┐
│ ✓ Keine Lücken. Alle Materialien haben einen Preis.  │
└──────────────────────────────────────────────────────┘
```

Positiv konnotiert mit success-Farbe, großes Häkchen. Kein CTA
nötig.

---

## 6. Re-Use der NearMissDrawer für Listen-Einträge

**Eleganter Brückenschlag zu B+4.3.1b.** Statt in B+4.3.1c eine
separate Detail-Ansicht zu bauen:

- Liste im Gaps-Panel hat pro Zeile einen „Details"-Button.
- Click ruft `openDrawer(p)` in der LV-Detail-Page auf — exakt
  derselbe Flow wie der StageBadge-Click in der Positions-Tabelle.
- Voraussetzung: Panel bekommt `onOpenDrawer(position)`-Callback
  als Prop; Page gibt ihn rein.

Für die Position-Lookup per ID braucht der Callback die volle
Position (nicht nur die ID), weil `openDrawer` in B+4.3.1b auch
`currentEp` erwartet. Der Gap-Eintrag liefert nur `position_id`;
die Position kommt aus dem bereits geladenen `lv.positions`-Array
(Lookup per `id`). Sauber und ohne zusätzlichen API-Call.

---

## 7. Implementierungs-Plan

### Phase 1 — Baseline (15 min)

- `docs/b431c_baseline.md` mit Design-Entscheidungen + UI-Skizze +
  Wording-Mapping
- Commit: „docs: B+4.3.1c baseline and design decisions for
  catalog gaps tab"

### Phase 2 — gapsApi-Client + Tests (15 min)

- `src/lib/gapsApi.ts` (~40 LOC)
- `src/__tests__/gapsApi.test.tsx` (2 Tests: URL mit und ohne
  `include_low_confidence`)
- Commit: „feat(frontend): B+4.3.1c gaps API client and types"

### Phase 3 — CatalogGapsPanel-Komponente + Tests (40 min)

- `src/components/CatalogGapsPanel.tsx` (~200 LOC)
- Props: `lvId`, `onOpenDrawer(posId: string)`,
  `refetchToken: number` (Parent triggert Refetch per
  inkrementiertem Token nach Drawer-Save)
- 4–5 Smoke-Tests:
  - Loading-Skelett, Error-Retry, Empty-State, Liste mit Severity-
    Badges, Toggle-Refetch, Details-Button triggert `onOpenDrawer`
- Commit: „feat(ui): B+4.3.1c CatalogGapsPanel with severity
  filter + drawer hand-off"

### Phase 4 — Tab-Switch in LV-Detail-Page (20 min)

- Zwei `<button>`-Tabs mit `aria-pressed` über der Positions-
  Tabelle
- State: `activeTab: "results" | "gaps"`
- Conditional Render der Positions-Tabelle bzw. des Panels
- Refetch-Token wird im Drawer-`onUpdated` inkrementiert → Panel
  lädt neu
- 1–2 Integrations-Tests in `lv-detail.test.tsx`:
  - Tab-Switch rendert Panel; Count-Badge aus API
  - Klick auf Details im Panel öffnet den Drawer
- Commit: „feat(frontend): B+4.3.1c integrate gaps tab into LV
  detail page"

### Phase 5 — Abschluss + Push (10 min)

- `docs/b431c_complete.md` mit Test-Bilanz, UI-Layout-Screenshot-
  Hinweis, Follow-ups
- Commit: „docs: B+4.3.1c complete — catalog gaps tab live"
- Push

---

## 8. Aufwandsschätzung

| Phase | Zeit |
|---|---|
| 1 Baseline | 15 min |
| 2 gapsApi + Tests | 15 min |
| 3 Panel + 4–5 Tests | 40 min |
| 4 Tab-Switch + 1–2 Tests | 20 min |
| 5 Report + Push | 10 min |
| **Gesamt** | **~1h 40min** |

Im vom Nutzer vorgegebenen 1–1,5-h-Korridor mit leichter Pufferung
(~10 min Puffer). Wenn der Panel-Bau signifikant länger dauert (z. B.
Toggle-Animation will nicht), Scope = Toggle wird Native-Checkbox
ohne Animation.

Kosten: 0 $.

---

## 9. Offene Mini-Fragen

1. **Tab-Pattern-Bestätigung:** Variante A (zwei Header-Buttons mit
   `aria-pressed`, empfohlen), B (Unter-Route) oder C (Collapsible)?

2. **`include_low_confidence`-Default:** API-Default ist `false`.
   Empfehlung: Toggle initial **off**, passt zum API-Default.

3. **Severity-Sortierung in der Liste:** Backend liefert bereits
   `missing > low_confidence > estimated`. Übernehmen? Oder
   zusätzliche Sortierung nach `position_oz`?
   Empfehlung: **Backend-Sortierung 1:1 übernehmen** — der Report
   ist bereits nach Severity-Rank + OZ sortiert.

4. **Details-Button-Label:** „Details anzeigen" oder „Preis
   eintragen" oder nur Icon (z. B. ArrowRight)?
   Empfehlung: **„Details"** als Text, `ArrowRight` als Icon.
   Konsistent mit Pilot-Wording, nicht überladen.

5. **Refetch-Token-Mechanik:** Pro erfolgreichem Drawer-Submit
   den Counter im Parent inkrementieren und als Prop ins Panel
   geben. Panel beobachtet Token im `useEffect`-Dependency und
   refetched. Klappt das, oder lieber einen Imperativ-Callback
   `panelRef.current?.refetch()`?
   Empfehlung: **Token-Prop**, weil simpler und React-idiomatisch.

6. **Counter-Anzeige am Tab:** Nur `gaps_count`, oder auch
   Aufschlüsselung missing/estimated?
   Empfehlung: **Nur `gaps_count` am Tab-Label** („Katalog-Lücken
   126"), Aufschlüsselung erst im Panel-Header sichtbar. Hält die
   Tab-Leiste kompakt.
