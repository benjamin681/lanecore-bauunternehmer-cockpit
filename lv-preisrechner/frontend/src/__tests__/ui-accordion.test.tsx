/**
 * B+4.3.1b Smoke-Test: Accordion-Primitive.
 */

import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

function Harness({ initial }: { initial?: string }) {
  return (
    <Accordion defaultValue={initial ?? null}>
      <AccordionItem value="a">
        <AccordionTrigger>Titel A</AccordionTrigger>
        <AccordionContent>Inhalt A</AccordionContent>
      </AccordionItem>
      <AccordionItem value="b">
        <AccordionTrigger>Titel B</AccordionTrigger>
        <AccordionContent>Inhalt B</AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

describe("Accordion primitive", () => {
  test("renders all triggers, no content visible without defaultValue", () => {
    render(<Harness />);
    expect(screen.getByRole("button", { name: /titel a/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /titel b/i })).toBeInTheDocument();
    expect(screen.queryByText("Inhalt A")).not.toBeInTheDocument();
    expect(screen.queryByText("Inhalt B")).not.toBeInTheDocument();
  });

  test("clicking a trigger opens its content and sets aria-expanded", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const a = screen.getByRole("button", { name: /titel a/i });
    expect(a).toHaveAttribute("aria-expanded", "false");
    await user.click(a);
    expect(a).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Inhalt A")).toBeInTheDocument();
  });

  test("single-mode: opening B closes A", async () => {
    const user = userEvent.setup();
    render(<Harness initial="a" />);
    expect(screen.getByText("Inhalt A")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /titel b/i }));
    expect(screen.getByText("Inhalt B")).toBeInTheDocument();
    expect(screen.queryByText("Inhalt A")).not.toBeInTheDocument();
  });
});
