/** Geteilte TypeScript-Typen zwischen Frontend und ggf. Backend-Client */

// ---- Analyse-Jobs ----

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface AnalyseJob {
  id: string;
  projektId: string;
  filename: string;
  status: JobStatus;
  progress: number; // 0–100
  errorMessage?: string;
  createdAt: string; // ISO 8601
  completedAt?: string;
}

// ---- Analyse-Ergebnisse ----

export interface Raum {
  bezeichnung: string;
  flaecheM2: number;
  breiteM?: number;
  tiefeM?: number;
  hoeheM?: number;
  nutzung?: string;
}

export interface Wand {
  id: string;
  typ: WandTyp;
  laengeM: number;
  hoeheM: number;
  flaecheM2: number; // netto (ohne Öffnungen)
  vonRaum?: string;
  zuRaum?: string;
  unsicher?: boolean;
  notizen?: string;
}

export type WandTyp =
  | "W112" // Standard, 1× GK
  | "W115" // Schallschutz, 2× GK
  | "W116" // Installationswand
  | "W118" // Brandschutz F90
  | "W125" // Schwere Trennwand
  | "Unbekannt";

export interface Decke {
  raum: string;
  typ: DeckenTyp;
  flaecheM2: number;
  abhaengehoeheM?: number;
}

export type DeckenTyp = "D112" | "D113" | "D115" | "Unbekannt";

export interface AnalyseErgebnis {
  jobId: string;
  massstab: string;
  geschoss?: string;
  gebaeudetyp?: string;
  raeume: Raum[];
  waende: Wand[];
  decken: Decke[];
  konfidenz: number; // 0.0–1.0
  warnungen: string[];
  nichtLesbar: string[];
  // Zusammenfassung
  summary: {
    gesamtWandflaeche: Record<WandTyp, number>; // m² pro Typ
    gesamtDeckenflaeche: Record<DeckenTyp, number>;
    gesamtRaumflaeche: number;
    anzahlRaeume: number;
  };
}

// ---- Projekte ----

export interface Projekt {
  id: string;
  name: string;
  auftraggeber?: string;
  beschreibung?: string;
  createdAt: string;
  updatedAt: string;
  analyseCount: number;
}

// ---- API Responses ----

export interface ApiResponse<T> {
  data: T;
  meta?: {
    page?: number;
    perPage?: number;
    total?: number;
  };
}

export interface ApiError {
  error: string;
  details?: Record<string, unknown>;
}
