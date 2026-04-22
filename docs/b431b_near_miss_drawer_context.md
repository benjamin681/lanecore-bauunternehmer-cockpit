# B+4.3.1b — Near-Miss-Drawer: Kontext & Plan

**Stand:** 22.04.2026
**Zweck:** Vor-Analyse + Design-Entscheidungen. Kein Code, kein Commit.
**Abhängigkeit:** B+4.3.0b (Candidates-Endpoint live), B+4.3.1a
(Vitest + React-Testing-Library).

---

## 1. Bestehende LV-Detail-Struktur

Datei: `src/app/dashboard/lvs/[id]/page.tsx` (400 LOC)

### Positions-Tabelle (`PosRow`)

Die Tabelle rendert pro Position eine Zeile mit 12 Spalten
(OZ, Beschreibung, System, Menge, Einheit, Material, Lohn, Zuschläge,
EP, GP, **Preisquelle**, Icons).

**Kein expliziter Zeilen-Click-Handler existiert heute.** Stattdessen:

- Jede Einzelzelle ist via `cell(field, display, raw)` inline
  editierbar (OZ, Beschreibung, Menge, Einheit, EP).
- Beim Klick auf eine Zelle wird `editingPos` / `edit`-State gesetzt,
  ein `<Input>` erscheint.
- Der neue Drawer darf **diese Inline-Edit-Mechanik nicht kaputt
  machen**. Er muss durch eine **separate** Trigger-Geste
  ausgelöst werden.

