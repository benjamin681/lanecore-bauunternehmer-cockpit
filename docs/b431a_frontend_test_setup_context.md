# B+4.3.1a — Frontend-Test-Setup: Kontext & Plan

**Stand:** 22.04.2026
**Zweck:** Planung vor Implementierung der drei Smoke-Tests. Kein Code,
kein Commit.
**Abhängigkeit:** vor B+4.3.1b (Near-Miss-Drawer, Katalog-Lücken-Tab).

---

## 1. Bestehende Frontend-Struktur

### 1.1 Framework + Tooling

| Aspekt | Stand |
|---|---|
| Framework | **Next.js 14.2.15** (App Router) |
| React | 18.3.1 |
| TypeScript | 5.6.3, strict mode aktiv (Tsconfig) |
| Styling | Tailwind 3.4.14 + custom `class-variance-authority` |
| Icons | `lucide-react` 0.454.0 |
| Toast | `sonner` 1.5.0 |
| Formulare | `clsx` + `tailwind-merge` für conditional classes |
| Package Manager | npm (`package-lock.json` präsent) |

### 1.2 Routen und Komponenten

```
src/app/
├── login, register
└── dashboard/
    ├── lvs/        (Liste) / neu (Upload) / [id] (Detail)
    ├── preislisten/ (Legacy-Liste) / neu / [id]
    ├── pricing/    (Neue Supplier-Listen) / upload / [id] / [id]/review
    ├── einstellungen/
    └── dev/components  (Komponenten-Showcase)

src/components/
├── Dropzone.tsx, ProgressBar.tsx
└── ui/  (button, card, input, label, badge, dialog,
       table, select, pagination, stage-badge)

src/lib/
├── api.ts          (267 LOC, core HTTP client + pollJob)
├── pricingApi.ts   (98 LOC, /pricing/* wrappers)
├── cn.ts, format.ts
└── types/
```

### 1.3 API-Layer

- **`api.ts`** kapselt `fetch` mit Token-Management aus `localStorage`
  (`lvp_token`-Key).
- Direkter Backend-Call (umgeht Vercel-Proxy wegen 4.5 MB Body-Limit):
  `http://<backend>:<port>/api/v1/...`.
- Alle API-Funktionen sind `"use client"` — werden also nur in Client
  Components verwendet.
- `pollJob(jobId)` für Background-Worker-Status (z. B. LV-Parse).
- `getPricingReadiness()` etc. für Feature-Flags und Pricing-Daten.

Das ist **wichtig für Tests:** die API-Schicht ist rein client-seitig
und kann über `fetch`-Mocks getestet werden. Keine Server Actions zu
mocken, keine MSW-Pflicht.

---

## 2. Bestehende Test-Infrastruktur

| Aspekt | Stand |
|---|---|
| Test-Framework installiert? | **nein** |
| `test`-Script in package.json? | **nein** |
| Bestehende Tests (`*.test.tsx`, `*.spec.tsx`) | **keine** |
| CI / GitHub Actions | **nicht konfiguriert** |
| Husky oder Pre-Commit | **keines** |
| Jest/Vitest-Config-Datei | **keine** |

**Klartext:** Das Frontend hat null Test-Setup. Wir starten auf der
grünen Wiese.

---

## 3. Empfehlung Test-Framework

### Bewertete Optionen

| Option | Pro | Contra |
|---|---|---|
| **Vitest + RTL + jsdom** | Native Vite-/ESM-Unterstützung, sehr schnell, Next.js 14 kompatibel, moderne Defaults, Watch-Mode ideal für TDD | Etwas neuer als Jest, kleinere Community |
| Jest + RTL + jsdom + Babel | Etablierter Standard, breites Tutorial-Ökosystem | Next.js 14 braucht `next/jest` Wrapper, mehr Config-Boilerplate, ESM-Schmerzen |
| Playwright | Echtes Browser-Testing, gut für E2E | Overkill für Smoke-Tests, viel langsamer, Backend muss laufen |

### **Empfehlung: Vitest + React Testing Library + jsdom**

Begründung:
- Minimale Konfiguration (eine `vitest.config.ts`, `npm test` läuft)
- Gut mit Next.js 14 App Router (wir testen nur Client Components)
- `vi.fn()` / `vi.mock()` reichen für `fetch`-Mocking ohne MSW
- Schneller Start, IDE-Integration (VSCode) out of the box

**Zusätzliche Dev-Dependencies** (geplant, nicht jetzt installieren):
- `vitest`
- `@testing-library/react`
- `@testing-library/user-event`
- `@testing-library/jest-dom` (für Custom-Matcher wie
  `toBeInTheDocument`)
