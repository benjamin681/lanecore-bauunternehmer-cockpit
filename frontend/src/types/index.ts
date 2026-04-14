/** Frontend TypeScript types matching backend schemas. */

// --- Job Status ---

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface AnalyseStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  filename: string | null;
  error_message: string | null;
  created_at: string | null;
}

// --- Analyse Result ---

export interface RaumSchema {
  bezeichnung: string;
  raum_nr: string | null;
  flaeche_m2: number | null;
  breite_m: number | null;
  tiefe_m: number | null;
  hoehe_m: number | null;
  nutzung: string | null;
  deckentyp: string | null;
}

export interface WandSchema {
  id: string;
  typ: string;
  laenge_m: number;
  hoehe_m: number;
  flaeche_m2: number | null;
  von_raum: string | null;
  zu_raum: string | null;
  unsicher: boolean;
  notizen: string | null;
}

export interface DeckeSchema {
  raum: string;
  raum_nr: string | null;
  typ: string;
  system: string | null;
  flaeche_m2: number | null;
  abhaengehoehe_m: number | null;
  beplankung: string | null;
  profil: string | null;
  entfaellt: boolean;
}

export interface AnalyseResultResponse {
  job_id: string;
  status: string;
  plantyp: string | null;
  massstab: string | null;
  geschoss: string | null;
  raeume: RaumSchema[];
  waende: WandSchema[];
  decken: DeckeSchema[];
  warnungen: string[];
  konfidenz: number;
  model_used: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  summary: {
    gesamt_raumflaeche: number;
    anzahl_raeume: number;
  };
}

// --- Dashboard ---

export interface DashboardStats {
  projekte: number;
  analysen_gesamt: number;
  analysen_erfolgreich: number;
  eingesparte_stunden: number;
  kosten_usd_gesamt: number;
}

// --- Projekte ---

export interface Projekt {
  id: string;
  name: string;
  auftraggeber: string | null;
  beschreibung: string | null;
  created_at: string;
  updated_at: string;
  analyse_count: number;
}
