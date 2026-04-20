"use client";

/**
 * API-Client fuer die neue /pricing/*-Endpoints (B+1/B+2).
 *
 * Nicht zu verwechseln mit den Legacy-Calls in api.ts ("/price-lists").
 * Die beiden Systeme laufen parallel.
 */

import { api } from "@/lib/api";
import type {
  ListPricelistsQuery,
  SupplierPriceList,
  SupplierPriceListDetail,
  SupplierPriceEntry,
} from "@/lib/types/pricing";

function _qs(params: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

/** Upload-Parameter. Die Datei selbst kommt als FormData, der Rest als Felder. */
export type UploadParams = {
  file: File;
  supplier_name: string;
  list_name: string;
  valid_from: string; // YYYY-MM-DD
  supplier_location?: string;
  valid_until?: string;
  auto_parse?: boolean;
};

export const pricingApi = {
  listPricelists: (q: ListPricelistsQuery = {}) =>
    api<SupplierPriceList[]>(`/pricing/pricelists${_qs(q)}`),

  getPricelist: (id: string, opts: { includeEntries?: boolean; offset?: number; limit?: number } = {}) =>
    api<SupplierPriceListDetail>(
      `/pricing/pricelists/${id}${_qs({
        include_entries: opts.includeEntries,
        entries_offset: opts.offset,
        entries_limit: opts.limit,
      })}`,
    ),

  uploadPricelist: (p: UploadParams) => {
    const fd = new FormData();
    fd.append("file", p.file);
    fd.append("supplier_name", p.supplier_name);
    fd.append("list_name", p.list_name);
    fd.append("valid_from", p.valid_from);
    if (p.supplier_location) fd.append("supplier_location", p.supplier_location);
    if (p.valid_until) fd.append("valid_until", p.valid_until);
    fd.append("auto_parse", p.auto_parse === false ? "false" : "true");
    // Grosse Uploads gehen direkt ans Backend (Vercel-Proxy hat 4.5 MB-Limit).
    return api<SupplierPriceList>("/pricing/upload", {
      method: "POST",
      form: fd,
      direct: true,
    });
  },

  /** Soft-Delete (Archive) */
  deletePricelist: (id: string) =>
    api<SupplierPriceList>(`/pricing/pricelists/${id}`, { method: "DELETE" }),

  activatePricelist: (id: string) =>
    api<SupplierPriceList>(`/pricing/pricelists/${id}/activate`, { method: "POST" }),

  parsePricelist: (id: string) =>
    api<SupplierPriceList>(`/pricing/pricelists/${id}/parse`, { method: "POST" }),

  listReviewNeeded: (id: string, opts: { offset?: number; limit?: number } = {}) =>
    api<SupplierPriceEntry[]>(
      `/pricing/pricelists/${id}/review-needed${_qs({
        offset: opts.offset,
        limit: opts.limit,
      })}`,
    ),
};

export type PricingApi = typeof pricingApi;
