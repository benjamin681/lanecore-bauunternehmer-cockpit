# B+4.3.1b — Near-Miss-Drawer: Baseline

**Stand:** 22.04.2026
**Kontext-Doc:** `docs/b431b_near_miss_drawer_context.md`
**Abhängigkeiten:** B+4.3.0b (Candidates-Endpoint live), B+4.3.1a
(Vitest-Infrastruktur).

---

## 1. Scope

Near-Miss-Drawer für die LV-Detail-Tabelle.

- **Trigger:** Klick auf die `StageBadge` einer Position (Hover-State,
  Cursor-Pointer).
- **Inhalt:** Top-3 Kandidaten pro Material der Position + Action-
  Buttons für Kandidaten-Auswahl und manuelle Preis-Eingabe.
- **Datenquelle:** `GET /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates`
  (seit B+4.3.0b produktiv).
- **Persistence:** `PATCH /api/v1/lvs/{lv_id}/positions/{pos_id}`
  mit `{ ep: number }` — vorhandener Endpoint ohne Backend-Änderung.

---

## 2. Design-Entscheidungen

### a) Drawer-Position: **Side-Right (max-w-md, 448 px)**

**Begründung:** Tabellen-Layout bleibt erhalten, skaliert auf
komplexe Positionen mit 6+ Materialien ohne Zeilen-Sprengung. Der
Drawer überlagert die rechten Tabellen-Spalten partiell, scrollt
intern.

**Gegen Variante A (Inline-Expand):** Bei W628A-artigen Positionen
mit 6 Materialien würde die Tabelle vertikal explodieren.

**Gegen Variante C (Dialog-Modal):** Unterbricht den „Tabellen-
Vergleich"-Workflow; der Nutzer will parallel die Original-Zeile
und die Kandidaten sehen.

### b) Material-Navigation: **Accordion, erstes Material offen**

**Begründung:** Bei 1 Material ist der Accordion optisch kaum
spürbar. Bei 6+ Materialien bleibt die Struktur kompakt und
scrollbar. Das erste Material auf offen zu setzen gibt dem Nutzer
sofort etwas zum Lesen ohne zusätzlichen Klick.

### c) Preis-Eingabe-Scope: **nur `ep`-Wert**

**Begründung:** Der bestehende `PATCH /lvs/{id}/positions/{pos_id}`
nimmt `ep` direkt entgegen. Kein Frontend-Nachrechnen auf Material-
Ebene nötig — einfach, transparent für den Nutzer.

**Konsequenz:** wenn der Nutzer einen Kandidaten übernimmt, berechnet
das Frontend `ep = candidate.price_net × required_amount + lohn_ep +
zuschlaege_ep` und PATCHt. Die Rechnung ist im Drawer sichtbar,
bevor gespeichert wird.

### d) Trigger-Geste: **Klick auf `StageBadge`, Hover + Cursor-Pointer**

**Begründung:** Weniger visuelles Rauschen als eine separate „Details"-
Icon-Spalte. Der Badge ist semantisch der Einstiegspunkt zum Thema
„Preisquelle" — der Klick darauf ist intuitiv („ich will wissen, was
dahinter steckt").

**Abgrenzung zu Inline-Edit:** Die Tabelle erlaubt heute Klick auf
`kurztext`, `menge`, `einheit`, `erkanntes_system`, `ep` für
Inline-Editing via `<Input>`. Der neue Drawer-Trigger liegt
ausschließlich auf `StageBadge` in der Spalte „Preisquelle" —
keine Kollision.

### e) Manual-Override-Scope: **Position-PATCH mit `ep`, kein Audit-Trail**

**Begründung:** 3–4-h-Rahmen. Ein dedizierter „Kandidat gewählt"-
Endpoint mit Audit-Trail wäre sauber, aber Scope-Erweiterung um
~45 min.

**Follow-up-Notizen aus User-Freigabe:**
- Touch-Device-Support für Drawer-Trigger → separater Block.
- Audit-Trail für Manual-Overrides → separater Block, wenn Pilot-
  Nutzung das verlangt.