- `jsdom`
- `@vitejs/plugin-react` (Vitest-kompatibler React-Transform)

Gesamter Install-Footprint: ~40 Pakete, ca. 30 MB. Vertretbar.

### API-Mocking-Strategie

**Für B+4.3.1a-Smoke:** `vi.mock("@/lib/api")` mit Stub-Funktionen.
Rationale:
- Die `api.ts`-Schicht ist klein und deterministisch.
- Komponenten rufen die Exports `api()`, `pollJob()`, `getPricingReadiness()`.
- MSW wäre präziser (geht auf `fetch` runter), aber für Smoke zu viel
  Infrastruktur.
- Wenn B+4.3.1b echten Request-Response-Round-Trip testen will
  (z. B. Error-Mapping im `api`-Client selbst), steigen wir dort auf
  MSW um.

### Test-Daten

**Inline pro Test.** Keine Fixtures-Dateien für Smoke. Drei Tests
brauchen jeweils einen Response, das schreibt sich schneller inline
als extern.

---

## 4. Drei konkrete Smoke-Tests — Entwürfe

### Smoke 1 — LV-Upload-Page rendert und reicht Datei an API weiter

**Datei:** `src/app/dashboard/lvs/neu/page.test.tsx`

**Was getestet wird:**
- Page rendert ohne Crash (Dropzone + Upload-Button sichtbar)
- Nach Dateiauswahl + Klick auf „Hochladen":
  - `api("/lvs/upload-async", { method: "POST", form, direct: true })`
    wird mit einem FormData aufgerufen, das die Datei enthält
  - `router.replace("/dashboard/lvs/<id>")` wird nach Erfolg getriggert

**Mocks:**
- `next/navigation` → `useRouter().replace` als `vi.fn()`
- `sonner` → `toast.success/error` als `vi.fn()`
- `@/lib/api` → `api` returned stub-Job, `pollJob` wird nicht
  aufgerufen im Upload-Pfad (würde erst auf Detail-Page laufen)

**Skizze:**
```tsx
it("uploads file and redirects to LV detail", async () => {
  const replace = vi.fn();
  (useRouter as Mock).mockReturnValue({ replace });
  (api as Mock).mockResolvedValue({
    id: "job-1", type: "parse_lv", target_id: "lv-1", status: "queued",
  });
  render(<NeuesLvPage />);
  const file = new File(["%PDF-1.4"], "lv.pdf", { type: "application/pdf" });
  // Simuliere Drop
  await user.upload(screen.getByTestId("dropzone-input"), file);
  await user.click(screen.getByRole("button", { name: /hochladen/i }));
  expect(api).toHaveBeenCalledWith(
    "/lvs/upload-async",
    expect.objectContaining({ method: "POST", direct: true }),
  );
  expect(replace).toHaveBeenCalledWith("/dashboard/lvs/lv-1");
});
```

**Aufwand:** ~20 min, kleines Risiko weil der Dropzone-Selektor ein
`data-testid` braucht (kleiner produktionsneutraler Eingriff).

### Smoke 2 — Preisliste-Upload-Page rendert und postet korrekt

**Datei:** `src/app/dashboard/pricing/upload/page.test.tsx`

**Was getestet wird:**
- Page rendert Felder (supplier_name, list_name, valid_from, Dropzone)
- Submit ruft `pricingApi.uploadPricelist(formData)` mit passenden
  Feld-Werten auf
- Bei Erfolg: `router.replace("/dashboard/pricing/<id>")`
- Bei 409 (Duplikat): Toast-Fehlermeldung sichtbar

**Mocks:**
- `next/navigation`, `sonner`, `@/lib/pricingApi`

**Skizze:**
```tsx
it("uploads price list with required fields", async () => {
  (pricingApi.uploadPricelist as Mock).mockResolvedValue({
    id: "pl-1", supplier_name: "Kemmler", status: "PENDING_PARSE",
  });
  render(<PricingUploadPage />);
  await user.type(screen.getByLabelText(/lieferant/i), "Kemmler");
  await user.type(screen.getByLabelText(/listen-name/i), "Ausbau 2026-04");
  await user.type(screen.getByLabelText(/gültig ab/i), "2026-04-01");
  await user.upload(
    screen.getByTestId("dropzone-input"),
    new File(["%PDF"], "kemmler.pdf", { type: "application/pdf" }),
  );
  await user.click(screen.getByRole("button", { name: /hochladen/i }));
  expect(pricingApi.uploadPricelist).toHaveBeenCalled();
});
```

**Aufwand:** ~30 min, weil die Seite 322 LOC hat und die Felder
nach aria-labelledby zu finden sind.

