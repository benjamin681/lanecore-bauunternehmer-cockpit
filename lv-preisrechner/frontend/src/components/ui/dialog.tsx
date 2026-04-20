"use client";

import {
  ButtonHTMLAttributes,
  ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
} from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Button, ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/cn";

type Size = "sm" | "md" | "lg" | "xl";

const SIZES: Record<Size, string> = {
  sm: "sm:max-w-sm",
  md: "sm:max-w-md",
  lg: "sm:max-w-2xl",
  xl: "sm:max-w-4xl",
};

export type DialogAction = {
  label: ReactNode;
  onClick?: () => void | Promise<void>;
  variant?: ButtonProps["variant"];
  disabled?: boolean;
  /** Automatisch Dialog schliessen nach onClick (default: true) */
  autoClose?: boolean;
  type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
};

export type DialogProps = {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  actions?: DialogAction[];
  size?: Size;
  /** Close bei Klick auf Backdrop (default: true) */
  closeOnBackdrop?: boolean;
  /** Close bei Escape-Taste (default: true) */
  closeOnEscape?: boolean;
  /** Close-X im Header anzeigen (default: true) */
  showClose?: boolean;
  className?: string;
};

/** Sammelt alle fokussierbaren Elemente unter `root`. */
function getFocusable(root: HTMLElement): HTMLElement[] {
  const sel = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");
  return Array.from(root.querySelectorAll<HTMLElement>(sel)).filter(
    (el) => !el.hasAttribute("data-focus-ignore"),
  );
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  actions,
  size = "md",
  closeOnBackdrop = true,
  closeOnEscape = true,
  showClose = true,
  className,
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descId = useId();

  // Escape + Focus-Trap
  useEffect(() => {
    if (!open) return;
    lastFocusedRef.current = document.activeElement as HTMLElement | null;

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && closeOnEscape) {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key === "Tab" && panelRef.current) {
        const focusable = getFocusable(panelRef.current);
        if (focusable.length === 0) {
          e.preventDefault();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement as HTMLElement | null;
        if (e.shiftKey) {
          if (active === first || !panelRef.current.contains(active)) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (active === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    // Initial-Fokus ins Panel
    const t = setTimeout(() => {
      if (!panelRef.current) return;
      const focusable = getFocusable(panelRef.current);
      (focusable[0] ?? panelRef.current).focus();
    }, 0);

    document.addEventListener("keydown", handleKey);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", handleKey);
      // Fokus zurueck ans urspruengliche Element
      lastFocusedRef.current?.focus?.();
    };
  }, [open, closeOnEscape, onClose]);

  // body-scroll-lock
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Portal-Target erst nach Mount verfuegbar
  const handleBackdrop = useCallback(
    (e: React.MouseEvent) => {
      if (!closeOnBackdrop) return;
      if (e.target === e.currentTarget) onClose();
    },
    [closeOnBackdrop, onClose],
  );

  if (typeof document === "undefined" || !open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-stretch sm:items-center justify-center bg-black/50 backdrop-blur-sm"
      onMouseDown={handleBackdrop}
      aria-hidden={false}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cn(
          // Mobile Fullscreen, Desktop zentriert
          "w-full h-full sm:h-auto flex flex-col bg-white shadow-xl",
          "sm:rounded-xl sm:my-8 sm:mx-4 sm:max-h-[calc(100vh-4rem)]",
          SIZES[size],
          "focus:outline-none",
          className,
        )}
      >
        {(title || showClose) && (
          <div className="flex items-start justify-between gap-4 px-6 py-4 border-b border-slate-200">
            <div className="flex-1 min-w-0">
              {title && (
                <h2 id={titleId} className="text-lg font-semibold text-slate-900">
                  {title}
                </h2>
              )}
              {description && (
                <p id={descId} className="text-sm text-slate-600 mt-1">
                  {description}
                </p>
              )}
            </div>
            {showClose && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Schliessen"
                className="shrink-0 -mr-2 -mt-1 w-9 h-9 grid place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-bauplan-500"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        )}
        <div className="flex-1 overflow-auto px-6 py-5">{children}</div>
        {actions && actions.length > 0 && (
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 px-6 py-4 border-t border-slate-200 bg-slate-50 sm:rounded-b-xl">
            {actions.map((a, i) => (
              <Button
                key={i}
                type={a.type ?? "button"}
                variant={a.variant ?? "secondary"}
                disabled={a.disabled}
                onClick={async () => {
                  await a.onClick?.();
                  if (a.autoClose !== false) onClose();
                }}
              >
                {a.label}
              </Button>
            ))}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

export default Dialog;
