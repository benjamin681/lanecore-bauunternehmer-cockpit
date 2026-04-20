/**
 * API client for LaneCore Backend.
 * Uses Next.js rewrites (/api/* → backend) to avoid CORS.
 *
 * All functions accept an optional AbortSignal so callers can cancel
 * in-flight requests (e.g. on component unmount).
 */

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  body: any;
  constructor(message: string, status: number, body: any = null) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export interface RequestOpts extends Omit<RequestInit, "body"> {
  signal?: AbortSignal;
  body?: any;
  timeoutMs?: number;
}

async function request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const { signal, body, timeoutMs = 60_000, ...rest } = opts;

  // Combine user-provided signal with a timeout signal
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(new Error("timeout")), timeoutMs);
  if (signal) {
    if (signal.aborted) ctrl.abort(signal.reason);
    else signal.addEventListener("abort", () => ctrl.abort(signal.reason), { once: true });
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...rest,
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
        ...rest.headers,
      },
      body: body !== undefined ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined,
    });

    if (!res.ok) {
      let parsed: any = null;
      try {
        parsed = await res.json();
      } catch {
        /* server returned non-JSON (e.g. HTML 500 page) */
      }
      const msg =
        parsed?.detail ||
        parsed?.error ||
        `API-Fehler: ${res.status} ${res.statusText}`;
      throw new ApiError(msg, res.status, parsed);
    }

    if (res.status === 204) return undefined as unknown as T;
    return res.json();
  } finally {
    clearTimeout(timer);
  }
}

// --- Projekte ---

export interface Projekt {
  id: string;
  name: string;
  auftraggeber?: string | null;
  adresse?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export const projekte = {
  list: (signal?: AbortSignal) => request<Projekt[]>("/projekte/", { signal }),
  create: (data: { name: string; auftraggeber?: string }, signal?: AbortSignal) =>
    request<Projekt>("/projekte/", { method: "POST", body: data, signal }),
  get: (id: string, signal?: AbortSignal) =>
    request<Projekt>(`/projekte/${id}`, { signal }),
  update: (id: string, data: Partial<Projekt>, signal?: AbortSignal) =>
    request<Projekt>(`/projekte/${id}`, { method: "PATCH", body: data, signal }),
  delete: (id: string, signal?: AbortSignal) =>
    request<void>(`/projekte/${id}`, { method: "DELETE", signal }),
  pipeline: (signal?: AbortSignal) =>
    request<Record<string, Projekt[]>>("/projekte/pipeline", { signal }),
};

// --- Bauplan-Analyse ---

export const bauplan = {
  upload: async (file: File, signal?: AbortSignal) => {
    const formData = new FormData();
    formData.append("file", file);

    const ctrl = new AbortController();
    if (signal) {
      if (signal.aborted) ctrl.abort(signal.reason);
      else signal.addEventListener("abort", () => ctrl.abort(signal.reason), { once: true });
    }

    const res = await fetch(`${API_BASE}/bauplan/upload`, {
      method: "POST",
      body: formData,
      signal: ctrl.signal,
      // No Content-Type header — browser sets multipart boundary
    });

    if (!res.ok) {
      let parsed: any = null;
      try {
        parsed = await res.json();
      } catch {}
      throw new ApiError(
        parsed?.detail || parsed?.error || `Upload fehlgeschlagen (${res.status})`,
        res.status,
        parsed,
      );
    }
    return res.json();
  },

  status: (jobId: string, signal?: AbortSignal) =>
    request<any>(`/bauplan/${jobId}/status`, { signal }),
  result: (jobId: string, signal?: AbortSignal) =>
    request<any>(`/bauplan/${jobId}/result`, { signal }),
  patchResult: (jobId: string, data: any, signal?: AbortSignal) =>
    request<any>(`/bauplan/${jobId}/result`, { method: "PATCH", body: data, signal }),
  kalkulation: (jobId: string, signal?: AbortSignal) =>
    request<any>(`/bauplan/${jobId}/kalkulation`, { signal }),
};

// --- Stats ---

export const stats = {
  dashboard: (signal?: AbortSignal) =>
    request<any>("/stats/dashboard", { signal }),
};

// --- Preislisten ---

export const preislisten = {
  list: (signal?: AbortSignal) => request<any[]>("/preislisten/", { signal }),
  get: (id: string, signal?: AbortSignal) =>
    request<any>(`/preislisten/${id}`, { signal }),
  delete: (id: string, signal?: AbortSignal) =>
    request<void>(`/preislisten/${id}`, { method: "DELETE", signal }),
  search: (query: string, signal?: AbortSignal) =>
    request<any>(
      `/preislisten/vergleich/suche?q=${encodeURIComponent(query)}`,
      { signal },
    ),
};

/**
 * Helper to detect user-cancelled / unmount-triggered aborts,
 * which callers typically want to silently ignore.
 */
export function isAbortError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const name = (err as any).name;
  return name === "AbortError" || name === "CanceledError";
}
