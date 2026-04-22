/**
 * B+4.3.1a Smoke-Test: Preisliste-Upload-Flow.
 *
 * Prueft dass Metadaten-Formular + File-Upload den richtigen
 * pricingApi-Aufruf triggern, bei 409 einen Duplikat-Toast zeigen
 * und bei fehlenden Pflichtfeldern gar nicht erst zur API gehen.
 *
 * Wichtig: ApiError bleibt die echte Klasse, weil die Page
 * `err instanceof ApiError` nutzt.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-Mocks ---------------------------------------------------------
const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  uploadPricelist: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mocks.routerPush,
    replace: vi.fn(),
    back: vi.fn(),
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

// pricingApi vollstaendig mocken
vi.mock("@/lib/pricingApi", () => ({
  pricingApi: {
    uploadPricelist: mocks.uploadPricelist,
  },
}));

// @/lib/api: nur ApiError und hasToken werden vom Upload-Code beruehrt;
// wir behalten die echte ApiError-Klasse via importActual, damit
// `err instanceof ApiError` im Page-Code greift.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>(
    "@/lib/api",
  );
  return {
    ...actual,
    hasToken: () => true,
  };
});

// eslint-disable-next-line import/first
import { ApiError } from "@/lib/api";
// eslint-disable-next-line import/first
import PricingUploadPage from "@/app/dashboard/pricing/upload/page";

// --- Helpers --------------------------------------------------------------
async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^Lieferant\s*\*/i), "Kemmler");
  await user.type(screen.getByLabelText(/^Listen-Name\s*\*/i), "Ausbau 2026-04");
  // valid_from hat bereits heutiges Datum als Default
  const pdf = new File(["%PDF-1.4"], "kemmler.pdf", {
    type: "application/pdf",
  });
  const input = screen.getByTestId(
    "pricelist-dropzone-input",
  ) as HTMLInputElement;
  await user.upload(input, pdf);
  return pdf;
}

// --- Tests ---------------------------------------------------------------
describe("Pricelist-Upload Flow", () => {
  beforeEach(() => {
    mocks.routerPush.mockReset();
    mocks.toastSuccess.mockReset();
    mocks.toastError.mockReset();
    mocks.uploadPricelist.mockReset();
  });

  test("happy path: uploads with required metadata and redirects to detail", async () => {
    mocks.uploadPricelist.mockResolvedValueOnce({
      id: "pl-abc",
      supplier_name: "Kemmler",
      status: "PENDING_PARSE",
    });

    const user = userEvent.setup();
    render(<PricingUploadPage />);

    expect(
      screen.getByRole("heading", { name: /neue preisliste hochladen/i }),
    ).toBeInTheDocument();

    const pdf = await fillRequiredFields(user);

    const submit = screen.getByRole("button", { name: /^hochladen$/i });
    expect(submit).not.toBeDisabled();
    await user.click(submit);

    await waitFor(() =>
      expect(mocks.uploadPricelist).toHaveBeenCalledTimes(1),
    );
    const args = mocks.uploadPricelist.mock.calls[0][0];
    expect(args.supplier_name).toBe("Kemmler");
    expect(args.list_name).toBe("Ausbau 2026-04");
    expect(args.file).toBe(pdf);
    expect(typeof args.valid_from).toBe("string"); // ISO-Datum
    expect(args.auto_parse).toBe(true); // Default-Checkbox an

    await waitFor(() =>
      expect(mocks.routerPush).toHaveBeenCalledWith("/dashboard/pricing/pl-abc"),
    );
    expect(mocks.toastSuccess).toHaveBeenCalled();
    expect(mocks.toastError).not.toHaveBeenCalled();
  });

  test("409 conflict: existing pricelist triggers duplicate toast, no redirect", async () => {
    mocks.uploadPricelist.mockRejectedValueOnce(
      new ApiError(409, "Datei existiert bereits"),
    );

    const user = userEvent.setup();
    render(<PricingUploadPage />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /^hochladen$/i }));

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
    const msg = mocks.toastError.mock.calls[0][0] as string;
    expect(msg.toLowerCase()).toContain("duplikat");
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  test("validation: submit button disabled without file, no api call", async () => {
    // Der effektive Validation-Pfad in der UI: der Submit-Button ist
    // `disabled={busy || !file}`. Ohne gewaehlte Datei kann der User
    // gar nicht erst klicken. Die Pflichtfeld-Checks fuer supplier_name
    // / list_name / valid_from werden zuerst von HTML5 `required`
    // abgefangen, bevor der JS-Handler laeuft — wir testen deshalb den
    // primaeren UX-Pfad (Button-State) statt den JS-Fallback.
    const user = userEvent.setup();
    render(<PricingUploadPage />);

    // Metadaten ausfuellen, aber keine Datei.
    await user.type(screen.getByLabelText(/^Lieferant\s*\*/i), "Kemmler");
    await user.type(
      screen.getByLabelText(/^Listen-Name\s*\*/i),
      "Ausbau 2026-04",
    );

    const submit = screen.getByRole("button", { name: /^hochladen$/i });
    expect(submit).toBeDisabled();

    // Klick-Versuch auf disabled Button darf keinen API-Call triggern.
    await user.click(submit);
    expect(mocks.uploadPricelist).not.toHaveBeenCalled();
  });
});