**Empfehlung:** neues Spalten-Icon (Lupe / „Details öffnen") in
der „Preisquelle"-Spalte oder am Zeilen-Ende. Alternativ: Klick auf
die `StageBadge` selbst öffnet den Drawer (Badge wird bereits
gerendert).

### State-Management

- Purer `useState`, kein Zustand/Redux.
- Drawer-State wird analog eingeführt:
  `const [drawerPosId, setDrawerPosId] = useState<string | null>(null)`.

### Toast / Modal

- `toast` aus `sonner` (global).
- `Dialog`-Komponente existiert als Eigenbau unter
  `src/components/ui/dialog.tsx` — Modal mit Portal, Focus-Trap,
  ESC-to-Close. Nicht shadcn.

---

## 2. shadcn / UI-Komponenten-Inventar

### Keine shadcn-Installation vorhanden

- `components.json` / `ui.json` existiert **nicht**.
- `src/components/ui/` enthält **Eigenbau-Komponenten** im shadcn-Stil:
  `badge, button, card, dialog, input, label, pagination, select,
  stage-badge, table`.
- Keine `@radix-ui/*`- oder `vaul`-Dependency installiert.

### Konsequenz für B+4.3.1b

Keine neue Lib-Installation. Der Drawer wird **als Eigenbau-
Komponente** umgesetzt im gleichen Stil wie `dialog.tsx` —
rechtsseitiges Sheet mit Backdrop, Portal, Focus-Trap, ESC-to-Close.

Vorlage: `dialog.tsx` minimal anpassen
- Position absolut rechts statt zentriert
- `translate-x` statt `scale`-Transition
- `max-w-md`/`max-w-lg` statt `sm:max-w-2xl`
- `h-full` statt `max-h`

### Neue UI-Komponenten im Drawer

| Komponente | Status |
|---|---|
| Accordion (für Material-Sektionen) | neu, Eigenbau |
| Near-Miss-Drawer | neu, Eigenbau |
| Radio-Group (für Kandidaten-Auswahl) | neu, Eigenbau oder native `<input type="radio">` |

---

## 3. API-Layer

### Bestehende Struktur

`src/lib/api.ts` exportiert:
- `api<T>(path, opts)` — core fetch-Wrapper
- `ApiError` — Error-Klasse mit `.status`, `.detail`
- Types: `User`, `Position`, `LV`, `LVDetail`, `Job`, ...
- Keine Candidates-Types oder Funktionen vorhanden.

### Hinzuzufügen

```ts
export type CandidateOut = {
  pricelist_name: string;
  candidate_name: string;
  match_confidence: number;
  stage: string;
  price_net: number;
  unit: string;
  match_reason: string;
};

export type MaterialWithCandidates = {
  material_name: string;
  required_amount: number;
  unit: string;
  candidates: CandidateOut[];
};

export type PositionCandidatesOut = {
  position_id: string;
  position_name: string;
  materials: MaterialWithCandidates[];
};

export async function getPositionCandidates(
  lvId: string, posId: string, limit = 3
): Promise<PositionCandidatesOut> {
  return api(`/lvs/${lvId}/positions/${posId}/candidates?limit=${limit}`);
}
```

Diese Additionen gehören zum Drawer-Block (nicht separat), weil sie
ausschließlich vom Drawer konsumiert werden.

---

## 4. Manual-Override — Backend-Verfügbarkeit

### Was existiert heute

| Endpoint | Scope | Geeignet für Drawer? |
|---|---|---|
| `PATCH /lvs/{id}/positions/{pos_id}` | setzt `ep`/`menge`/`einheit`/`kurztext`/`erkanntes_system` der Position | **Ja** — sofort nutzbar für „EP manuell überschreiben" |
| `POST /pricing/overrides` | Tenant-weite Override via `article_number` (wirkt auf alle LVs) | **Nein** — falsche Granularität für diesen UX |

### Was fehlt

**Ein Positions-scoped Kandidaten-Selector.** Also: „Merk dir dass
Position X den Kandidaten Y verwendet hat". Heute gibt es keine
saubere DB-Spalte, die den Kandidaten-Match referenziert — nur den
berechneten `ep`-Wert.

### Empfehlung

**B+4.3.1b bleibt im Scope:**

- „Diesen Kandidaten übernehmen"-Button → PATCH auf Position mit
  neuem `ep` (berechnet aus `candidate.price_net × required_amount
  + Lohn + Zuschläge`). Die Page macht die Rechnung frontend-seitig
  sichtbar, der Backend-PATCH persistiert nur den finalen `ep`.

- „Preis manuell setzen" → Inline-Input im Drawer für `ep`-Wert,
  gleicher PATCH.

**Ausgeschlossen für B+4.3.1b:**

- Neuer Endpoint zum Speichern des gewählten Kandidaten-IDs.
- Tenant-wide-Override aus dem Drawer.

Follow-up (später, wenn gewünscht): separater Block für „Manual-
Override-UI in Einstellungen" mit dem bestehenden
`POST /pricing/overrides`.

**Implikation:** nach „Übernehmen" verschwindet der Drawer, die
Tabelle reloadet, der Winner ist implizit sichtbar über den neuen
`ep`. Der Handwerker sieht das Ergebnis, aber die App kann nicht
zurückverfolgen „welcher Kandidat wurde gewählt". Das ist für den
Pilot ok.

---

## 5. Wording-Mapping aus `docs/ui_wording_guide.md`

### Stage-Labels (stimmen mit `StageBadge` überein, siehe Zeile 30 in `stage-badge.tsx`)

| Backend | Drawer-Label |
|---|---|
| `supplier_price` (exakt) | „Preis gefunden" |
| `supplier_price` (fuzzy) | „Ähnlicher Artikel" |
| `estimated` | „Richtwert" |
| `not_found` | „Fehlt im Katalog" |

**Abweichung zum bestehenden StageBadge:** der Guide unterscheidet
„Preis gefunden" (exakt) vs. „Ähnlicher Artikel" (fuzzy). Der
aktuelle `StageBadge` hat nur `supplier_price: "Lieferantenpreis"`.
Im Drawer reicht für Pilot die grobe Klassifikation aus dem
Candidates-Endpoint (`stage` als String). Eine Vereinheitlichung mit
StageBadge ist **ein Follow-up**, nicht Teil von B+4.3.1b.

### Confidence-Darstellung

Laut Guide **keine Prozent-Zahlen**. Mapping:
- `≥ 0.85` → „fast sicher"
- `0.5 – 0.85` → „unsicher"
- `< 0.5` → „sehr unsicher"

Im Drawer pro Kandidat angezeigt. Zusatz für Debug-Transparenz:
`match_reason` (bereits vom Backend geliefert, z. B.
„Produktcode exakt: CW100") wird als kleiner grauer Hinweistext
unter dem Label gezeigt.

### Button-Labels

Aus Guide ableitbar:
- „Diesen Preis übernehmen" (nicht „Kandidat wählen")
- „Preis selbst eingeben" (nicht „Manual override")
- „Details schließen" / ESC (nicht „Cancel")

