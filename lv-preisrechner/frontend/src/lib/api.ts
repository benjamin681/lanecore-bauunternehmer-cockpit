"use client";

const TOKEN_KEY = "lvp_token";

// Direct Backend-URL (umgeht Vercel-Proxy wegen 4.5 MB Body-Limit)
// Public env, per Build oder per window-Global gesetzt.
const BACKEND_URL_DIRECT =
  (typeof process !== "undefined" &&
    (process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL)) ||
  "";

function apiBase(directCall: boolean): string {
  if (directCall && BACKEND_URL_DIRECT) return `${BACKEND_URL_DIRECT}/api/v1`;
  return "/api/v1";
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export function hasToken(): boolean {
  return !!getToken();
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  form?: FormData;
  raw?: boolean; // Blob-Rückgabe
  direct?: boolean; // Direkt ans Backend (umgeht Vercel-Proxy, nützlich bei großen Uploads)
  signal?: AbortSignal;
};

export class ApiError extends Error {
  status: number;
  detail?: string;
  constructor(status: number, detail?: string) {
    super(detail ? `HTTP ${status}: ${detail}` : `HTTP ${status}`);
    this.status = status;
    this.detail = detail || `HTTP ${status}`;
  }
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(`${apiBase(!!opts.direct)}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body,
      signal: opts.signal,
    });
  } catch (networkErr: any) {
    if (networkErr?.name === "AbortError") {
      throw new ApiError(0, "Abgebrochen");
    }
    throw new ApiError(0, `Netzwerk-Fehler: ${networkErr?.message || "Unbekannt"}`);
  }

  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.clone().json();
      if (typeof j?.detail === "string") {
        detail = j.detail;
      } else if (Array.isArray(j?.detail)) {
        // FastAPI 422-Format: [{loc, msg, type}]
        detail = j.detail
          .map((d: any) => d?.msg || JSON.stringify(d))
          .join(", ");
      } else {
        detail = JSON.stringify(j);
      }
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = "";
      }
    }
    // Global 401-Handling: Token wegwerfen + zu /login
    if (res.status === 401 && typeof window !== "undefined") {
      clearToken();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.replace("/login");
      }
    }
    throw new ApiError(res.status, detail);
  }

  if (opts.raw) {
    return (await res.blob()) as unknown as T;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Typed wrappers --------------------------------------------------------
export type User = {
  user_id: string;
  email: string;
  vorname: string;
  nachname: string;
  tenant_id: string;
  firma: string;
  stundensatz_eur: number;
  bgk_prozent: number;
  agk_prozent: number;
  wg_prozent: number;
  // B+4.3.1: Neue Preis-Engine (Lookup gegen SupplierPriceList / Overrides)
  use_new_pricing: boolean;
};

export type PricingReadiness = {
  has_active_pricelist: boolean;
  has_overrides: boolean;
  ready_for_new_pricing: boolean;
};

export async function getPricingReadiness(): Promise<PricingReadiness> {
  return api<PricingReadiness>("/pricing/readiness");
}

export type PriceList = {
  id: string;
  haendler: string;
  niederlassung: string;
  stand_monat: string;
  original_dateiname: string;
  status: string;
  aktiv: boolean;
  eintraege_gesamt: number;
  eintraege_unsicher: number;
  created_at: string;
};

export type PriceEntry = {
  id: string;
  art_nr: string;
  dna: string;
  hersteller: string;
  kategorie: string;
  produktname: string;
  abmessungen: string;
  variante: string;
  preis: number;
  einheit: string;
  preis_pro_basis: number;
  basis_einheit: string;
  konfidenz: number;
  manuell_korrigiert: boolean;
};

export type PriceListDetail = PriceList & { entries: PriceEntry[] };

export type Position = {
  id: string;
  reihenfolge: number;
  oz: string;
  titel: string;
  kurztext: string;
  menge: number;
  einheit: string;
  erkanntes_system: string;
  feuerwiderstand: string;
  plattentyp: string;
  materialien: unknown[];
  material_ep: number;
  lohn_stunden: number;
  lohn_ep: number;
  zuschlaege_ep: number;
  ep: number;
  gp: number;
  konfidenz: number;
  manuell_korrigiert: boolean;
  warnung: string;
  // B+4.2: Preis-Herkunft (aggregiert pro Position, Details im
  // materialien-JSON). Default-Strings/false fuer Legacy-Backends,
  // die das Feld nicht liefern.
  needs_price_review?: boolean;
  price_source_summary?: string;
};

export type LV = {
  id: string;
  projekt_name: string;
  auftraggeber: string;
  original_dateiname: string;
  status: string;
  positionen_gesamt: number;
  positionen_gematcht: number;
  positionen_unsicher: number;
  angebotssumme_netto: number;
  /** B+4.9: optionale Verknuepfung zum Project. NULL = "Lose LVs". */
  project_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type LVDetail = LV & { positions: Position[] };

export type Job = {
  id: string;
  kind: string;
  status: "queued" | "running" | "done" | "error" | string;
  target_id: string;
  target_kind: string;
  progress: number;
  message: string;
  error_message: string;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

/** Pollt einen Job bis er fertig ist. Retry bei Network-Errors. */
export async function pollJob(
  jobId: string,
  opts: {
    intervalMs?: number;
    timeoutMs?: number;
    onProgress?: (j: Job) => void;
  } = {},
): Promise<Job> {
  const interval = opts.intervalMs ?? 3000;
  const timeout = opts.timeoutMs ?? 15 * 60 * 1000; // 15 Min
  const start = Date.now();
  let consecutiveErrors = 0;
  while (Date.now() - start < timeout) {
    try {
      const job = await api<Job>(`/jobs/${jobId}`);
      consecutiveErrors = 0;
      opts.onProgress?.(job);
      if (job.status === "done" || job.status === "error") return job;
    } catch (e: any) {
      consecutiveErrors += 1;
      // 401 → Auth-Fehler, weitergeben
      if (e?.status === 401) throw e;
      // Bei > 5 Netz-Fehlern in Folge aufgeben
      if (consecutiveErrors > 5) throw e;
      // sonst weiter pollen (Netz wackelig / Mobile Screen-Off)
    }
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new ApiError(0, "Job läuft länger als erwartet — Seite neu laden und unter 'LVs' prüfen");
}
