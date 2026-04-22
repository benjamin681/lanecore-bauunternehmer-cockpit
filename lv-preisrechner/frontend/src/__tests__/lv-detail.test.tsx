/**
 * B+4.3.1a Smoke-Test: LV-Detail + Kalkulations-Flow.
 *
 * Die Page lädt das LV beim Mount, erlaubt Kalkulation via Button und
 * reloadet danach. Wir mocken api() mit Path-basiertem Routing, damit
 * GET/POST/GET-Sequenz deterministisch ist.
 *
 * Scope bewusst minimal:
 *  - Tabelle rendert mit mindestens einer Zeile
 *  - StageBadge erscheint in der Preisquelle-Spalte
 *  - Kalkulation-Button triggert POST /lvs/{id}/kalkulation
 *  - Error-Pfad zeigt toast.error, Page bleibt renderbar
 *
 * Loading-State-Test: weggelassen. Die Page hat kein separates
 * "Kalkulation läuft"-UI (der Button wird disabled via `busy`-State).
 * Das reicht nicht fuer einen stabilen Test und bringt keinen
 * zusaetzlichen Regression-Schutz.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-Mocks --------------------------------------------------------
const mocks = vi.hoisted(() => ({
  routerReplace: vi.fn(),
  routerPush: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  toastInfo: vi.fn(),
  apiMock: vi.fn(),
  fetchCandidates: vi.fn(),
  updatePositionEp: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "lv-1" }),
  useRouter: () => ({
    replace: mocks.routerReplace,
    push: mocks.routerPush,
    back: vi.fn(),
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
    info: mocks.toastInfo,
  },
}));

vi.mock("@/lib/api", () => ({
  api: mocks.apiMock,
  pollJob: vi.fn(),
  setToken: vi.fn(),
  clearToken: vi.fn(),
  hasToken: () => true,
  getPricingReadiness: vi.fn(),
}));

// B+4.3.1b Integration: NearMissDrawer im LV-Detail nutzt candidatesApi
vi.mock("@/lib/candidatesApi", () => ({
  fetchCandidates: mocks.fetchCandidates,
  updatePositionEp: mocks.updatePositionEp,
}));

// eslint-disable-next-line import/first
import LvDetailPage from "@/app/dashboard/lvs/[id]/page";

// --- Fixtures ------------------------------------------------------------
type Pos = {
  id: string;
  reihenfolge: number;
  oz: string;
  titel: string;
  kurztext: string;
  menge: number;
  einheit: string;
  erkanntes_system: string;
  feuerwiderstand: string;
  plattentyp: string;
  materialien: unknown[];
  material_ep: number;
  lohn_stunden: number;
  lohn_ep: number;
  zuschlaege_ep: number;
  ep: number;
  gp: number;
  konfidenz: number;
  manuell_korrigiert: boolean;
  warnung: string;
  needs_price_review: boolean;
  price_source_summary: string;
};

function makePos(overrides: Partial<Pos> & { id: string; oz: string }): Pos {
  return {
    reihenfolge: 0,
    titel: "",
    kurztext: "Position",
    menge: 1,
    einheit: "m²",
    erkanntes_system: "W112",
    feuerwiderstand: "F0",
    plattentyp: "GKB",
    materialien: [],
    material_ep: 0,
    lohn_stunden: 0,
    lohn_ep: 0,
    zuschlaege_ep: 0,
    ep: 0,
    gp: 0,
    konfidenz: 1,
    manuell_korrigiert: false,
    warnung: "",
    needs_price_review: false,
    price_source_summary: "",
    ...overrides,
  };
}

function makeLv(status: string, extra: Partial<Record<string, unknown>> = {}) {
  return {
    id: "lv-1",
    projekt_name: "E2E-Test",
    auftraggeber: "Pilot-Kunde",
    original_dateiname: "lv.pdf",
    status,
    positionen_gesamt: 2,
    positionen_gematcht: 2,
    positionen_unsicher: 0,
    angebotssumme_netto: 1234.56,
    created_at: "2026-04-22T10:00:00Z",
    updated_at: "2026-04-22T10:00:00Z",
    positions: [
      makePos({
        id: "pos-1",
        oz: "1.1",
        kurztext: "GK-Wand W112",
        menge: 42.0,
        material_ep: 18.5,
        lohn_ep: 24.0,
        zuschlaege_ep: 4.0,
        ep: 46.5,
        gp: 1953.0,
        price_source_summary: "3\u00d7 supplier_price",
      }),
      makePos({
        id: "pos-2",
        oz: "1.2",
        kurztext: "Dämmung 40mm",
        menge: 42.0,
        material_ep: 2.84,
        lohn_ep: 3.2,
        zuschlaege_ep: 0.5,
        ep: 6.54,
        gp: 274.68,
        price_source_summary: "1\u00d7 estimated",
        needs_price_review: true,
        konfidenz: 0.5,
      }),
    ],
    ...extra,
  };
}

// --- Tests ---------------------------------------------------------------
describe("LV-Detail + Kalkulation Flow", () => {
  beforeEach(() => {
    mocks.routerReplace.mockReset();
    mocks.routerPush.mockReset();
    mocks.toastSuccess.mockReset();
    mocks.toastError.mockReset();
    mocks.toastInfo.mockReset();
    mocks.apiMock.mockReset();
    mocks.fetchCandidates.mockReset();
    mocks.updatePositionEp.mockReset();
  });

  test("happy path: loads LV, runs kalkulation, renders positions with StageBadge", async () => {
    // Path-basiertes Routing: erster GET liefert review_needed, POST
    // /kalkulation antwortet beliebig, zweiter GET liefert calculated.
    let getCount = 0;
    mocks.apiMock.mockImplementation(
      async (path: string, opts?: { method?: string }) => {
        const method = opts?.method ?? "GET";
        if (path === "/lvs/lv-1" && method === "GET") {
          getCount += 1;
          return getCount === 1 ? makeLv("review_needed") : makeLv("calculated");
        }
        if (path === "/lvs/lv-1/kalkulation" && method === "POST") {
          return { ok: true };
        }
        throw new Error(`Unexpected api call: ${method} ${path}`);
      },
    );

    const user = userEvent.setup();
    render(<LvDetailPage />);

    // Warte auf initialen Load — Headline erscheint, Spinner geht weg.
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /e2e-test/i }),
      ).toBeInTheDocument(),
    );

    // Tabelle ist da und enthaelt beide Positionen (OZ-Spalte).
    const table = screen.getByRole("table");
    expect(within(table).getByText("1.1")).toBeInTheDocument();
    expect(within(table).getByText("1.2")).toBeInTheDocument();
    // StageBadge-Labels aus price_source_summary
    expect(within(table).getByText(/lieferantenpreis/i)).toBeInTheDocument();
    expect(within(table).getByText(/sch\u00e4tzwert/i)).toBeInTheDocument();

    // Kalkulation triggern
    const calcBtn = screen.getByRole("button", { name: /kalkulieren/i });
    expect(calcBtn).not.toBeDisabled();
    await user.click(calcBtn);

    // POST wurde gesendet
    await waitFor(() =>
      expect(
        mocks.apiMock.mock.calls.some(
          ([p, o]) => p === "/lvs/lv-1/kalkulation" && o?.method === "POST",
        ),
      ).toBe(true),
    );
    // Erfolgs-Toast + Reload (status switcht auf "calculated" ->
    // Button-Label wird "Kalkulation wiederholen")
    await waitFor(() => expect(mocks.toastSuccess).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /kalkulation wiederholen/i }),
      ).toBeInTheDocument(),
    );
    expect(mocks.toastError).not.toHaveBeenCalled();
  });

  test("error path: kalkulation error shows toast and page stays rendered", async () => {
    mocks.apiMock.mockImplementation(
      async (path: string, opts?: { method?: string }) => {
        const method = opts?.method ?? "GET";
        if (path === "/lvs/lv-1" && method === "GET") {
          return makeLv("review_needed");
        }
        if (path === "/lvs/lv-1/kalkulation" && method === "POST") {
          throw { detail: "Preisdaten fehlen", status: 400 };
        }
        throw new Error(`Unexpected: ${method} ${path}`);
      },
    );

    const user = userEvent.setup();
    render(<LvDetailPage />);

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /e2e-test/i }),
      ).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /kalkulieren/i }));

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
    const msg = mocks.toastError.mock.calls[0][0] as string;
    expect(msg.toLowerCase()).toContain("preisdaten fehlen");
    // Page ist weiterhin renderbar (kein Crash)
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(mocks.routerReplace).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------
  // B+4.3.1b Integration: Near-Miss-Drawer
  // ---------------------------------------------------------------------
  test("clicking a position's StageBadge opens the NearMissDrawer", async () => {
    mocks.apiMock.mockResolvedValue(makeLv("calculated"));
    mocks.fetchCandidates.mockResolvedValueOnce({
      position_id: "pos-1",
      position_name: "W112",
      materials: [
        {
          material_name: "Gipskarton",
          required_amount: 2.1,
          unit: "m\u00b2",
          candidates: [
            {
              pricelist_name: "Kemmler",
              candidate_name: "Knauf GKB",
              match_confidence: 0.95,
              stage: "supplier_price",
              price_net: 3.3,
              unit: "m\u00b2",
              match_reason: "Produktcode exakt",
            },
          ],
        },
      ],
    });

    const user = userEvent.setup();
    render(<LvDetailPage />);
    await screen.findByRole("heading", { name: /e2e-test/i });

    // Finde den StageBadge-Trigger fuer die erste Position (oz=1.1)
    const trigger = screen.getByRole("button", {
      name: /preis-details fuer position 1\.1/i,
    });
    await user.click(trigger);

    // Drawer mountet (role=dialog aus Drawer-Primitive), Fetch startet
    await waitFor(() =>
      expect(mocks.fetchCandidates).toHaveBeenCalledWith("lv-1", "pos-1", 3),
    );
    const dlg = await screen.findByRole("dialog");
    expect(dlg).toBeInTheDocument();
    // Kandidaten-Liste rendert
    await screen.findByText(/Knauf GKB/i);
  });

  test("drawer onUpdated triggers LV reload via PATCH + refetch", async () => {
    // Erster GET, dann beliebig viele weitere GETs fuer Reload
    mocks.apiMock.mockImplementation(async () => makeLv("calculated"));
    mocks.fetchCandidates.mockResolvedValueOnce({
      position_id: "pos-1",
      position_name: "W112",
      materials: [],
    });
    mocks.updatePositionEp.mockResolvedValueOnce(undefined);

    const user = userEvent.setup();
    render(<LvDetailPage />);
    await screen.findByRole("heading", { name: /e2e-test/i });

    // Initialer GET wurde schon gemacht
    const initialGets = mocks.apiMock.mock.calls.filter(
      ([, o]) => (o?.method ?? "GET") === "GET",
    ).length;

    // Drawer öffnen
    await user.click(
      screen.getByRole("button", {
        name: /preis-details fuer position 1\.1/i,
      }),
    );
    await screen.findByRole("dialog");

    // EP eingeben + submitten
    const input = await screen.findByTestId("nm-ep-input");
    await user.clear(input);
    await user.type(input, "50");
    await user.click(
      screen.getByRole("button", { name: /preis selbst eintragen/i }),
    );

    // updatePositionEp lief, danach triggert onUpdated den LV-Reload
    await waitFor(() =>
      expect(mocks.updatePositionEp).toHaveBeenCalledWith("lv-1", "pos-1", 50),
    );
    await waitFor(() => {
      const getsAfter = mocks.apiMock.mock.calls.filter(
        ([, o]) => (o?.method ?? "GET") === "GET",
      ).length;
      expect(getsAfter).toBeGreaterThan(initialGets);
    });
  });
});