---

## 3. Komponenten-Plan

### Neue Dateien

| Datei | LOC (grob) | Zweck |
|---|---|---|
| `src/components/ui/drawer.tsx` | ~120 | Side-Right-Sheet mit Portal, Focus-Trap, ESC-to-Close (analog `dialog.tsx`) |
| `src/components/ui/accordion.tsx` | ~80 | Minimal-Accordion, headless, CSS-basiert (`details/summary`-Pattern oder state-kontrolliert) |
| `src/components/NearMissDrawer.tsx` | ~250 | Business-Komponente: Candidates laden, rendern, PATCH bei Action |
| `src/lib/candidatesApi.ts` | ~40 | Types + `getPositionCandidates(lvId, posId, limit)` |

### Erweiterte Dateien

| Datei | Änderung |
|---|---|
| `src/components/ui/stage-badge.tsx` | Optional: `onClick`-Prop + `clickable`-Flag; Hover-State und Cursor-Pointer bei `clickable` |
| `src/app/dashboard/lvs/[id]/page.tsx` | `drawerPosId`-State, `StageBadge`-Click-Handler, `<NearMissDrawer>`-Mount am Page-Ende |
| `src/lib/api.ts` | ggf. Re-Export der Types, falls die Seite sie auch braucht |

### Unberührt bleiben

- `Dialog`, `Dropzone`, bestehende `StageBadge`-Logik (Label-Mapping,
  Varianten) — additive Änderung
- Bestehende Inline-Edit-Mechanik in `PosRow`
- Alle Backend-Dateien, Migrations
- Alle bestehenden Tests

---

## 4. API-Integration

### Candidates abrufen

```ts
// src/lib/candidatesApi.ts
export type CandidateOut = {
  pricelist_name: string;
  candidate_name: string;
  match_confidence: number;       // 0.0-1.0
  stage: string;                  // 'supplier_price' | 'estimated'
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
  return api(
    `/lvs/${lvId}/positions/${posId}/candidates?limit=${limit}`
  );
}
```

### Manual-Override persistieren

Existierender Endpoint: `PATCH /api/v1/lvs/{lv_id}/positions/{pos_id}`

```ts
await api(`/lvs/${lvId}/positions/${posId}`, {
  method: "PATCH",
  body: { ep: newEp },
});
```

Nach Erfolg: `onUpdated()`-Callback triggert Page-Reload via
bestehende `load()`-Funktion.

---

## 5. Wording (aus `docs/ui_wording_guide.md`)

### Stage-Labels (Drawer-intern, pro Kandidat)

| Backend-`stage` | Drawer-Label |
|---|---|
| `supplier_price` (Score ≥ 0,85) | „Preis gefunden" |
| `supplier_price` (Score < 0,85) | „Ähnlicher Artikel" |
| `estimated` | „Richtwert" |
| (keiner) | „Fehlt im Katalog" |

### Confidence-Übersetzung (keine Prozentzahlen)

| `match_confidence` | Anzeige |
|---|---|
| ≥ 0,85 | „fast sicher" |
| 0,50 – 0,85 | „unsicher" |
| < 0,50 | „sehr unsicher" |

### Button-/Link-Labels

- **Kandidat übernehmen:** „Diesen Preis übernehmen"
- **Manual-Override:** „Preis selbst eingeben"
- **Schließen:** „Details schließen" (Button); ESC ebenfalls
- **Match-Reason:** kleiner grauer Hinweis unter dem Label (z. B.
  „Produktcode exakt: CW100" oder „Ähnlichkeit: 0,73" — hier ist
  Prozent erlaubt, weil es ein Debug-Hinweis ist, nicht User-facing)

### Error-Messages

- Candidates-Fetch fehlgeschlagen: „Kandidaten konnten nicht geladen
  werden."
- PATCH fehlgeschlagen: „Preis konnte nicht gespeichert werden: {detail}"

