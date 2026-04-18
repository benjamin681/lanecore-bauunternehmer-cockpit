"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, User } from "@/lib/api";

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
    <form onSubmit={save} className="max-w-2xl space-y-6">
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