### Smoke 3 — LV-Detail-Page zeigt Positions-Tabelle nach Kalkulation

**Datei:** `src/app/dashboard/lvs/[id]/page.test.tsx`

**Was getestet wird:**
- Page rendert mit geladenem LV
- Kalkulations-Button vorhanden; Klick ruft
  `api("/lvs/{id}/kalkulation", { method: "POST" })`
- Nach Response: Positions-Tabelle zeigt OZ, Kurztext, EP, GP für
  erste Zeile
- StageBadge (aus `ui/stage-badge.tsx`) wird gerendert, wenn
  `price_source_summary` gesetzt ist

**Mocks:**
- `@/lib/api` → erst ein "loaded" LV mit 3 Positions, dann ein
  "calculated" LV nach POST
- `next/navigation` → `useParams` mit `{ id: "lv-1" }`

**Skizze:**
```tsx
it("renders positions after kalkulation", async () => {
  (api as Mock)
    .mockResolvedValueOnce(LV_LOADED_FIXTURE)    // initial GET
    .mockResolvedValueOnce(LV_CALCULATED_FIXTURE); // POST kalkulation
  render(<LvDetailPage />);
  await waitFor(() => expect(screen.getByText(/1\.1/)).toBeInTheDocument());
  await user.click(screen.getByRole("button", { name: /kalkulation/i }));
  await waitFor(() =>
    expect(screen.getByText(/1× supplier_price/)).toBeInTheDocument(),
  );
});
```

**Aufwand:** ~40 min, weil die Detail-Page 400 LOC hat und mehrere
Datenpfade (polling, retry) enthält. Für Smoke reichen die primären
zwei Pfade.

---

## 5. Implementierungs-Plan für B+4.3.1a

| Schritt | Beschreibung | Zeit |
|---|---|---|
| 1 | Dev-Dependencies installieren: `vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom` | 10 min |
| 2 | `vitest.config.ts` (jsdom-Environment, globals, setupFiles) + `test/setup.ts` (jest-dom erweitern) | 10 min |
| 3 | Kleines `data-testid`-Refactor im `Dropzone`, falls nötig, um Tests stabil zu machen | 10 min |
| 4 | Smoke 1 — LV-Upload | 20 min |
| 5 | Smoke 2 — Preisliste-Upload | 30 min |
| 6 | Smoke 3 — LV-Detail + Kalkulation | 40 min |
| 7 | `package.json` um `"test": "vitest run"` und `"test:watch": "vitest"` ergänzen | 5 min |
| 8 | Kurzer `npm test`-Lauf; dokumentieren; Commit | 10 min |
| **Gesamt** | | **~2h15** |

Optional, nicht Teil von 4.3.1a:
- `.github/workflows/frontend-tests.yml` (CI) — kann später nachgezogen werden, wenn GitHub Actions eingeführt wird
- Coverage-Schwelle — heute nicht, wir bauen erstmal den Boden

---

## 6. Offene Mini-Fragen vor Implementierung

1. **`data-testid`-Policy:** darf der `Dropzone` ein `data-testid`
   bekommen, oder nutzen wir ausschließlich `aria-label` / Label-
   Text? Empfehlung: testid bei nicht-trivial auffindbaren Elementen,
   sonst Role/Label. Kleiner Produktionsneutrale Eingriff.

2. **Backend-Interaktion:** die Smoke-Tests laufen komplett ohne
   laufendes Backend. Wenn du einen echten Backend-Lauf willst
   (Integrationstest), wäre das ein separater B+4.3.1-Schritt mit
   Playwright. **Vorschlag:** diesen echten E2E-Test erstmal hinten
   anstellen.

3. **Node-Version:** Vitest läuft auf Node 18+. Lokal ist Node 22
   vorhanden (aus `@types/node 22.7.9` zu schließen). Keine Aktion
   nötig.

4. **Framework-Review:** wenn du Jest statt Vitest bevorzugst
   (aus Team-Gründen oder existierender Anthropic-Standardisierung),
   lass es mich wissen vor Implementierung — Umstellung kostet kein
   Overhead, aber Config und Mocks unterscheiden sich stark.

---

## 7. Aufwandsschätzung + Risiken

- **Gesamt:** ~2h15 bei sauberem Durchlauf.
- **Risiko niedrig:** keine Backend-Änderung, keine UI-Design-Änderung.
- **Risiko mittel:** kleine `data-testid`-Ergänzungen im
  `Dropzone`/Formular-Code nötig; das sind produktionsrelevante
  Änderungen, die im Merge sichtbar werden.

Kosten: 0 $ (keine LLM-Calls, nur lokale Installation + Test-Ausführung).