---

## 6. Mockup-Analyse — `docs/ui_mockup_v1.html`

Referenz: „Pos 01.07 — aufgeklappt als Referenz für Near-Miss-Drawer".
Der Mockup zeigt:

- **Position-Overlay** in der Tabelle — aufgeklappte Zeile **statt**
  separatem Drawer.
- Innen: Liste mit 3–5 Kandidaten, die Top-1 ist farbig hervorgehoben
  („gewählter Preis"), Alternativen darunter mit Radio-Button-artigem
  Selektor.
- Rechts pro Kandidat: Lieferant, Name, Label, Preis.
- Footer der aufgeklappten Sektion: „Preis selbst eingeben" (Link)
  und „Alle Details schließen" (Button).

### Abweichung Mockup ↔ Empfehlung

Der Mockup setzt auf **Inline-Expand** pro Zeile, nicht auf Side-
Drawer. Das ist UX-technisch eleganter (kein Kontext-Switch), aber
bei vielen Materialien pro Position (W628A = 6 Materialien, manchmal
mehr) wird die Tabelle aufgerissen — Tabellen-Layout bricht.

**Vorschlag zur Diskussion:**

- **Variante A (Mockup-treu):** Inline-Expand über `<tr>` mit
  `colSpan=12`, innerhalb ein Accordion pro Material. Funktioniert
  für 1–3 Materialien gut, bei 6+ nervig.

- **Variante B (Side-Drawer, FU-3 aus B+4.3.0b):** `right: 0;
  width: 480px`, überlagert die Tabelle partiell, scrollt intern.
  Für komplexe Positionen komfortabler.

- **Variante C (Dialog-Modal):** maximale Komfort-Zone, aber
  unterbricht den „Tabellen-Vergleich"-Workflow.

**Meine Empfehlung: B (Side-Drawer rechts).** Begründung:

- Der bestehende Mockup ist ein Moodboard, keine finale Spec.
- B+4.3.0b-Follow-up FU-3 hat bereits „Accordion für viele Material-
  Sektionen" als Anforderung dokumentiert — das passt zum Side-
  Drawer besser als zur Inline-Expand.
- Side-Drawer lässt sich mit minimalem CSS aus der bestehenden
  `Dialog`-Komponente ableiten.

---

## 7. Design-Empfehlungen

| Frage | Empfehlung | Begründung |
|---|---|---|
| a) Drawer-Position | **Side-Right, max-w-md (448 px)** | Tabellen-Layout bleibt, skaliert auf komplexe Positionen |
| b) Material-Navigation | **Accordion**, erstes Material offen | bei 1 Material: flach; bei 6+ Materialien: kompakt |
| c) „Kandidat übernehmen" | **Direkt, ohne Confirm-Dialog**, Toast-Feedback | ein zusätzlicher Dialog bremst den Pilot-Workflow |
| c) „Preis manuell setzen" | **Inline-Input** im Accordion-Panel, Speichern-Button daneben | Inline ist schneller, bleibt beim Kontext |
| c) UI-Aktualisierung | **Abwarten auf Server-Response, dann Reload der LV-Daten** | wir haben schon `load()` in der Page — einheitlicher Pfad |
| d) Scope Manual-Override | **Position-PATCH mit neuem `ep`**, kein neuer Endpoint | passt in den 3–4-h-Rahmen und hält B+4.3.1b zielgerichtet |

---

## 8. Implementierungs-Plan

### Phase 1 — Baseline (30 min)

- `docs/b431b_baseline.md` mit den Design-Entscheidungen aus §7
- `components.json`-Entscheidung final (Eigenbau, nicht shadcn)
- Commit: „docs: B+4.3.1b baseline and design decisions"

### Phase 2 — Drawer-Komponente (60 min)

- `src/components/ui/drawer.tsx` (neu, ~120 LOC, portal-basiert,
  side-right, basiert auf `dialog.tsx`)
- `src/components/ui/accordion.tsx` (neu, ~80 LOC)
- Beide als passive UI-Komponenten — kein API-Call, keine Business-
  Logik.
