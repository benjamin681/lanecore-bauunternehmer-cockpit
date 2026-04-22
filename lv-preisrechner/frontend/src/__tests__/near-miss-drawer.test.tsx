/**
 * B+4.3.1b Smoke-Tests: NearMissDrawer.
 *
 * Deckt Loading / Error / Loaded, Row-Click-Vorschlag, EP-Submit und
 * ESC-Close ab. Die Candidates-API und updatePositionEp sind gemockt.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { PositionCandidates } from "@/lib/candidatesApi";

const mocks = vi.hoisted(() => ({
  fetchCandidates: vi.fn(),
  updatePositionEp: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/candidatesApi", () => ({
  fetchCandidates: mocks.fetchCandidates,
  updatePositionEp: mocks.updatePositionEp,
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

// eslint-disable-next-line import/first
import { NearMissDrawer } from "@/components/NearMissDrawer";

// -------------------------------------------------------------------
// Fixtures + Harness
// -------------------------------------------------------------------
function makeData(): PositionCandidates {
  return {
    position_id: "pos-1",
    position_name: "W112",
    materials: [
      {
        material_name: "Gipskarton 12.5 mm",
        required_amount: 2.1,
        unit: "m\u00b2",
        candidates: [
          {
            pricelist_name: "Kemmler",
            candidate_name: "Knauf GKB 12,5 mm",
            match_confidence: 0.92,
            stage: "supplier_price",
            price_net: 3.3,
            unit: "m\u00b2",
            match_reason: "Produktcode exakt",
          },
          {
            pricelist_name: "(Schaetzung)",
            candidate_name: "\u00d8 Kategorie Gipskarton",
            match_confidence: 0.5,
            stage: "estimated",
            price_net: 3.1,
            unit: "m\u00b2",
            match_reason: "\u00d8 aus Kategorie",
          },
        ],
      },
      {
        material_name: "CW-Profil 75",
        required_amount: 1.15,
        unit: "m",
        candidates: [
          {
            pricelist_name: "Kemmler",
            candidate_name: "CW-Profil 75x50x0,6 mm",
            match_confidence: 0.42,
            stage: "fuzzy",
            price_net: 8.05,
            unit: "m",
            match_reason: "Fuzzy-\u00c4hnlichkeit 42%",
          },
        ],
      },
    ],
  };
}

function Harness({ initialOpen = true }: { initialOpen?: boolean }) {
  const [open, setOpen] = useState(initialOpen);
  const [updated, setUpdated] = useState(0);
  return (
    <div>
      <span data-testid="updated-count">{updated}</span>
      <NearMissDrawer
        open={open}
        onClose={() => setOpen(false)}
        lvId="lv-1"
        posId="pos-1"
        currentEp={46.5}
        onUpdated={() => setUpdated((n) => n + 1)}
      />
    </div>
  );
}

// -------------------------------------------------------------------
// Tests
// -------------------------------------------------------------------
describe("NearMissDrawer", () => {
  beforeEach(() => {
    mocks.fetchCandidates.mockReset();
    mocks.updatePositionEp.mockReset();
    mocks.toastSuccess.mockReset();
    mocks.toastError.mockReset();
  });

  test("shows loading skeleton while fetching", () => {
    // Promise bewusst pending lassen — Vitest raeumt via afterEach(cleanup)
    // nach dem Test auf.
    mocks.fetchCandidates.mockImplementationOnce(
      () => new Promise<PositionCandidates>(() => {}),
    );
    render(<Harness />);
    expect(screen.getByTestId("nm-loading")).toBeInTheDocument();
  });

  test("renders materials accordion with first item open", async () => {
    mocks.fetchCandidates.mockResolvedValueOnce(makeData());
    render(<Harness />);
    await waitFor(() =>
      expect(screen.getByRole("dialog")).toBeInTheDocument(),
    );
    const triggers = await screen.findAllByRole("button", {
      name: /gipskarton|cw-profil/i,
    });
    expect(triggers.length).toBeGreaterThanOrEqual(2);
    // Erstes Material: aria-expanded=true
    const first = triggers.find((t) =>
      /gipskarton/i.test(t.textContent ?? ""),
    )!;
    expect(first).toHaveAttribute("aria-expanded", "true");
    // Inhalt des ersten Materials ist sichtbar
    expect(screen.getByText(/Knauf GKB 12,5 mm/i)).toBeInTheDocument();
    expect(screen.getByText(/Preis gefunden/i)).toBeInTheDocument();
    expect(screen.getByText(/fast sicher/i)).toBeInTheDocument();
  });

  test("clicking a candidate row pre-fills the EP input", async () => {
    mocks.fetchCandidates.mockResolvedValueOnce(makeData());
    const user = userEvent.setup();
    render(<Harness />);
    await screen.findByText(/Knauf GKB 12,5 mm/i);
    const rows = screen.getAllByTestId("candidate-row");
    // Erster Kandidat im ersten Material: Knauf GKB 12,5 mm (3,30) × 2,10
    await user.click(rows[0]);
    const input = screen.getByTestId("nm-ep-input") as HTMLInputElement;
    expect(input.value).toBe("6.93"); // 3.30 * 2.10
  });

  test("submit with valid ep triggers updatePositionEp and closes drawer", async () => {
    mocks.fetchCandidates.mockResolvedValueOnce(makeData());
    mocks.updatePositionEp.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    render(<Harness />);
    await screen.findByText(/Knauf GKB 12,5 mm/i);

    const input = screen.getByTestId("nm-ep-input") as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "42,50");

    await user.click(
      screen.getByRole("button", { name: /preis selbst eintragen/i }),
    );

    await waitFor(() =>
      expect(mocks.updatePositionEp).toHaveBeenCalledTimes(1),
    );
    const [lvId, posId, ep] = mocks.updatePositionEp.mock.calls[0];
    expect(lvId).toBe("lv-1");
    expect(posId).toBe("pos-1");
    expect(ep).toBeCloseTo(42.5, 2);

    expect(mocks.toastSuccess).toHaveBeenCalled();
    // onUpdated wurde aufgerufen -> Harness-Counter +1
    await waitFor(() =>
      expect(screen.getByTestId("updated-count").textContent).toBe("1"),
    );
    // Drawer ist geschlossen
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  test("submit with invalid ep shows error toast and no PATCH", async () => {
    mocks.fetchCandidates.mockResolvedValueOnce(makeData());
    const user = userEvent.setup();
    render(<Harness />);
    await screen.findByText(/Knauf GKB 12,5 mm/i);

    const input = screen.getByTestId("nm-ep-input") as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "abc");

    await user.click(
      screen.getByRole("button", { name: /preis selbst eintragen/i }),
    );

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
    const msg = mocks.toastError.mock.calls[0][0] as string;
    expect(msg.toLowerCase()).toContain("preis");
    expect(mocks.updatePositionEp).not.toHaveBeenCalled();
    // Dialog bleibt offen
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  test("error path renders retry, retry refetches", async () => {
    mocks.fetchCandidates
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(makeData());
    const user = userEvent.setup();
    render(<Harness />);
    const err = await screen.findByTestId("nm-error");
    expect(
      within(err).getByText(/kandidaten konnten nicht geladen werden/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /erneut versuchen/i }));

    await waitFor(() =>
      expect(mocks.fetchCandidates).toHaveBeenCalledTimes(2),
    );
    await screen.findByText(/Knauf GKB 12,5 mm/i);
  });

  test("ESC closes the drawer", async () => {
    mocks.fetchCandidates.mockResolvedValueOnce(makeData());
    render(<Harness />);
    await screen.findByText(/Knauf GKB 12,5 mm/i);
    // ESC feuern
    const evt = new KeyboardEvent("keydown", { key: "Escape" });
    document.dispatchEvent(evt);
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });
});
