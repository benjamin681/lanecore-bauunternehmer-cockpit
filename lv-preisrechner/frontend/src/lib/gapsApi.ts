"use client";

/**
 * API-Client fuer den Katalog-Luecken-Endpoint (B+4.3.1c).
 *
 * Konsumiert den bestehenden Backend-Endpoint:
 *   GET /api/v1/lvs/{lv_id}/gaps?include_low_confidence=<bool>
 *
 * Types spiegeln die Pydantic-Schemas aus
 * ``backend/app/schemas/gaps.py`` (B+4.3.0c).
 */

import { api } from "@/lib/api";

/**
 * Severity-Klassifizierung einer Katalog-Luecke.
 *
 * Reihenfolge der Prioritaet (aus Backend):
 *   missing > low_confidence > estimated
 *
 * - ``missing``         — kein Katalog-Match (``price_source=not_found``)
 * - ``low_confidence``  — supplier_price, aber ``match_confidence<0.5``;
 *                         erscheint nur mit ``include_low_confidence=true``
 * - ``estimated``       — Kategorie-Mittelwert-Schaetzung (Stage 4)
 */
export type GapSeverity = "missing" | "low_confidence" | "estimated";

export interface CatalogGapEntry {
  position_id: string;
  position_oz: string;
  position_name: string;
  material_name: string;
  material_dna: string;
  required_amount: number;
  unit: string;
  severity: GapSeverity;
  price_source: string;
  /** Bei ``severity=missing`` ist der Wert ``null`` (keine Confidence). */
  match_confidence: number | null;
  source_description: string;
  needs_review: boolean;
}

/** B+4.6 — per-DNA deduplizierte Gap-Liste für das UI. */
export interface UniqueMissingMaterial {
  material_dna: string;
  material_name: string;
  unit: string;
  severity: GapSeverity;
  betroffene_positionen: string[];
  total_required_amount: number;
  geschaetzter_preis: number | null;
  geschaetzter_preis_einheit: string | null;
  resolution: {
    resolution_type: string;
    resolved_value: Record<string, unknown> | null;
    created_at: string;
  } | null;
}

export interface LVGapsReport {
  lv_id: string;
  total_positions: number;
  total_materials: number;
  gaps_count: number;
  missing_count: number;
  estimated_count: number;
  low_confidence_count: number;
  gaps: CatalogGapEntry[];
  unique_missing_materials?: UniqueMissingMaterial[];
}

/** B+4.6 — POST /lvs/{lv_id}/gaps/resolve */
export type GapResolutionType = "manual_price" | "skip";

export interface GapResolveRequest {
  material_dna: string;
  resolution_type: GapResolutionType;
  value: Record<string, unknown>;
}

export interface GapResolutionOut {
  id: string;
  lv_id: string;
  tenant_id: string;
  material_dna: string;
  resolution_type: string;
  resolved_value: Record<string, unknown> | null;
  tenant_price_override_id: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface GapResolveResponse {
  resolution: GapResolutionOut;
  recalculated: boolean;
}

/**
 * Laedt den Katalog-Luecken-Report eines LVs.
 *
 * @param lvId                UUID-String des LVs
 * @param includeLowConfidence Wenn ``true``, enthaelt der Report
 *                             zusaetzlich ``supplier_price``-Matches mit
 *                             ``match_confidence < 0.5`` als severity
 *                             ``low_confidence``. Default ``false``
 *                             (matched Backend-Default); in dem Fall
 *                             wird KEIN Query-Param gesendet, um
 *                             URL-Bytes zu sparen und die Default-
 *                             Bedeutung konsistent zu halten.
 */
export async function fetchGaps(
  lvId: string,
  includeLowConfidence: boolean = false,
): Promise<LVGapsReport> {
  const qs = includeLowConfidence ? "?include_low_confidence=true" : "";
  return api<LVGapsReport>(`/lvs/${lvId}/gaps${qs}`);
}

/**
 * B+4.6 — loest eine Katalog-Luecke per manuellem Preis oder Skip.
 *
 * Bei manual_price wird zusaetzlich ein Tenant-Override angelegt; der
 * Server rekalkuliert das LV direkt (recalculate=true default). Die
 * neuen EPs sind nach der Response sichtbar.
 */
export async function resolveGap(
  lvId: string,
  body: GapResolveRequest,
  recalculate: boolean = true,
): Promise<GapResolveResponse> {
  const qs = recalculate ? "" : "?recalculate=false";
  return api<GapResolveResponse>(`/lvs/${lvId}/gaps/resolve${qs}`, {
    method: "POST",
    body,
  });
}
