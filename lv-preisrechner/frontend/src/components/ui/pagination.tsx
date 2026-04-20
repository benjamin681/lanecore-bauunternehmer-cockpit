"use client";

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { cn } from "@/lib/cn";

export type PaginationProps = {
  /** 1-basierte aktuelle Seite */
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** Fuer "X-Y von Z"-Anzeige (optional) */
  totalItems?: number;
  itemsPerPage?: number;
  /** Max sichtbare Seitenzahl-Buttons auf Desktop (default 7) */
  maxVisible?: number;
  className?: string;
};

/** Baut die Liste der anzuzeigenden Seiten — inklusive "..." als string. */
function buildPageList(current: number, total: number, maxVisible: number): Array<number | "dots"> {
  if (total <= maxVisible) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  // Randbereiche: erste + letzte Seite immer sichtbar.
  // Fenster um `current` herum, mit "..." auf Luecken.
  const pages: Array<number | "dots"> = [];
  const siblings = Math.max(1, Math.floor((maxVisible - 3) / 2)); // ohne first/last/current
  const left = Math.max(2, current - siblings);
  const right = Math.min(total - 1, current + siblings);

  pages.push(1);
  if (left > 2) pages.push("dots");
  for (let p = left; p <= right; p++) pages.push(p);
  if (right < total - 1) pages.push("dots");
  pages.push(total);
  return pages;
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  totalItems,
  itemsPerPage,
  maxVisible = 7,
  className,
}: PaginationProps) {
  if (totalPages <= 1 && !totalItems) return null;

  const pages = buildPageList(currentPage, totalPages, maxVisible);
  const canPrev = currentPage > 1;
  const canNext = currentPage < totalPages;

  // "X-Y von Z"
  let range = "";
  if (totalItems && itemsPerPage) {
    const from = (currentPage - 1) * itemsPerPage + 1;
    const to = Math.min(totalItems, currentPage * itemsPerPage);
    range = totalItems === 0 ? "0 Einträge" : `${from}–${to} von ${totalItems}`;
  }

  const pageBtn = (
    content: React.ReactNode,
    {
      key,
      onClick,
      disabled,
      active,
      ariaLabel,
    }: {
      key?: string | number;
      onClick?: () => void;
      disabled?: boolean;
      active?: boolean;
      ariaLabel?: string;
    },
  ) => (
    <button
      key={key}
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-current={active ? "page" : undefined}
      className={cn(
        "min-w-[36px] h-9 px-2.5 rounded-lg text-sm font-medium inline-flex items-center justify-center",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-bauplan-500",
        active
          ? "bg-bauplan-600 text-white"
          : "text-slate-700 hover:bg-slate-100 disabled:text-slate-300 disabled:hover:bg-transparent",
        disabled && "cursor-not-allowed",
      )}
    >
      {content}
    </button>
  );

  return (
    <nav
      aria-label="Seiten-Navigation"
      className={cn("flex items-center justify-between gap-4 flex-wrap", className)}
    >
      {/* Range-Anzeige */}
      {range && <div className="text-sm text-slate-500">{range}</div>}

      {/* Mobile: nur Zurueck / Vor */}
      <div className="flex items-center gap-1 sm:hidden">
        {pageBtn(
          <>
            <ChevronLeft className="w-4 h-4" /> Zurück
          </>,
          {
            key: "m-prev",
            onClick: () => onPageChange(currentPage - 1),
            disabled: !canPrev,
            ariaLabel: "Vorherige Seite",
          },
        )}
        <span className="px-3 text-sm text-slate-600">
          {currentPage} / {totalPages}
        </span>
        {pageBtn(
          <>
            Vor <ChevronRight className="w-4 h-4" />
          </>,
          {
            key: "m-next",
            onClick: () => onPageChange(currentPage + 1),
            disabled: !canNext,
            ariaLabel: "Naechste Seite",
          },
        )}
      </div>

      {/* Desktop: volle Navigation */}
      <div className="hidden sm:flex items-center gap-1">
        {pageBtn(<ChevronsLeft className="w-4 h-4" />, {
          key: "d-first",
          onClick: () => onPageChange(1),
          disabled: !canPrev,
          ariaLabel: "Erste Seite",
        })}
        {pageBtn(<ChevronLeft className="w-4 h-4" />, {
          key: "d-prev",
          onClick: () => onPageChange(currentPage - 1),
          disabled: !canPrev,
          ariaLabel: "Vorherige Seite",
        })}
        {pages.map((p, i) =>
          p === "dots" ? (
            <span key={`d-dots-${i}`} className="px-2 text-slate-400 select-none">
              …
            </span>
          ) : (
            pageBtn(p, {
              key: `p-${p}`,
              onClick: () => onPageChange(p),
              active: p === currentPage,
              ariaLabel: `Seite ${p}`,
            })
          ),
        )}
        {pageBtn(<ChevronRight className="w-4 h-4" />, {
          key: "d-next",
          onClick: () => onPageChange(currentPage + 1),
          disabled: !canNext,
          ariaLabel: "Naechste Seite",
        })}
        {pageBtn(<ChevronsRight className="w-4 h-4" />, {
          key: "d-last",
          onClick: () => onPageChange(totalPages),
          disabled: !canNext,
          ariaLabel: "Letzte Seite",
        })}
      </div>
    </nav>
  );
}

export default Pagination;
