/**
 * TypeScript-Typen fuer die neue Pricing-API (B+1/B+2).
 *
 * Schema-Quelle: lv-preisrechner/backend/app/schemas/pricing.py
 * Nicht zu verwechseln mit den Legacy-Typen PriceList / PriceEntry in api.ts
 * (die sprechen den alten /price-lists-Endpoint).
 */

/** Status-Enum aus app/models/pricing.py:PricelistStatus */
export type PricingStatus =
  | "PENDING_PARSE"
  | "PARSING"
  | "PARSED"
  | "REVIEWED"
  | "APPROVED"
  | "ARCHIVED"
  | "ERROR";

export const PRICING_STATUS_VALUES: PricingStatus[] = [
  "PENDING_PARSE",
  "PARSING",
  "PARSED",
  "REVIEWED",
  "APPROVED",
  "ARCHIVED",
  "ERROR",
];

/** Menschlich lesbare Bezeichnung + Badge-Variant je Status. */
export const PRICING_STATUS_META: Record<
  PricingStatus,
  { label: string; badge: "default" | "info" | "warning" | "success" | "danger" }
> = {
  PENDING_PARSE: { label: "Warten auf Parse", badge: "info" },
  PARSING: { label: "Wird geparst …", badge: "info" },
  PARSED: { label: "Geparst", badge: "info" },
  REVIEWED: { label: "Review abgeschlossen", badge: "info" },
  APPROVED: { label: "Freigegeben", badge: "success" },
  ARCHIVED: { label: "Archiviert", badge: "default" },
  ERROR: { label: "Fehler", badge: "danger" },
};

/** SupplierPriceListOut */
export type SupplierPriceList = {
  id: string;
  tenant_id: string;
  supplier_name: string;
  supplier_location: string | null;
  list_name: string;
  valid_from: string; // ISO-Date YYYY-MM-DD
  valid_until: string | null;
  source_file_path: string;
  source_file_hash: string;
  status: PricingStatus;
  parse_error: string | null;
  entries_total: number | null;
  entries_reviewed: number | null;
  is_active: boolean;
  uploaded_by_user_id: string;
  uploaded_at: string; // ISO-Datetime
  approved_by_user_id: string | null;
  approved_at: string | null;
};

/** SupplierPriceEntryOut */
export type SupplierPriceEntry = {
  id: string;
  pricelist_id: string;
  tenant_id: string;
  article_number: string | null;
  manufacturer: string | null;
  product_name: string;
  category: string | null;
  subcategory: string | null;
  price_net: number;
  currency: string;
  unit: string;
  package_size: number | null;
  package_unit: string | null;
  pieces_per_package: number | null;
  effective_unit: string;
  price_per_effective_unit: number;
  attributes: Record<string, unknown>;
  source_page: number | null;
  parser_confidence: number;
  needs_review: boolean;
  reviewed_by_user_id?: string | null;
  reviewed_at?: string | null;
  correction_applied?: boolean;
};

/** Partial-Update-Payload fuer PATCH /entries/{id} */
export type SupplierPriceEntryUpdate = Partial<{
  article_number: string | null;
  manufacturer: string | null;
  product_name: string;
  category: string | null;
  subcategory: string | null;
  price_net: number;
  unit: string;
  effective_unit: string;
  price_per_effective_unit: number;
  package_size: number | null;
  package_unit: string | null;
  pieces_per_package: number | null;
  attributes: Record<string, unknown>;
  needs_review: boolean;
}>;

/** SupplierPriceListDetail: Liste plus optional geladene Entries */
export type SupplierPriceListDetail = SupplierPriceList & {
  entries: SupplierPriceEntry[];
};

/** Filter-Params fuer listPricelists. */
export type ListPricelistsQuery = {
  status?: PricingStatus | null;
  supplier_name?: string | null;
  active?: boolean | null;
  offset?: number;
  limit?: number;
};
