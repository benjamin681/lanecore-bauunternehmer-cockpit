"use client";

/**
 * Minimales Single-Mode-Accordion (B+4.3.1b).
 *
 * Compound-API analog zu shadcn/radix, aber ohne externe
 * Abhaengigkeiten:
 *
 *   <Accordion defaultValue="m-1">
 *     <AccordionItem value="m-1">
 *       <AccordionTrigger>Titel 1</AccordionTrigger>
 *       <AccordionContent>Inhalt 1</AccordionContent>
 *     </AccordionItem>
 *     <AccordionItem value="m-2">
 *       <AccordionTrigger>Titel 2</AccordionTrigger>
 *       <AccordionContent>Inhalt 2</AccordionContent>
 *     </AccordionItem>
 *   </Accordion>
 *
 * Single-Mode: immer nur ein Item offen. Falls `value`-Prop gesetzt
 * ist, laeuft das Accordion controlled; sonst uncontrolled mit
 * `defaultValue`.
 *
 * ARIA:
 *   - Trigger ist <button aria-expanded aria-controls>
 *   - Content hat role="region" aria-labelledby
 */

import {
  createContext,
  ReactNode,
  useContext,
  useId,
  useMemo,
  useState,
} from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

type AccordionCtx = {
  activeValue: string | null;
  setActiveValue: (v: string | null) => void;
};

const AccordionContext = createContext<AccordionCtx | null>(null);

function useAccordion() {
  const ctx = useContext(AccordionContext);
  if (!ctx) {
    throw new Error(
      "AccordionItem/Trigger/Content must be used inside <Accordion>",
    );
  }
  return ctx;
}

type ItemCtx = {
  value: string;
  isOpen: boolean;
  toggle: () => void;
  headerId: string;
  panelId: string;
};

const AccordionItemContext = createContext<ItemCtx | null>(null);

function useItem() {
  const ctx = useContext(AccordionItemContext);
  if (!ctx) {
    throw new Error(
      "AccordionTrigger/Content must be used inside <AccordionItem>",
    );
  }
  return ctx;
}

// -----------------------------------------------------------------
// Accordion (Root)
// -----------------------------------------------------------------
export type AccordionProps = {
  /** Kontrollierter Wert — wenn gesetzt, muss auch onValueChange kommen. */
  value?: string | null;
  onValueChange?: (v: string | null) => void;
  /** Uncontrolled: initial offenes Item. */
  defaultValue?: string | null;
  /** Darf sich das aktive Item zuklappen? Default: true. */
  collapsible?: boolean;
  children: ReactNode;
  className?: string;
};

export function Accordion({
  value,
  onValueChange,
  defaultValue = null,
  collapsible = true,
  children,
  className,
}: AccordionProps) {
  const [internal, setInternal] = useState<string | null>(defaultValue);
  const isControlled = value !== undefined;
  const activeValue = isControlled ? (value ?? null) : internal;

  const setActiveValue = (v: string | null) => {
    if (!isControlled) setInternal(v);
    onValueChange?.(v);
  };

  const ctx = useMemo<AccordionCtx>(
    () => ({
      activeValue,
      setActiveValue: (next: string | null) => {
        if (next === activeValue && !collapsible) return;
        setActiveValue(next === activeValue ? null : next);
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeValue, collapsible, isControlled],
  );

  return (
    <AccordionContext.Provider value={ctx}>
      <div className={cn("divide-y divide-slate-200", className)}>
        {children}
      </div>
    </AccordionContext.Provider>
  );
}

// -----------------------------------------------------------------
// AccordionItem
// -----------------------------------------------------------------
export function AccordionItem({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const { activeValue, setActiveValue } = useAccordion();
  const headerId = useId();
  const panelId = useId();
  const isOpen = activeValue === value;
  const toggle = () => setActiveValue(value);

  const ctx = useMemo<ItemCtx>(
    () => ({ value, isOpen, toggle, headerId, panelId }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [value, isOpen],
  );

  return (
    <AccordionItemContext.Provider value={ctx}>
      <div className={cn("py-0", className)} data-state={isOpen ? "open" : "closed"}>
        {children}
      </div>
    </AccordionItemContext.Provider>
  );
}

// -----------------------------------------------------------------
// AccordionTrigger
// -----------------------------------------------------------------
export function AccordionTrigger({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const { isOpen, toggle, headerId, panelId } = useItem();
  return (
    <h3 id={headerId} className="m-0">
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={toggle}
        className={cn(
          "w-full flex items-center justify-between gap-2 py-3 text-left",
          "text-slate-900 font-medium hover:bg-slate-50 rounded-md px-2",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-bauplan-500",
          className,
        )}
      >
        <span className="flex-1 min-w-0 truncate">{children}</span>
        <ChevronDown
          className={cn(
            "w-4 h-4 shrink-0 text-slate-500 transition-transform",
            isOpen && "rotate-180",
          )}
          aria-hidden="true"
        />
      </button>
    </h3>
  );
}

// -----------------------------------------------------------------
// AccordionContent
// -----------------------------------------------------------------
export function AccordionContent({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const { isOpen, headerId, panelId } = useItem();
  if (!isOpen) return null;
  return (
    <div
      id={panelId}
      role="region"
      aria-labelledby={headerId}
      className={cn("px-2 pb-4 pt-1 text-sm text-slate-700", className)}
    >
      {children}
    </div>
  );
}

export default Accordion;
