# B+4.3.1a Abschluss — Frontend-Test-Infrastruktur

**Datum:** 22.04.2026
**Baseline:** `docs/b431a_baseline.md`
**Kontext:** `docs/b431a_frontend_test_setup_context.md`
**Branch:** `claude/beautiful-mendel`

---

## Status

- Vitest + React Testing Library live
- **7 Smoke-Tests grün** (Laufzeit ~2 s)
- **2 `data-testid`-Eingriffe** dokumentiert
- Null Regressionen an Backend oder Frontend
- Next.js-Build weiterhin grün (12 Routen, keine zusätzlichen Fehler)

## Test-Suite-Übersicht

| Datei | Tests | Abdeckung |
|---|---|---|
| `src/__tests__/lv-upload.test.tsx` | 2 | File-Upload Happy Path, API-Error-Pfad |
| `src/__tests__/pricelist-upload.test.tsx` | 3 | Upload mit Metadaten, 409-Duplikat, Disabled-Button ohne Datei |
| `src/__tests__/lv-detail.test.tsx` | 2 | Kalkulation Happy Path mit Status-Transition, Kalkulations-Error |
| **Gesamt Frontend** | **7** | |

## Produktions-Eingriffe

| Datei | Eingriff | Grund |
|---|---|---|
| `src/components/Dropzone.tsx` | `data-testid="dropzone-input"` auf hidden `<input type="file">` | Input hat `className="hidden"` und ist nicht per Label/Role erreichbar |
| `src/app/dashboard/pricing/upload/page.tsx` | `data-testid="pricelist-dropzone-input"` auf inline hidden File-Input | Pricing-Page nutzt nicht die `Dropzone`-Komponente, sondern einen eigenen Drop-Bereich |

Beide additive Eingriffe, keine Verhaltens-Änderungen. Full Next.js
Build bleibt auf vorigem Niveau (6,48 kB / 115 kB shared für
`/dashboard/pricing/upload`).

## Bekannte Gaps (bewusst)

1. **Kein E2E-Test mit laufendem Backend** — aus Scope ausgeschlossen.
   Wenn später gewünscht, wäre Playwright die natürliche Wahl.
2. **Kein CI-Setup** für automatische Test-Ausführung — separater
   Block, wenn GitHub Actions eingeführt wird.
3. **Tot-Code-Befund** in `pricing/upload/page.tsx`: der JS-Pflicht-
   Check für `supplier_name`/`list_name`/`valid_from` ist unerreichbar,
   weil HTML5 `required` vorher greift. Kein Test-Schaden, aber ein
   kleiner Cleanup-Kandidat für später.
4. **`--legacy-peer-deps`-Workaround** bei Install: `@types/node@25`
   (peer von `vitest@4`) kollidiert mit Next.js-14-Pin. Folgt mit
   Next.js-15-Upgrade auf.

## Infrastruktur-Bilanz

| Metrik | Wert |
|---|---|
| Commits B+4.3.1a | 4 |
| Frontend-Tests neu | 7 |
| Backend-Tests (unberührt) | 412 |
| **Gesamt-Tests** | **419** |
| Dependencies hinzugefügt | 6 (`vitest`, `@vitejs/plugin-react`, `@testing-library/{react,user-event,jest-dom,dom}`, `jsdom`) |

## Technische Highlights

- **Mock-Pattern:** `vi.hoisted()` für shared state zwischen Module-
  Mocks und Test-Assertions (Vitest hoistet `vi.mock`-Aufrufe über
  Imports).
- **Partial-Mock von `@/lib/api`:** via `vi.importActual` bleibt
  `ApiError` eine echte Klasse — wichtig weil `page.tsx`
  `err instanceof ApiError` nutzt.
- **Path-basiertes API-Routing** im LV-Detail-Test: `mockImplementation`
  entscheidet per `(path, method)` welche Response kommt — robuster
  als `mockResolvedValueOnce`-Kette bei 3 sequentiellen Requests.
- **Auto-Cleanup** via `afterEach(cleanup)` in `vitest.setup.ts`
  verhindert DOM-Leaks zwischen Tests.
- **Validation-Test umgebaut:** der JS-Pflicht-Check in pricing/upload
  ist unter HTML5 `required` nicht erreichbar, deshalb testen wir den
  effektiven UX-Pfad (Disabled-Button bei fehlendem File).

## Nächster Block: B+4.3.1b

**Near-Miss-Drawer-Komponente** (3–4 h):

- Konsumiert den bereits implementierten Endpoint
  `GET /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates`
- Ziel-Design aus `docs/ui_mockup_v1.html`
- Wording aus `docs/ui_wording_guide.md`
- Smoke-Test für Drawer-Öffnung/Schließung im gleichen Block — die
  Infrastruktur aus B+4.3.1a steht bereit

Der ebenfalls bereits gebaute Endpoint
`GET /api/v1/lvs/{lv_id}/gaps` ist Grundlage für B+4.3.1c
(Katalog-Lücken-Tab) — der kommt nach dem Drawer.
