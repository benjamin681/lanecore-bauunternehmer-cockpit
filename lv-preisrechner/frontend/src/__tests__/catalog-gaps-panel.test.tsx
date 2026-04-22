/**
 * B+4.3.1c Smoke-Tests: CatalogGapsPanel.
 *
 * Deckt Loading / Loaded / Empty / Toggle-Refetch / Open-Callback ab.
 * ``@/lib/gapsApi`` ist gemockt.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { LVGapsReport } from "@/lib/gapsApi";

const mocks = vi.hoisted(() => ({
  fetchGaps: vi.fn(),
}));

vi.mock("@/lib/gapsApi", async () => {
  const actual = await vi.importActual<typeof import("@/lib/gapsApi")>(
    "@/lib/gapsApi",
  );
  return {
    ...actual,
    fetchGaps: mocks.fetchGaps,
  };
});

// eslint-disable-next-line import/first
import { CatalogGapsPanel } from "@/components/CatalogGapsPanel";

// -------------------------------------------------------------------
// Fixtures
// -------------------------------------------------------------------
function makeReport(overrides: Partial<LVGapsReport> = {}): LVGapsReport {
  return {
    lv_id: "lv-1",
    total_positions: 10,
    total_materials: 40,
    gaps_count: 3,
    missing_count: 2,
    estimated_count: 1,
    low_confidence_count: 0,
    gaps: [
      {
        position_id: "pos-1",
        position_oz: "1.1",
        position_name: "W112",
        material_name: "GKB 12,5 mm",
        material_dna: "Knauf|Gipskarton|GKB|12.5|",
        required_amount: 2.1,
        unit: "m\u00b2",
        severity: "missing",
        price_source: "not_found",
        match_confidence: null,
        source_description: "Kein Katalog-Eintrag",
        needs_review: true,
      },
      {
        position_id: "pos-2",
        position_oz: "1.2",
        position_name: "W112",
        material_name: "CW 75",
        material_dna: "Knauf|Profile|CW|75|",
        required_amount: 1.15,
        unit: "m",
        severity: "missing",
        price_source: "not_found",
        match_confidence: null,
        source_description: "Kein Katalog-Eintrag",
        needs_review: true,
      },
      {
        position_id: "pos-3",
        position_oz: "2.1",
        position_name: "W628A",
        material_name: "D\u00e4mmung 40mm",
        material_dna: "|D\u00e4mmung||40mm|",
        required_amount: 1.05,
        unit: "m\u00b2",
        severity: "estimated",
        price_source: "estimated",
        match_confidence: 0.5,
        source_description: "\u00d8 Kategorie D\u00e4mmung",
        needs_review: true,
      },
    ],
    ...overrides,
  };
}

// -------------------------------------------------------------------
// Tests
// -------------------------------------------------------------------
describe("CatalogGapsPanel", () => {
  beforeEach(() => {
    mocks.fetchGaps.mockReset();
  });

  test("shows loading skeleton while fetching", () => {
    mocks.fetchGaps.mockImplementationOnce(
      () => new Promise<LVGapsReport>(() => {}),
    );
    render(
      <CatalogGapsPanel lvId="lv-1" dataToken={0} onOpenPosition={() => {}} />,
    );
    expect(screen.getByTestId("gaps-loading")).toBeInTheDocument();
  });

  test("loaded state: list renders with severity badges and counts", async () => {
    mocks.fetchGaps.mockResolvedValueOnce(makeReport());
    render(
      <CatalogGapsPanel lvId="lv-1" dataToken={0} onOpenPosition={() => {}} />,
    );
    await waitFor(() => expect(screen.queryByTestId("gaps-loading")).toBeNull());

    // Header Counter
    expect(screen.getByText(/3 l\u00fccken/i)).toBeInTheDocument();
    expect(screen.getByText(/2 fehlen/i)).toBeInTheDocument();
    expect(screen.getByText(/1 richtwerte/i)).toBeInTheDocument();

    // Badges fuer Severity — "Richtwert" (exakt, ohne Plural "Richtwerte"
    // aus dem Counter) wird ueber exact-match isoliert.
    expect(screen.getAllByText(/Fehlt im Katalog/).length).toBe(2);
    expect(screen.getByText("Richtwert")).toBeInTheDocument();

    // Details-Buttons: einer pro Zeile
    expect(screen.getAllByTestId("gap-open-button").length).toBe(3);
  });

  test("empty state: green success panel when gaps_count is 0", async () => {
    mocks.fetchGaps.mockResolvedValueOnce(
      makeReport({ gaps_count: 0, missing_count: 0, estimated_count: 0, gaps: [] }),
    );
    render(
      <CatalogGapsPanel lvId="lv-1" dataToken={0} onOpenPosition={() => {}} />,
    );
    await screen.findByTestId("gaps-empty");
    expect(
      screen.getByText(/alle materialien haben einen preis/i),
    ).toBeInTheDocument();
    // Keine Liste
    expect(screen.queryByTestId("gap-row")).toBeNull();
  });

  test("toggling low-confidence triggers refetch with includeLowConfidence=true", async () => {
    mocks.fetchGaps
      .mockResolvedValueOnce(makeReport())
      .mockResolvedValueOnce(makeReport({ low_confidence_count: 1 }));
    const user = userEvent.setup();
    render(
      <CatalogGapsPanel lvId="lv-1" dataToken={0} onOpenPosition={() => {}} />,
    );

    await waitFor(() =>
      expect(mocks.fetchGaps).toHaveBeenLastCalledWith("lv-1", false),
    );

    await user.click(screen.getByTestId("toggle-low-confidence"));

    await waitFor(() =>
      expect(mocks.fetchGaps).toHaveBeenLastCalledWith("lv-1", true),
    );
    expect(mocks.fetchGaps).toHaveBeenCalledTimes(2);
  });

  test("clicking 'Kandidaten pruefen' calls onOpenPosition with the correct id", async () => {
    mocks.fetchGaps.mockResolvedValueOnce(makeReport());
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<CatalogGapsPanel lvId="lv-1" dataToken={0} onOpenPosition={onOpen} />);
    await screen.findAllByTestId("gap-open-button");

    // Click auf den zweiten Button => pos-2
    const buttons = screen.getAllByTestId("gap-open-button");
    await user.click(buttons[1]);

    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith("pos-2");
  });

  test("dataToken change triggers refetch", async () => {
    mocks.fetchGaps.mockResolvedValue(makeReport());
    const { rerender } = render(
      <CatalogGapsPanel lvId="lv-1" dataToken={0} onOpenPosition={() => {}} />,
    );
    await waitFor(() => expect(mocks.fetchGaps).toHaveBeenCalledTimes(1));

    rerender(
      <CatalogGapsPanel lvId="lv-1" dataToken={1} onOpenPosition={() => {}} />,
    );
    await waitFor(() => expect(mocks.fetchGaps).toHaveBeenCalledTimes(2));
  });
});
