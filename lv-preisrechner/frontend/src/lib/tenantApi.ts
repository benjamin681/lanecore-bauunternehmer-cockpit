"use client";

/**
 * API-Client fuer den B+4.9 Vertriebs-Workflow:
 *   - Tenant-Profil (typisierte Spalten)
 *   - Customer-CRUD
 *   - Project-CRUD
 *
 * Schema-Quelle: backend/app/schemas/tenant.py
 */

import { api } from "@/lib/api";

// --------------------------------------------------------------------------- //
// Tenant-Profil
// --------------------------------------------------------------------------- //
export type TenantProfile = {
  id: string;
  name: string;
  company_name: string | null;
  company_address_street: string | null;
  company_address_zip: string | null;
  company_address_city: string | null;
  company_address_country: string;
  tax_id: string | null;
  vat_id: string | null;
  bank_iban: string | null;
  bank_bic: string | null;
  bank_name: string | null;
  logo_url: string | null;
  default_payment_terms_days: number;
  default_offer_validity_days: number;
  default_agb_text: string | null;
  signature_text: string | null;
  use_new_pricing: boolean;
  stundensatz_eur: number;
  bgk_prozent: number;
  agk_prozent: number;
  wg_prozent: number;
  created_at: string;
};

export type TenantProfileUpdate = Partial<{
  company_name: string | null;
  company_address_street: string | null;
  company_address_zip: string | null;
  company_address_city: string | null;
  company_address_country: string | null;
  tax_id: string | null;
  vat_id: string | null;
  bank_iban: string | null;
  bank_bic: string | null;
  bank_name: string | null;
  logo_url: string | null;
  default_payment_terms_days: number | null;
  default_offer_validity_days: number | null;
  default_agb_text: string | null;
  signature_text: string | null;
}>;

// --------------------------------------------------------------------------- //
// Customer
// --------------------------------------------------------------------------- //
export type Customer = {
  id: string;
  tenant_id: string;
  name: string;
  contact_person: string | null;
  address_street: string | null;
  address_zip: string | null;
  address_city: string | null;
  address_country: string;
  email: string | null;
  phone: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerCreate = {
  name: string;
  contact_person?: string | null;
  address_street?: string | null;
  address_zip?: string | null;
  address_city?: string | null;
  address_country?: string | null;
  email?: string | null;
  phone?: string | null;
  notes?: string | null;
};

// --------------------------------------------------------------------------- //
// Project
// --------------------------------------------------------------------------- //
export type ProjectStatus = "draft" | "active" | "completed" | "cancelled";

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "Entwurf",
  active: "Aktiv",
  completed: "Abgeschlossen",
  cancelled: "Storniert",
};

export type Project = {
  id: string;
  tenant_id: string;
  customer_id: string;
  name: string;
  address_street: string | null;
  address_zip: string | null;
  address_city: string | null;
  status: ProjectStatus | string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectCreate = {
  customer_id: string;
  name: string;
  status?: ProjectStatus;
  notes?: string | null;
};

export type ProjectLV = {
  id: string;
  projekt_name: string;
  auftraggeber: string;
  status: string;
  angebotssumme_netto: number;
  positionen_gesamt: number;
  created_at: string | null;
};

// --------------------------------------------------------------------------- //
// API
// --------------------------------------------------------------------------- //
export const tenantApi = {
  getProfile: () => api<TenantProfile>("/tenant/profile"),
  updateProfile: (body: TenantProfileUpdate) =>
    api<TenantProfile>("/tenant/profile", { method: "PATCH", body }),
};

export const customersApi = {
  list: (search?: string) =>
    api<Customer[]>(
      `/customers${search ? `?search=${encodeURIComponent(search)}` : ""}`,
    ),
  get: (id: string) => api<Customer>(`/customers/${id}`),
  create: (body: CustomerCreate) =>
    api<Customer>("/customers", { method: "POST", body }),
  update: (id: string, body: Partial<CustomerCreate>) =>
    api<Customer>(`/customers/${id}`, { method: "PATCH", body }),
  delete: (id: string) =>
    api<void>(`/customers/${id}`, { method: "DELETE" }),
};

export const projectsApi = {
  list: (params: { customer_id?: string; status?: string } = {}) => {
    const qs: string[] = [];
    if (params.customer_id)
      qs.push(`customer_id=${encodeURIComponent(params.customer_id)}`);
    if (params.status) qs.push(`status=${encodeURIComponent(params.status)}`);
    return api<Project[]>(`/projects${qs.length ? `?${qs.join("&")}` : ""}`);
  },
  get: (id: string) => api<Project>(`/projects/${id}`),
  create: (body: ProjectCreate) =>
    api<Project>("/projects", { method: "POST", body }),
  update: (id: string, body: Partial<ProjectCreate>) =>
    api<Project>(`/projects/${id}`, { method: "PATCH", body }),
  delete: (id: string) =>
    api<void>(`/projects/${id}`, { method: "DELETE" }),
  listLvs: (id: string) =>
    api<ProjectLV[]>(`/projects/${id}/lvs`),
};

// --------------------------------------------------------------------------- //
// Validation-Helpers (clientseitig, nicht-strict)
// --------------------------------------------------------------------------- //
export function isValidIBAN(iban: string): boolean {
  // Lockere Pruefung: Whitespace ignorieren, dann 15-34 alphanumerisch.
  const stripped = iban.replace(/\s+/g, "").toUpperCase();
  return /^[A-Z]{2}[0-9A-Z]{13,32}$/.test(stripped);
}

export function isValidBIC(bic: string): boolean {
  // 8 oder 11 Zeichen, Format LLLLCCAA[BBB]
  const stripped = bic.trim().toUpperCase();
  return /^[A-Z]{4}[A-Z]{2}[0-9A-Z]{2}([0-9A-Z]{3})?$/.test(stripped);
}

export function isValidVATID(vat: string): boolean {
  // Sehr lockere Pruefung — Format variiert pro Land. Mindestens
  // 2 Buchstaben (Country) gefolgt von Ziffern/Buchstaben.
  const stripped = vat.replace(/\s+/g, "").toUpperCase();
  return /^[A-Z]{2}[0-9A-Z]{2,15}$/.test(stripped);
}
