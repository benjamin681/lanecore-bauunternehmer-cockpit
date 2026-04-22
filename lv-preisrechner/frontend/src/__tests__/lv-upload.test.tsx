/**
 * B+4.3.1a Smoke-Test: LV-Upload-Flow.
 *
 * Bewusst minimal: wir pruefen dass die Page rendert, einen File-Drop
 * akzeptiert, beim Submit die API ruft und nach Erfolg in die Detail-
 * Route redirectet. Kein echter Backend-Call; alle externen Abhaengigkeiten
 * sind gemockt (api, next/navigation, sonner).
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// --- Module-Mocks ---------------------------------------------------------
// Wichtig: vi.mock wird vor Imports gehoistet, also muss shared State
// ueber vi.hoisted() laufen.

const mocks = vi.hoisted(() => ({
  routerReplace: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  apiMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mocks.routerReplace,
    push: vi.fn(),
    back: vi.fn(),
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
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

// Wichtig: Import der Page NACH den vi.mock-Aufrufen, damit die
// Mocks vor dem Modul-Load gebunden sind.
// eslint-disable-next-line import/first
import NeuesLvPage from "@/app/dashboard/lvs/neu/page";

// --- Tests ---------------------------------------------------------------

describe("LV-Upload Flow", () => {
  beforeEach(() => {
    mocks.routerReplace.mockReset();
    mocks.toastSuccess.mockReset();
    mocks.toastError.mockReset();
    mocks.apiMock.mockReset();
  });

  test("happy path: file upload triggers /lvs/upload-async and redirect", async () => {
    mocks.apiMock.mockResolvedValueOnce({
      id: "job-1",
      type: "parse_lv",
      target_id: "lv-xyz",
      status: "queued",
      progress: 0,
      message: null,
    });

    const user = userEvent.setup();
    render(<NeuesLvPage />);

    // Seite ist sichtbar
    expect(
      screen.getByRole("heading", { name: /neues lv hochladen/i }),
    ).toBeInTheDocument();

    // File-Drop simulieren ueber das Hidden-Input der Dropzone
    const pdf = new File(["%PDF-1.4 fake"], "angebot.pdf", {
      type: "application/pdf",
    });
    const input = screen.getByTestId("dropzone-input") as HTMLInputElement;
    await user.upload(input, pdf);

    // Submit-Button ist jetzt enabled — klicken
    const submit = screen.getByRole("button", {
      name: /hochladen & analysieren/i,
    });
    expect(submit).not.toBeDisabled();
    await user.click(submit);

    // API-Aufruf mit richtiger Route + Options
    await waitFor(() => expect(mocks.apiMock).toHaveBeenCalledTimes(1));
    const [path, opts] = mocks.apiMock.mock.calls[0];
    expect(path).toBe("/lvs/upload-async");
    expect(opts.method).toBe("POST");
    expect(opts.direct).toBe(true);
    expect(opts.form).toBeInstanceOf(FormData);
    expect((opts.form as FormData).get("file")).toBeInstanceOf(File);

    // Redirect nach Erfolg
    await waitFor(() =>
      expect(mocks.routerReplace).toHaveBeenCalledWith("/dashboard/lvs/lv-xyz"),
    );
    expect(mocks.toastSuccess).toHaveBeenCalled();
    expect(mocks.toastError).not.toHaveBeenCalled();
  });

  test("error path: API error shows error toast and no redirect", async () => {
    mocks.apiMock.mockRejectedValueOnce({
      detail: "Upload zu gross",
      status: 413,
    });
    // Console-Error-Rauschen aus der Seite unterdruecken (sie loggt
    // im catch-Zweig).
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const user = userEvent.setup();
    render(<NeuesLvPage />);

    const pdf = new File(["%PDF-1.4"], "boom.pdf", { type: "application/pdf" });
    const input = screen.getByTestId("dropzone-input") as HTMLInputElement;
    await user.upload(input, pdf);
    await user.click(
      screen.getByRole("button", { name: /hochladen & analysieren/i }),
    );

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
    const firstMsg = mocks.toastError.mock.calls[0][0] as string;
    expect(firstMsg.toLowerCase()).toContain("upload fehlgeschlagen");
    expect(mocks.routerReplace).not.toHaveBeenCalled();

    errSpy.mockRestore();
  });
});
