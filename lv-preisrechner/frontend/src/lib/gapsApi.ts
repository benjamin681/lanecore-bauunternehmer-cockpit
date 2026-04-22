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

export interface LVGapsReport {
  lv_id: string;
  total_positions: number;
  total_materials: number;
  gaps_count: number;
  missing_count: number;
  estimated_count: number;
  low_confidence_count: number;
  gaps: CatalogGapEntry[];
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
