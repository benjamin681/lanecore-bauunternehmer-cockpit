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

// --------------------------------------------------------------------------- //
// Offer (B+4.11)
// --------------------------------------------------------------------------- //
export type OfferStatus =
  | "draft"
  | "sent"
  | "accepted"
  | "rejected"
  | "negotiating"
  | "expired";

export const OFFER_STATUS_LABELS: Record<OfferStatus, string> = {
  draft: "Entwurf",
  sent: "Versendet",
  accepted: "Angenommen",
  rejected: "Abgelehnt",
  negotiating: "In Verhandlung",
  expired: "Abgelaufen",
};

export type OfferPdfFormat = "eigenes_layout" | "original_lv_filled";

export const OFFER_PDF_FORMAT_LABELS: Record<OfferPdfFormat, string> = {
  eigenes_layout: "Eigenes Angebots-Layout",
  original_lv_filled: "Original-LV mit Preisen ausgefüllt",
};

export type Offer = {
  id: string;
  tenant_id: string;
  lv_id: string;
  project_id: string | null;
  offer_number: string;
  status: OfferStatus | string;
  offer_date: string;
  sent_date: string | null;
  accepted_date: string | null;
  rejected_date: string | null;
  valid_until: string | null;
  betrag_netto: number;
  betrag_brutto: number;
  position_count: number;
  pdf_format: OfferPdfFormat | string;
  internal_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type OfferStatusChange = {
  id: string;
  old_status: string | null;
  new_status: string;
  changed_at: string;
  changed_by: string | null;
  reason: string | null;
};

export type OfferDetail = Offer & {
  status_history: OfferStatusChange[];
};

export type OfferCreate = {
  pdf_format?: OfferPdfFormat;
  internal_notes?: string | null;
};

export type OfferStatusUpdate = {
  status: OfferStatus;
  reason?: string | null;
  on_date?: string | null;
};

export type OfferLvSummary = {
  offer_count: number;
  latest_status: string;
  latest_offer_number: string;
  latest_valid_until: string | null;
  expiring_soon: boolean;
};

export const offersApi = {
  listForLv: (lvId: string) => api<Offer[]>(`/lvs/${lvId}/offers`),
  createForLv: (lvId: string, body: OfferCreate) =>
    api<Offer>(`/lvs/${lvId}/offers`, { method: "POST", body }),
  get: (offerId: string) => api<OfferDetail>(`/offers/${offerId}`),
  updateStatus: (offerId: string, body: OfferStatusUpdate) =>
    api<OfferDetail>(`/offers/${offerId}/status`, { method: "PATCH", body }),
  pdfUrl: (offerId: string, inline = false) =>
    `/api/v1/offers/${offerId}/pdf${inline ? "?inline=true" : ""}`,
  lvSummary: () =>
    api<Record<string, OfferLvSummary>>(`/offers/lv-summary`),
};

// --------------------------------------------------------------------------- //
// Aufmaß (B+4.12)
// --------------------------------------------------------------------------- //
export type AufmassStatus = "in_progress" | "finalized" | "cancelled";

export const AUFMASS_STATUS_LABELS: Record<AufmassStatus, string> = {
  in_progress: "In Erfassung",
  finalized: "Abgeschlossen",
  cancelled: "Storniert",
};

export type AufmassPosition = {
  id: string;
  aufmass_id: string;
  lv_position_id: string;
  oz: string;
  kurztext: string;
  einheit: string;
  lv_menge: number;
  ep: number;
  gemessene_menge: number;
  notes: string | null;
  gp_lv_snapshot: number;
  gp_aufmass: number;
  created_at: string;
  updated_at: string;
};

export type Aufmass = {
  id: string;
  tenant_id: string;
  lv_id: string;
  source_offer_id: string;
  aufmass_number: string;
  status: AufmassStatus | string;
  finalized_at: string | null;
  finalized_by: string | null;
  internal_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type AufmassDetail = Aufmass & {
  positions: AufmassPosition[];
};

export type AufmassGroupSummary = {
  group: string;
  lv_netto: number;
  aufmass_netto: number;
  diff_netto: number;
  position_count: number;
};

export type AufmassSummary = {
  lv_total_netto: number;
  aufmass_total_netto: number;
  diff_netto: number;
  diff_brutto: number;
  diff_pct: number | null;
  position_count: number;
  by_group: AufmassGroupSummary[];
};

export type AufmassPositionUpdate = {
  gemessene_menge?: number;
  notes?: string | null;
};

export const aufmassApi = {
  createFromOffer: (offerId: string, body: { internal_notes?: string | null } = {}) =>
    api<AufmassDetail>(`/offers/${offerId}/aufmass`, { method: "POST", body }),
  listForLv: (lvId: string) => api<Aufmass[]>(`/lvs/${lvId}/aufmasse`),
  get: (id: string) => api<AufmassDetail>(`/aufmasse/${id}`),
  patchPosition: (id: string, posId: string, body: AufmassPositionUpdate) =>
    api<AufmassPosition>(`/aufmasse/${id}/positions/${posId}`, {
      method: "PATCH",
      body,
    }),
  finalize: (id: string) =>
    api<AufmassDetail>(`/aufmasse/${id}/finalize`, { method: "POST" }),
  summary: (id: string) => api<AufmassSummary>(`/aufmasse/${id}/summary`),
  createFinalOffer: (id: string) =>
    api<Offer>(`/aufmasse/${id}/create-final-offer`, { method: "POST" }),
  pdfUrl: (id: string, inline = false) =>
    `/api/v1/aufmasse/${id}/pdf${inline ? "?inline=true" : ""}`,
};

// --------------------------------------------------------------------------- //
// Invoice + Dunning + Finance (B+4.13)
// --------------------------------------------------------------------------- //
export type InvoiceStatus =
  | "draft"
  | "sent"
  | "paid"
  | "partially_paid"
  | "overdue"
  | "cancelled";

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "Entwurf",
  sent: "Versendet",
  paid: "Bezahlt",
  partially_paid: "Teilweise bezahlt",
  overdue: "Überfällig",
  cancelled: "Storniert",
};

export type InvoiceType = "schlussrechnung" | "abschlagsrechnung";

export type InvoiceStatusChange = {
  id: string;
  old_status: string | null;
  new_status: string;
  changed_at: string;
  changed_by: string | null;
  reason: string | null;
};

export type Dunning = {
  id: string;
  tenant_id: string;
  invoice_id: string;
  dunning_level: number;
  dunning_date: string;
  due_date: string;
  mahngebuehr_betrag: number;
  mahnzinsen_betrag: number;
  status: string;
  internal_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type Invoice = {
  id: string;
  tenant_id: string;
  lv_id: string;
  source_offer_id: string;
  source_aufmass_id: string | null;
  invoice_number: string;
  invoice_type: string;
  status: InvoiceStatus | string;
  invoice_date: string;
  sent_date: string | null;
  due_date: string | null;
  paid_date: string | null;
  paid_amount: number;
  betrag_netto: number;
  betrag_ust: number;
  betrag_brutto: number;
  position_count: number;
  internal_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type InvoiceDetail = Invoice & {
  status_history: InvoiceStatusChange[];
  dunnings: Dunning[];
};

export type InvoiceCreate = {
  invoice_type?: InvoiceType;
  internal_notes?: string | null;
};

export type PaymentCreate = {
  amount: number;
  payment_date?: string | null;
  note?: string | null;
};

export type InvoiceStatusUpdate = {
  status: InvoiceStatus;
  reason?: string | null;
  on_date?: string | null;
};

export type FinanceOverview = {
  offene_rechnungen_count: number;
  offene_summe_brutto: number;
  ueberfaellige_count: number;
  ueberfaellige_summe_brutto: number;
  gezahlte_summe_jahr_aktuell: number;
  year: number;
};

export type OverdueInvoiceRow = {
  id: string;
  invoice_number: string;
  betrag_brutto: number;
  paid_amount: number;
  open_amount: number;
  due_date: string | null;
  days_overdue: number | null;
  highest_dunning_level: number;
  next_dunning_due: string | null;
  lv_id: string;
};

export type EmailDraftOut = {
  mailto: string;
  subject: string;
  body: string;
  to: string | null;
};

export const invoicesApi = {
  createFromOffer: (offerId: string, body: InvoiceCreate = {}) =>
    api<InvoiceDetail>(`/offers/${offerId}/invoice`, { method: "POST", body }),
  listForLv: (lvId: string) => api<Invoice[]>(`/lvs/${lvId}/invoices`),
  get: (id: string) => api<InvoiceDetail>(`/invoices/${id}`),
  updateStatus: (id: string, body: InvoiceStatusUpdate) =>
    api<InvoiceDetail>(`/invoices/${id}/status`, { method: "PATCH", body }),
  recordPayment: (id: string, body: PaymentCreate) =>
    api<InvoiceDetail>(`/invoices/${id}/payments`, { method: "POST", body }),
  pdfUrl: (id: string, inline = false) =>
    `/api/v1/invoices/${id}/pdf${inline ? "?inline=true" : ""}`,
  createDunning: (id: string, body: { internal_notes?: string | null } = {}) =>
    api<Dunning>(`/invoices/${id}/dunnings`, { method: "POST", body }),
  dunningPdfUrl: (invoiceId: string, dunningId: string, inline = false) =>
    `/api/v1/invoices/${invoiceId}/dunnings/${dunningId}/pdf${
      inline ? "?inline=true" : ""
    }`,
  emailDraft: (id: string) =>
    api<EmailDraftOut>(`/invoices/${id}/email`, { method: "POST" }),
};

export const financeApi = {
  overview: () => api<FinanceOverview>(`/finance/overview`),
  overdueInvoices: () => api<OverdueInvoiceRow[]>(`/finance/overdue-invoices`),
  checkOverdue: () =>
    api<{ updated: number }>(`/finance/check-overdue`, { method: "POST" }),
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
