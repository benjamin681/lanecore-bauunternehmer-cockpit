"use client";

import { ReactNode, useMemo } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/cn";

export type SortDirection = "asc" | "desc";

export type TableColumn<T> = {
  /** Stable key, z.B. "product_name" */
  key: string;
  /** Angezeigter Spalten-Titel */
  label: ReactNode;
  /** Wenn true: Spalte ist sortierbar, Header wird klickbar */
  sortable?: boolean;
  /** Eigene Render-Funktion fuer die Zelle. Wenn nicht gesetzt, wird
   *  row[key as keyof T] direkt ausgegeben (nur fuer primitive Werte sinnvoll). */
  render?: (row: T, rowIndex: number) => ReactNode;
  /** Zusaetzliche Klassen fuer die td */
  className?: string;
  /** Zusaetzliche Klassen fuer die th */
  headerClassName?: string;
  /** Horizontale Ausrichtung */
  align?: "left" | "center" | "right";
};

export type TableProps<T> = {
  data: T[];
  columns: TableColumn<T>[];
  /** Eindeutiger Row-Key. Default: rowIndex */
  getRowKey?: (row: T, index: number) => string | number;
  /** Wird beim Klick auf einen Zeilenbereich aufgerufen (optional) */
  onRowClick?: (row: T, index: number) => void;
  /** Spalten-Key nach dem aktuell sortiert wird */
  sortBy?: string;
  sortDirection?: SortDirection;
  /** Wird aufgerufen, wenn User auf einen sortierbaren Header klickt */
  onSort?: (key: string, direction: SortDirection) => void;
  /** Placeholder wenn data leer */
  empty?: ReactNode;
  /** Zebra-Striping an/aus (default: an) */
  striped?: boolean;
  /** Kompaktere Zeilen (default: false) */
  dense?: boolean;
  className?: string;
};

const ALIGN: Record<"left" | "center" | "right", string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

export function Table<T>({
  data,
  columns,
  getRowKey,
  onRowClick,
  sortBy,
  sortDirection,
  onSort,
  empty,
  striped = true,
  dense = false,
  className,
}: TableProps<T>) {
  const handleSort = useMemo(
    () => (col: TableColumn<T>) => {
      if (!col.sortable || !onSort) return;
      if (sortBy === col.key) {
        onSort(col.key, sortDirection === "asc" ? "desc" : "asc");
      } else {
        onSort(col.key, "asc");
      }
    },
    [onSort, sortBy, sortDirection],
  );

  const rowPadding = dense ? "py-2" : "py-3";

  return (
    <div className={cn("overflow-x-auto rounded-xl border border-slate-200 bg-white", className)}>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            {columns.map((col) => {
              const isSortActive = col.sortable && sortBy === col.key;
              const Icon =
                !col.sortable
                  ? null
                  : isSortActive
                    ? sortDirection === "asc"
                      ? ArrowUp
                      : ArrowDown
                    : ArrowUpDown;
              return (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    "px-4 font-medium text-xs uppercase tracking-wide",
                    rowPadding,
                    ALIGN[col.align ?? "left"],
                    col.sortable && "cursor-pointer select-none hover:text-slate-900",
                    isSortActive && "text-slate-900",
                    col.headerClassName,
                  )}
                  onClick={col.sortable ? () => handleSort(col) : undefined}
                  aria-sort={
                    isSortActive
                      ? sortDirection === "asc"
                        ? "ascending"
                        : "descending"
                      : col.sortable
                        ? "none"
                        : undefined
                  }
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {Icon && <Icon className="w-3.5 h-3.5 opacity-70" />}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-12 text-center text-slate-500"
              >
                {empty ?? "Keine Daten"}
              </td>
            </tr>
          ) : (
            data.map((row, idx) => {
              const key = getRowKey ? getRowKey(row, idx) : idx;
              return (
                <tr
                  key={key}
                  onClick={onRowClick ? () => onRowClick(row, idx) : undefined}
                  className={cn(
                    "text-slate-800",
                    striped && idx % 2 === 1 && "bg-slate-50/40",
                    onRowClick && "cursor-pointer hover:bg-bauplan-50/60",
                    "transition-colors",
                  )}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        "px-4 align-middle",
                        rowPadding,
                        ALIGN[col.align ?? "left"],
                        col.className,
                      )}
                    >
                      {col.render
                        ? col.render(row, idx)
                        : // Safe-Default: Primitive in Zelle
                          String((row as Record<string, unknown>)[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default Table;
