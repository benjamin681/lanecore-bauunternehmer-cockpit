"use client";

/**
 * API-Client fuer den Candidates-Endpoint + Manual-Override (B+4.3.1b).
 *
 * Konsumiert zwei bestehende Backend-Endpoints:
 *   GET   /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates
 *   PATCH /api/v1/lvs/{lv_id}/positions/{pos_id}
 *
 * Types spiegeln die Pydantic-Schemas aus
 * ``backend/app/schemas/candidates.py`` (siehe B+4.3.0b-Baseline).
 */

import { api } from "@/lib/api";

/**
 * Stage im Candidates-Response.
 *
 * Die Werte werden vom Backend in
 * ``price_lookup.list_candidates_for_position`` bestimmt:
 *   - ``supplier_price`` — Fuzzy-Score >= FUZZY_MATCH_THRESHOLD
 *   - ``fuzzy``          — Score unter Threshold, aber im Pool
 *   - ``estimated``      — Kategorie-Mittelwert als virtueller Eintrag
 */
export type Stage = "supplier_price" | "fuzzy" | "estimated";

export interface Candidate {
  pricelist_name: string;
  candidate_name: string;
  /** 0.0 – 1.0 (gerundet auf 3 Nachkommastellen durch Backend). */
  match_confidence: number;
  stage: Stage;
  price_net: number;
  unit: string;
  /** Freitext-Begruendung, z. B. "Fuzzy-Aehnlichkeit 73%" oder
   *  "O Kategorie Daemmung (17 Eintraege)". */
  match_reason: string;
}

export interface MaterialWithCandidates {
  material_name: string;
  required_amount: number;
  unit: string;
  /** Top-N echte Kandidaten + 1 virtueller estimated-Eintrag als
   *  Abschluss (siehe Backend-Design-Entscheidung B+4.3.0b-d). */
  candidates: Candidate[];
}

export interface PositionCandidates {
  position_id: string;
  position_name: string;
  materials: MaterialWithCandidates[];
}

/**
 * Laedt die Top-N Kandidaten-Liste pro Material fuer eine Position.
 *
 * @param lvId   UUID-String des LVs
 * @param posId  UUID-String der Position
 * @param limit  Top-N echte Kandidaten (1-5, Default 3). Der
 *               estimated-Eintrag wird vom Backend immer zusaetzlich
 *               angehaengt, d. h. das Array hat bis zu ``limit + 1``
 *               Elemente.
 */
export async function fetchCandidates(
  lvId: string,
  posId: string,
  limit: number = 3,
): Promise<PositionCandidates> {
  return api<PositionCandidates>(
    `/lvs/${lvId}/positions/${posId}/candidates?limit=${limit}`,
  );
}

/**
 * Aktualisiert den Einzelpreis (EP) einer LV-Position.
 *
 * Wird vom Near-Miss-Drawer aufgerufen, wenn der Handwerker einen
 * anderen Kandidaten uebernimmt oder einen Preis manuell eingibt.
 * Der uebergebene Wert landet direkt in Position.ep; das Backend
 * berechnet keine Materialien daraus neu.
 */
export async function updatePositionEp(
  lvId: string,
  posId: string,
  ep: number,
): Promise<void> {
  await api(`/lvs/${lvId}/positions/${posId}`, {
    method: "PATCH",
    body: { ep },
  });
}
