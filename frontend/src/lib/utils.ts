import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merges tailwind classes (shadcn/ui pattern). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Formats a number as m² (German locale). */
export function formatM2(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "\u2014";
  return `${val.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m²`;
}

/** Formats a number as meters (German locale). */
export function formatM(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "\u2014";
  return `${val.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m`;
}

/** Formats a date string as German locale. */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}
