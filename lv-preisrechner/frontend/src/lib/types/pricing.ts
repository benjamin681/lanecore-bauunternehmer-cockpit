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
  | "PARTIAL_PARSE"
  | "REVIEWED"
  | "APPROVED"
  | "ARCHIVED"
  | "ERROR";

export const PRICING_STATUS_VALUES: PricingStatus[] = [
  "PENDING_PARSE",
  "PARSING",
  "PARSED",
  "PARTIAL_PARSE",
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
  PARTIAL_PARSE: { label: "Teilweise geparst", badge: "warning" },
  REVIEWED: { label: "Review abgeschlossen", badge: "info" },
  APPROVED: { label: "Freigegeben", badge: "success" },
  ARCHIVED: { label: "Archiviert", badge: "default" },
  ERROR: { label: "Fehler", badge: "danger" },
};

/** B+4.5 — strukturierter Batch-Fehler aus dem Parser. */
export type ParseErrorDetail = {
  batch_idx: number;
  page_range: string;
  attempts: number;
  error_class: string;
  error_message: string;
  raw_response_file: string | null;
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
  parse_error_details: ParseErrorDetail[] | null;
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
  source_row_raw?: string | null;
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


// --------------------------------------------------------------------------- //
// Review / Correction (B+4.4 P4)
// --------------------------------------------------------------------------- //

/** Normierte review_reason-Werte aus app/services/pricelist_parser.py. */
export const REVIEW_REASON_LABELS: Record<string, string> = {
  bundgroesse_fehlt: "Bundgröße fehlt",
  bundpreis_vs_einzelpreis_unklar: "Bund- oder Einzelpreis unklar",
  preis_ausserhalb_korridor: "Preis außerhalb des Korridors",
  einheit_nicht_erkannt: "Einheit nicht erkannt",
  unknown: "Ohne strukturierten Grund",
};

export type EntryReviewItem = {
  id: string;
  pricelist_id: string;
  article_number: string | null;
  manufacturer: string | null;
  product_name: string;
  price_net: number;
  currency: string;
  unit: string;
  package_size: number | null;
  pieces_per_package: number | null;
  effective_unit: string;
  price_per_effective_unit: number;
  source_page: number | null;
  source_row_raw: string | null;
  review_reason: string | null;
  attributes: Record<string, unknown>;
  parser_confidence: number;
};

export type EntryReviewGroup = {
  review_reason: string;
  count: number;
  items: EntryReviewItem[];
};

export type EntryReviewResponse = {
  pricelist_id: string;
  total_needs_review: number;
  groups: EntryReviewGroup[];
};

/** Backend: ProductCorrectionType-Enum-Werte. */
export type ProductCorrectionType =
  | "pieces_per_package"
  | "unit_override"
  | "price_per_effective_unit"
  | "confirmed_as_is";

export type CorrectEntryRequest = {
  correction_type: ProductCorrectionType;
  corrected_value: Record<string, unknown>;
  persist?: boolean;
};

export type CorrectEntryResponse = {
  entry: SupplierPriceEntry;
  correction_persisted: boolean;
  correction_id: string | null;
};
