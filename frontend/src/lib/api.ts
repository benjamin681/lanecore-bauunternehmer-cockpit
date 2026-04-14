/**
 * API client for LaneCore Backend.
 * Uses Next.js rewrites (/api/* → backend) to avoid CORS.
 */

const API_BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    throw new Error(body.error || body.detail || `API-Fehler: ${res.status}`);
  }

  return res.json();
}

// --- Projekte ---

export const projekte = {
  list: () => request<any[]>("/projekte/"),
  create: (data: { name: string; auftraggeber?: string }) =>
    request<any>("/projekte/", { method: "POST", body: JSON.stringify(data) }),
  get: (id: string) => request<any>(`/projekte/${id}`),
};

// --- Bauplan-Analyse ---

export const bauplan = {
  upload: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/bauplan/upload`, {
      method: "POST",
      body: formData,
      // No Content-Type header — browser sets multipart boundary
    });

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || body?.error || `Upload fehlgeschlagen (${res.status})`);
    }
    return res.json();
  },

  status: (jobId: string) => request<any>(`/bauplan/${jobId}/status`),
  result: (jobId: string) => request<any>(`/bauplan/${jobId}/result`),
};