### Migrations-Policy

**Nur neue Komponenten** bekommen Wording aus dem Guide. Bestehende
Strings (z. B. „Kalkulieren" in der Action-Bar) bleiben unverändert
— die vollständige Wording-Migration ist ein separater Block
(B+4.3.1d oder später).

---

## 6. Test-Strategie

### Phase 6 — Smoke-Tests in `src/__tests__/near-miss-drawer.test.tsx`

| Test | Prüft |
|---|---|
| Drawer ist initial zu | Kein Portal-Content sichtbar |
| Drawer öffnet bei Click auf `StageBadge` | Page-State `drawerPosId` gesetzt; Drawer-Content rendert |
| Candidates werden beim Öffnen geladen | `getPositionCandidates(lvId, posId, 3)` wurde aufgerufen |
| Kandidaten-Liste rendert | Mindestens ein Kandidat sichtbar, pricelist_name + candidate_name + price_net |
| „Diesen Preis übernehmen" PATCHt | `api(PATCH)` mit `{ ep: <berechneter Wert> }` |
| „Preis selbst eingeben" zeigt Input + speichert | PATCH mit `{ ep: <user-eingegeben> }` |
| Drawer schließt bei ESC | Portal-Content verschwindet |
| Drawer schließt bei „Details schließen"-Button | Gleiche Assertion |

### Mock-Strategie (analog B+4.3.1a)

- `vi.hoisted()` für shared Mocks
- `vi.mock("@/lib/api")` für `api`
- `vi.mock("@/lib/candidatesApi")` für `getPositionCandidates`
- `vi.mock("sonner")` für Toasts

---

## 7. Phasen-Plan und Aufwand

| Phase | Inhalt | Zeit |
|---|---|---|
| 1 | Baseline-Doc (dieser Doc-Commit) | 30 min |
| 2 | `drawer.tsx` + `accordion.tsx` Primitive | 60 min |
| 3 | `candidatesApi.ts` + Types | 20 min |
| 4 | `NearMissDrawer.tsx` mit Fetch + Render + Actions | 90 min |
| 5 | Integration in `lvs/[id]/page.tsx` + StageBadge-Click | 30 min |
| 6 | Smoke-Tests (`near-miss-drawer.test.tsx`, 5–8 Tests) | 30 min |
| 7 | Abschluss-Doc + Full Build + Push | 15 min |
| **Gesamt** | | **~4 h 15 min** |

Pufferung nach oben möglich, wenn Mock-Probleme auftreten (B+4.3.1a
hatte z. B. vitest-Hoisting-Issue in Iteration 1).

Kosten: 0 $.

---

## 8. Verifikations-Kriterien (Abschluss)

Am Ende von Phase 7 müssen alle grün sein:

- **Frontend-Tests:** 7 (bestehend) + 5–8 (neu) = 12–15 grün
- **Backend-Tests:** 412 unberührt grün
- **Typecheck:** `npx tsc --noEmit` ohne Fehler
- **Next.js Build:** alle Routen kompilieren
- **Preview-Dev-Server:** keine Errors, Login-Redirect funktioniert
- **Commit-Stack:** 7 Commits auf `claude/beautiful-mendel`, Push sauber

---

## 9. Follow-ups (nicht in B+4.3.1b)

- Touch-Device-Support für Drawer-Trigger (Klick auf Badge auf
  mobile eventuell zu klein — ggf. mit Grip-Icon als alternativen
  Trigger auf schmalen Viewports).
- Audit-Trail für Manual-Overrides (neuer Backend-Endpoint +
  DB-Spalte, wenn Pilot-Nutzung das verlangt).
- Wording-Migration für bestehende Strings (B+4.3.1d).
- Vereinheitlichung StageBadge-Label mit Wording-Guide-Begriffen
  („Preis gefunden" statt „Lieferantenpreis") — Backend liefert nur
  `supplier_price`, Frontend müsste Confidence einbeziehen.
