/**
 * B+4.3.1b Smoke-Test: Drawer-Primitive.
 *
 * Prueft Portal-Mount/Unmount und ESC-Handling. Die Slide-in-
 * Animation wird in jsdom nicht visuell geprueft — nur Existenz
 * vs. Absenz der Dialog-Rolle.
 */

import { describe, expect, test } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { Drawer } from "@/components/ui/drawer";

function Harness({ initialOpen = false }: { initialOpen?: boolean }) {
  const [open, setOpen] = useState(initialOpen);
  return (
    <div>
      <button onClick={() => setOpen(true)}>Open</button>
      <Drawer open={open} onClose={() => setOpen(false)} title="Details">
        <p>Drawer-Body</p>
      </Drawer>
    </div>
  );
}

describe("Drawer primitive", () => {
  test("renders nothing when closed", () => {
    render(<Harness initialOpen={false} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("Drawer-Body")).not.toBeInTheDocument();
  });

  test("renders content when open", () => {
    render(<Harness initialOpen={true} />);
    const dlg = screen.getByRole("dialog");
    expect(dlg).toBeInTheDocument();
    expect(dlg).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Drawer-Body")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /details/i }),
    ).toBeInTheDocument();
  });

  test("closes on ESC", () => {
    render(<Harness initialOpen={true} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