- Optional: Smoke-Test für Drawer (Öffnen/Schließen via ESC).
- Commit: „feat(ui): B+4.3.1b drawer + accordion primitives"

### Phase 3 — Candidates-API-Client (20 min)

- `src/lib/api.ts` um Types + `getPositionCandidates()` erweitern
- Commit: „feat(api-client): B+4.3.1b candidates types and fetcher"

### Phase 4 — Near-Miss-Drawer-Komponente (90 min)

- `src/components/near-miss-drawer.tsx` (neu, ~250 LOC)
- Nimmt `lvId`, `position`, `open`, `onClose`, `onUpdated`
- Lädt `getPositionCandidates` on-open
- Rendert Accordion pro Material mit:
  - Kandidaten-Liste (`candidate_name`, Lieferant, Preis, Confidence,
    Match-Reason)
  - „Diesen Preis übernehmen"-Button
  - „Preis selbst eingeben"-Inline-Input
- Beide Actions: PATCH `/lvs/{id}/positions/{pos}` mit `ep` →
  `onUpdated()` → Page reloadet
- Commit: „feat(ui): B+4.3.1b near-miss drawer with candidate
  selection and manual override"

### Phase 5 — Integration in LV-Detail (30 min)

- `src/app/dashboard/lvs/[id]/page.tsx`:
  - `drawerPosId`-State
  - Neue Spalte oder Icon-Button in Positions-Zeile, der Drawer
    öffnet
  - Drawer-Komponente am Ende der Page einbetten
- Commit: „feat(ui): B+4.3.1b integrate near-miss drawer into LV
  detail page"

### Phase 6 — Tests (30 min)

- `src/__tests__/near-miss-drawer.test.tsx`:
  - Drawer öffnet/schließt bei State-Wechsel
  - Candidates-Fetch wird getriggert beim Öffnen
  - „Diesen Preis übernehmen" PATCHt die Position und triggert
    `onUpdated`
  - Manual-Override-Input PATCHt ebenfalls
- Commit: „test(frontend): B+4.3.1b smoke tests for near-miss
  drawer"

### Phase 7 — Abschluss (15 min)

- `docs/b431b_complete.md`
- Full build + typecheck + vitest
- Push auf `claude/beautiful-mendel`

---

## 9. Aufwandsschätzung

| Phase | Zeit |
|---|---|
| 1 Baseline | 30 min |
| 2 Drawer + Accordion | 60 min |
| 3 API-Client | 20 min |
| 4 Near-Miss-Drawer | 90 min |
| 5 Integration | 30 min |
| 6 Tests | 30 min |
| 7 Abschluss | 15 min |
| **Gesamt** | **~4h 15min** |

Im vom Nutzer angegebenen 3–4-h-Korridor, mit leichter Pufferung
nach oben bei unerwarteten Mock-Problemen.

Kosten: 0 $ (keine API-Calls).

## 10. Offene Mini-Fragen für dich

1. **Drawer-Variante:** A (Inline-Expand, Mockup-treu), B (Side-Drawer,
   meine Empfehlung), oder C (Dialog-Modal)? Entscheidung ändert die
   Drawer-Komponenten-Struktur.

2. **Accordion:** erstes Material offen, alle zu, oder alle offen?
   Empfehlung: **erstes offen** (schnell scannen, andere bei Bedarf).

3. **„Preis selbst eingeben":** nur für `ep` (Endpreis) oder auch für
   Material-Preis pro Einheit (dann müsste Frontend die Kalkulation
   nachrechnen)? Empfehlung: **nur `ep`**, weil das Backend bereits
   `PATCH` auf Position.ep unterstützt.

4. **Trigger-Geste:** neue Icon-Spalte „Details öffnen" (extra Klick-
   Ziel) oder Klick auf StageBadge selbst? Empfehlung: **Klick auf
   StageBadge**, weil das weniger visuelles Rauschen ist und die
   StageBadge sowieso der „Einstiegspunkt" zum Thema Preisquelle ist.

5. **Scope Manual-Override-Tracking:** wirklich Position-PATCH mit
   `ep` (einfach, aber kein Audit-Trail), oder möchtest du doch einen
   separaten Backend-Endpoint für „Kandidat Y wurde gewählt" im
   gleichen Block? Scope-Erweiterung um ~45 min.
