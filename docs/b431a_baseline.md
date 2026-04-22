# B+4.3.1a — Frontend-Test-Setup: Baseline

**Stand:** 22.04.2026, vor Installation.
**Kontext-Doc:** `docs/b431a_frontend_test_setup_context.md`.
**Abhängigkeit:** B+4.3.0c abgeschlossen; Backend-APIs stabil.

---

## 1. Bestehende Frontend-Struktur

| Aspekt | Stand |
|---|---|
| Framework | Next.js 14.2.15 App Router |
| React | 18.3.1 |
| TypeScript | 5.6.3 strict |
| Tailwind | 3.4.14 |
| Package Manager | npm |
| CI / Husky | keines |
| Bestehende Tests | keine |

Kern-Komponenten für Smoke:

- `src/app/dashboard/lvs/neu/page.tsx` (91 LOC) — LV-Upload, nutzt
  `Dropzone`, `ProgressBar`, `Button`, `api<Job>(...)`, `useRouter`
- `src/app/dashboard/pricing/upload/page.tsx` (322 LOC) — Preisliste-
  Upload, nutzt `Dropzone`, Form-Felder, `pricingApi.uploadPricelist`
- `src/app/dashboard/lvs/[id]/page.tsx` (400 LOC) — LV-Detail,
  Kalkulation-Button, Positions-Tabelle mit `StageBadge`

API-Clients:

- `src/lib/api.ts` (267 LOC) — Core-`fetch`-Client mit Token-Management
- `src/lib/pricingApi.ts` (98 LOC) — Wrapper für `/pricing/*`

---

## 2. Entscheidung: Vitest

Gewählt **Vitest + React Testing Library + jsdom**.

Begründung:

- Minimale Konfiguration, eine `vitest.config.ts` reicht.
- Native ESM-Unterstützung (Next.js 14 liefert ESM-Mischung).
- `vi.mock("@/lib/api")` genügt zum Stubben, keine MSW-Pflicht.
- Schneller Watch-Mode, gute IDE-Integration.
- Kein Notwendigkeit für `next/jest`-Wrapper.

Abgelehnt:

- **Jest** — mehr Boilerplate bei Next.js-14/ESM-Kombination.
- **Playwright** — Overkill für Smoke; wäre ein Schritt für später,
  wenn echte Backend-Integrationstests gewünscht sind.

---

## 3. Komponenten, die `data-testid` bekommen

Minimal-Policy: nur wenn Role/Label-Queries den Test instabil machen.
Erwartet: **maximal 3 Test-IDs** im Produktions-Code.

| Datei | Element | testid (vorgeschlagen) | Begründung |
|---|---|---|---|
| `src/components/Dropzone.tsx` | `<input type="file">` | `dropzone-input` | `userEvent.upload` braucht stabilen File-Input-Selector; der aktuelle Selector wäre nur per Klassenname erreichbar |
| ggf. `src/app/dashboard/pricing/upload/page.tsx` | Submit-Button | `pricelist-upload-submit` | nur wenn Role+Label mehrdeutig ist (wird in Phase 3 entschieden) |
| ggf. `src/app/dashboard/lvs/[id]/page.tsx` | Kalkulation-Button | `lv-calc-button` | nur wenn Role+Label mehrdeutig ist (wird in Phase 4 entschieden) |

---

## 4. Test-Flow-Beschreibung

### Smoke 1 — LV-Upload

1. Render `NeuesLvPage` mit gemocktem `api` + `useRouter`.
2. Simuliere File-Drop via `userEvent.upload(dropzoneInput, file)`.
3. Click „Hochladen"-Button.
4. Assert: `api("/lvs/upload-async", { method: "POST", direct: true, form: FormData })`.
5. Assert: `router.replace("/dashboard/lvs/<id>")`.

### Smoke 2 — Preisliste-Upload

1. Render `PricingUploadPage` mit gemocktem `pricingApi` + `useRouter`.
2. Fülle Pflichtfelder (supplier_name, list_name, valid_from).
3. Simuliere File-Drop.
4. Click „Hochladen".
5. Assert: `pricingApi.uploadPricelist(formData)` aufgerufen.
6. Assert: Erfolgs-Toast oder Redirect.

Zweite Variante: `mockRejectedValue({ status: 409 })` → Fehler-Toast
sichtbar.

### Smoke 3 — LV-Detail + Kalkulation

1. Render `LvDetailPage` mit gemocktem `api` (initial GET → LV-Fixture).
2. Warte bis Page die Positionen rendert.
3. Click „Kalkulation starten"-Button.
4. Mock für POST `/kalkulation` → LV-Fixture mit EP/GP/`price_source_summary`.
5. Assert: Tabelle zeigt mindestens eine Positionszeile.
6. Assert: `StageBadge`-Komponente erscheint (oder ihr Label-Text, z. B.
   „supplier_price", „Richtwert", „Schätzung").

---

## 5. Commit-Strategie

| Commit | Inhalt |
|---|---|
| 1 | `chore(frontend): B+4.3.1a setup vitest + react testing library` |
| 2 | `test(frontend): B+4.3.1a smoke test for LV upload flow` |
| 3 | `test(frontend): B+4.3.1a smoke test for pricelist upload flow` |
| 4 | `test(frontend): B+4.3.1a smoke test for LV detail and calculation flow` |
| 5 | `docs: B+4.3.1a frontend test infrastructure live, 3 smoke tests green` |

Nach Commit 5: Push-Freigabe einholen.
