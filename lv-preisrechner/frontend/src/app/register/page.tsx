"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, setToken } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    firma: "",
    vorname: "",
    nachname: "",
    email: "",
    password: "",
  });
  const [busy, setBusy] = useState(false);

  function update<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api<{ access_token: string; firma: string }>("/auth/register", {
        method: "POST",
        body: form,
      });
      setToken(res.access_token);
      toast.success(`Willkommen, ${res.firma}! Jetzt kann's losgehen.`);
      router.replace("/dashboard");
    } catch (err: any) {
      toast.error(err?.detail || "Registrierung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center bg-gradient-to-b from-bauplan-50 to-white px-6 py-10">
      <div className="w-full max-w-md">
        <Link href="/" className="inline-flex items-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-lg bg-bauplan-600 text-white grid place-items-center font-bold">
            LC
          </div>
          <span className="font-semibold text-slate-900">LV-Preisrechner</span>
        </Link>
        <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-8">
          <h1 className="text-2xl font-bold text-slate-900">Kostenlos starten</h1>
          <p className="text-sm text-slate-600 mt-1">
            In weniger als einer Minute einsatzbereit.
          </p>
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <Label htmlFor="firma">Firma</Label>
              <Input
                id="firma"
                required
                placeholder="Trockenbau Mustermann GmbH"
                value={form.firma}
                onChange={(e) => update("firma", e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="vorname">Vorname</Label>
                <Input
                  id="vorname"
                  value={form.vorname}
                  onChange={(e) => update("vorname", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="nachname">Nachname</Label>
                <Input
                  id="nachname"
                  value={form.nachname}
                  onChange={(e) => update("nachname", e.target.value)}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="email">E-Mail</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="password">Passwort</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
              />
              <p className="text-xs text-slate-500 mt-1">Mindestens 8 Zeichen.</p>
            </div>
            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? "Wird erstellt…" : "Account erstellen"}
            </Button>
          </form>
          <div className="mt-6 text-sm text-center text-slate-600">
            Schon registriert?{" "}
            <Link href="/login" className="text-bauplan-600 font-medium">
              Zum Login
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
