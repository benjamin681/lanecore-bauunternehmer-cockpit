"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, getPricingReadiness, User } from "@/lib/api";
import {
  isValidBIC,
  isValidIBAN,
  isValidVATID,
  tenantApi,
  TenantProfile,
  TenantProfileUpdate,
} from "@/lib/tenantApi";

type Form = {
  firma: string;
  stundensatz_eur: number;
  bgk_prozent: number;
  agk_prozent: number;
  wg_prozent: number;
};

export default function EinstellungenPage() {
  const [user, setUser] = useState<User | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const [togglingFlag, setTogglingFlag] = useState(false);

  useEffect(() => {
    api<User>("/auth/me").then((u) => {
      setUser(u);
      setForm({
        firma: u.firma,
        stundensatz_eur: u.stundensatz_eur,
        bgk_prozent: u.bgk_prozent,
        agk_prozent: u.agk_prozent,
        wg_prozent: u.wg_prozent,
      });
    });
  }, []);

  function update<K extends keyof Form>(k: K, v: Form[K]) {
    setForm((f) => (f ? { ...f, [k]: v } : f));
  }

  async function toggleNewPricing(next: boolean) {
    if (togglingFlag) return;
    setTogglingFlag(true);
    try {
      if (next) {
        // Vorab-Check: Daten vorhanden?
        const r = await getPricingReadiness();
        if (!r.ready_for_new_pricing) {
          toast.error(
            "Keine aktive Lieferanten-Preisliste und kein Preis-Override vorhanden.",
            {
              description:
                "Bitte zuerst eine Preisliste hochladen oder einen Override anlegen.",
              action: {
                label: "Zur Preislisten-Verwaltung",
                onClick: () => {
                  window.location.href = "/dashboard/pricing";
                },
              },
            },
          );
          return;
        }
      }
      const updated = await api<User>("/auth/me/tenant", {
        method: "PATCH",
        body: { use_new_pricing: next },
      });
      setUser(updated);
      toast.success(
        next
          ? "Neue Preis-Engine aktiviert"
          : "Neue Preis-Engine deaktiviert",
      );
    } catch (err: unknown) {
      const detail =
        err instanceof ApiError ? err.detail : "Umschalten fehlgeschlagen";
      toast.error(detail || "Umschalten fehlgeschlagen");
    } finally {
      setTogglingFlag(false);
    }
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    try {
      const updated = await api<User>("/auth/me/tenant", {
        method: "PATCH",
        body: form,
      });
      setUser(updated);
      toast.success("Einstellungen gespeichert");
    } catch (err: any) {
      toast.error(err?.detail || "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  const dirty =
    user &&
    form &&
    (form.firma !== user.firma ||
      form.stundensatz_eur !== user.stundensatz_eur ||
      form.bgk_prozent !== user.bgk_prozent ||
      form.agk_prozent !== user.agk_prozent ||
      form.wg_prozent !== user.wg_prozent);

  const gesamtZuschlag = form
    ? form.bgk_prozent + form.agk_prozent + form.wg_prozent
    : 0;

  return (
    <div className="max-w-3xl space-y-8">
      <SettingsForm
        form={form}
        user={user}
        busy={busy}
        save={save}
        update={update}
        toggleNewPricing={toggleNewPricing}
        togglingFlag={togglingFlag}
        dirty={Boolean(dirty)}
        gesamtZuschlag={gesamtZuschlag}
      />
      <TenantProfileSection />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// B+4.9 — Tenant-Profil mit typisierten Spalten (Briefkopf, Bank, Defaults)
// --------------------------------------------------------------------------- //
function TenantProfileSection() {
  const [profile, setProfile] = useState<TenantProfile | null>(null);
  const [draft, setDraft] = useState<TenantProfileUpdate>({});
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    tenantApi.getProfile().then((p) => {
      setProfile(p);
      setDraft({});
    });
  }, []);

  function setField<K extends keyof TenantProfileUpdate>(
    key: K, value: TenantProfileUpdate[K],
  ) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function effective<K extends keyof TenantProfile>(key: K): TenantProfile[K] | null {
    if (key in draft) return (draft as Record<string, unknown>)[key as string] as TenantProfile[K];
    return profile ? profile[key] : null;
  }

  async function save() {
    if (!profile) return;
    // Clientseitige Validierung
    const errs: Record<string, string> = {};
    const iban = effective("bank_iban");
    const bic = effective("bank_bic");
    const vat = effective("vat_id");
    const country = effective("company_address_country");
    if (iban && typeof iban === "string" && iban.trim() && !isValidIBAN(iban)) {
      errs["bank_iban"] = "IBAN-Format ungültig (Land + 13–32 Zeichen).";
    }
    if (bic && typeof bic === "string" && bic.trim() && !isValidBIC(bic)) {
      errs["bank_bic"] = "BIC muss 8 oder 11 Zeichen haben.";
    }
    if (vat && typeof vat === "string" && vat.trim() && !isValidVATID(vat)) {
      errs["vat_id"] = "USt-IdNr. muss mit Land-Code beginnen (z.B. DE…).";
    }
    if (country && typeof country === "string" && country.length !== 2) {
      errs["company_address_country"] = "ISO-2-Land-Code (z.B. DE).";
    }
    setErrors(errs);
    if (Object.keys(errs).length > 0) {
      toast.error("Bitte Validierungsfehler korrigieren.");
      return;
    }
    setBusy(true);
    try {
      const updated = await tenantApi.updateProfile(draft);
      setProfile(updated);
      setDraft({});
      toast.success("Firmen-Profil gespeichert");
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : "Speichern fehlgeschlagen";
      toast.error(detail || "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  if (!profile) {
    return <div className="text-slate-500">Lade Firmen-Profil…</div>;
  }
  const isDirty = Object.keys(draft).length > 0;

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Firmen-Profil</h2>
        <p className="text-slate-600 mt-1 text-sm">
          Stammdaten für Briefkopf, Bankverbindung und Footer im Angebots-PDF.
        </p>
      </div>

      <div className="rounded-xl bg-white border border-slate-200 p-6 space-y-4">
        <h3 className="font-semibold text-slate-900">Briefkopf</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ProfileText label="Firmenname" value={effective("company_name")}
                       onChange={(v) => setField("company_name", v)} />
          <ProfileText label="Land (ISO-2)" value={effective("company_address_country")}
                       maxLength={2} placeholder="DE"
                       onChange={(v) => setField("company_address_country", v.toUpperCase())}
                       error={errors["company_address_country"]} />
          <ProfileText label="Strasse + Nr." value={effective("company_address_street")}
                       onChange={(v) => setField("company_address_street", v)} />
          <ProfileText label="PLZ" value={effective("company_address_zip")}
                       onChange={(v) => setField("company_address_zip", v)} />
          <ProfileText label="Stadt" value={effective("company_address_city")}
                       onChange={(v) => setField("company_address_city", v)} />
          <ProfileText label="Logo-URL (optional)" value={effective("logo_url")}
                       placeholder="https://…/logo.png"
                       onChange={(v) => setField("logo_url", v)} />
        </div>
      </div>

      <div className="rounded-xl bg-white border border-slate-200 p-6 space-y-4">
        <h3 className="font-semibold text-slate-900">Steuer &amp; Bank</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ProfileText label="Steuernummer" value={effective("tax_id")}
                       onChange={(v) => setField("tax_id", v)} />
          <ProfileText label="USt-IdNr." value={effective("vat_id")}
                       placeholder="DE123456789"
                       onChange={(v) => setField("vat_id", v)}
                       error={errors["vat_id"]} />
          <ProfileText label="IBAN" value={effective("bank_iban")}
                       placeholder="DE12 3456 7890 1234 5678 90"
                       onChange={(v) => setField("bank_iban", v)}
                       error={errors["bank_iban"]} />
          <ProfileText label="BIC" value={effective("bank_bic")}
                       placeholder="MUSTDE12"
                       onChange={(v) => setField("bank_bic", v)}
                       error={errors["bank_bic"]} />
          <div className="md:col-span-2">
            <ProfileText label="Bank-Name" value={effective("bank_name")}
                         onChange={(v) => setField("bank_name", v)} />
          </div>
        </div>
      </div>

      <div className="rounded-xl bg-white border border-slate-200 p-6 space-y-4">
        <h3 className="font-semibold text-slate-900">Vertragsbedingungen</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ProfileNumber label="Zahlungsziel (Tage)"
                         value={effective("default_payment_terms_days") ?? 14}
                         onChange={(v) => setField("default_payment_terms_days", v)} />
          <ProfileNumber label="Angebots-Gültigkeit (Tage)"
                         value={effective("default_offer_validity_days") ?? 30}
                         onChange={(v) => setField("default_offer_validity_days", v)} />
        </div>
        <div>
          <Label>AGB-Text</Label>
          <textarea
            className="w-full rounded-lg bg-white border border-slate-200 p-3 text-sm focus:outline-none focus:border-bauplan-500 focus:ring-2 focus:ring-bauplan-100"
            rows={3}
            value={String(effective("default_agb_text") ?? "")}
            onChange={(e) => setField("default_agb_text", e.target.value)}
          />
        </div>
        <div>
          <Label>Signatur (Footer-Text)</Label>
          <textarea
            className="w-full rounded-lg bg-white border border-slate-200 p-3 text-sm focus:outline-none focus:border-bauplan-500 focus:ring-2 focus:ring-bauplan-100"
            rows={2}
            value={String(effective("signature_text") ?? "")}
            onChange={(e) => setField("signature_text", e.target.value)}
          />
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={save} disabled={!isDirty || busy} variant="primary">
          <Save className="w-4 h-4" />
          {busy ? "Speichere…" : "Firmen-Profil speichern"}
        </Button>
      </div>
    </section>
  );
}

function ProfileText({
  label, value, onChange, placeholder, error, maxLength,
}: {
  label: string;
  value: string | null;
  onChange: (v: string) => void;
  placeholder?: string;
  error?: string;
  maxLength?: number;
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <Input
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
      />
      {error && <p className="text-xs text-danger-600">{error}</p>}
    </div>
  );
}

function ProfileNumber({
  label, value, onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <Input
        type="number" min={1} max={365}
        value={value}
        onChange={(e) => {
          const n = parseInt(e.target.value, 10);
          onChange(Number.isFinite(n) ? n : 0);
        }}
      />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// SettingsForm: existing Kalkulations-Defaults (unveraendert)
// --------------------------------------------------------------------------- //
function SettingsForm({
  form, user, busy, save, update, toggleNewPricing, togglingFlag,
  dirty, gesamtZuschlag,
}: {
  form: Form | null;
  user: User | null;
  busy: boolean;
  save: (e: FormEvent) => Promise<void>;
  update: <K extends keyof Form>(k: K, v: Form[K]) => void;
  toggleNewPricing: (next: boolean) => Promise<void>;
  togglingFlag: boolean;
  dirty: boolean;
  gesamtZuschlag: number;
}) {
  return (
    <form onSubmit={save} className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Einstellungen</h1>
        <p className="text-slate-600 mt-1">
          Stundensatz und Zuschläge werden bei jeder Kalkulation verwendet.
        </p>
      </div>

      {form && user && (
        <>
          <div className="rounded-xl bg-white border border-slate-200 p-6 space-y-4">
            <h2 className="font-semibold text-slate-900">Firma</h2>
            <div>
              <Label htmlFor="firma">Firmenname</Label>
              <Input
                id="firma"
                value={form.firma}
                onChange={(e) => update("firma", e.target.value)}
              />
            </div>
            <div>
              <Label>E-Mail</Label>
              <Input value={user.email} readOnly disabled />
              <p className="text-xs text-slate-500 mt-1">
                E-Mail-Änderung aktuell nur per Support.
              </p>
            </div>
          </div>

          <div className="rounded-xl bg-white border border-slate-200 p-6 space-y-4">
            <h2 className="font-semibold text-slate-900">Kalkulations-Defaults</h2>
            <div className="grid grid-cols-2 gap-4">
              <NumberField
                label="Stundensatz (€/h)"
                value={form.stundensatz_eur}
                step={0.5}
                onChange={(v) => update("stundensatz_eur", v)}
              />
              <NumberField
                label="BGK (%)"
                value={form.bgk_prozent}
                step={0.5}
                onChange={(v) => update("bgk_prozent", v)}
              />
              <NumberField
                label="AGK (%)"
                value={form.agk_prozent}
                step={0.5}
                onChange={(v) => update("agk_prozent", v)}
              />
              <NumberField
                label="Wagnis & Gewinn (%)"
                value={form.wg_prozent}
                step={0.5}
                onChange={(v) => update("wg_prozent", v)}
              />
            </div>
            <p className="text-xs text-slate-500">
              Gesamt-Zuschlag auf (Material + Lohn):{" "}
              <strong className="text-slate-900">{gesamtZuschlag.toFixed(1)} %</strong>
            </p>
          </div>

          <div className="rounded-xl bg-white border border-slate-200 p-6 space-y-3">
            <h2 className="font-semibold text-slate-900">Preis-Engine</h2>
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-300 text-bauplan-600 focus:ring-bauplan-500"
                checked={user.use_new_pricing}
                disabled={togglingFlag}
                onChange={(e) => toggleNewPricing(e.target.checked)}
              />
              <span className="text-sm">
                <span className="font-medium text-slate-900">
                  Neue Preis-Engine verwenden (Lieferanten-Preislisten)
                </span>
                <span className="block text-slate-500 mt-0.5">
                  Aktiviert das neue Matching gegen importierte Lieferanten-
                  Preislisten. Ohne aktive Preisliste oder Preis-Override kann
                  die Engine nicht aktiviert werden.
                </span>
                <Link
                  href="/dashboard/pricing"
                  className="text-bauplan-600 hover:text-bauplan-700 text-xs inline-block mt-1"
                >
                  Zur Preislisten-Verwaltung →
                </Link>
              </span>
            </label>
          </div>

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={busy || !dirty}>
              <Save className="w-4 h-4" />
              {busy ? "Speichert…" : "Speichern"}
            </Button>
            {dirty && (
              <span className="text-sm text-warning-600">Ungespeicherte Änderungen</span>
            )}
          </div>

          <div className="rounded-xl bg-bauplan-50 border border-bauplan-100 p-4 text-sm text-slate-700 leading-relaxed">
            <strong>Achtung:</strong> Änderungen wirken nur auf{" "}
            <em>neue Kalkulationen</em>. Bereits kalkulierte LVs behalten ihre alten Werte,
            bis Sie sie erneut kalkulieren lassen.
          </div>
        </>
      )}
    </form>
  );
}

function NumberField({
  label,
  value,
  step = 0.5,
  onChange,
}: {
  label: string;
  value: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <Input
        type="number"
        step={step}
        min={0}
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => {
          const v = parseFloat(e.target.value.replace(",", "."));
          onChange(Number.isFinite(v) ? v : 0);
        }}
      />
    </div>
  );
}
