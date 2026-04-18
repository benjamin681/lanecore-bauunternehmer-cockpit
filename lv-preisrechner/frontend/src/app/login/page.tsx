"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api<{ access_token: string; firma: string }>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setToken(res.access_token);
      toast.success(`Willkommen zurück, ${res.firma}`);
      router.replace("/dashboard");
    } catch (err: any) {
      toast.error(err?.detail || "Login fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center bg-gradient-to-b from-bauplan-50 to-white px-6">
      <div className="w-full max-w-md">
        <Link href="/" className="inline-flex items-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-lg bg-bauplan-600 text-white grid place-items-center font-bold">
            LC
          </div>
          <span className="font-semibold text-slate-900">LV-Preisrechner</span>
        </Link>
        <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-8">
          <h1 className="text-2xl font-bold text-slate-900">Anmelden</h1>
          <p className="text-sm text-slate-600 mt-1">
            Willkommen zurück. Laden Sie Ihr nächstes LV hoch.
          </p>
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <Label htmlFor="email">E-Mail</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="password">Passwort</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? "Wird angemeldet…" : "Anmelden"}
            </Button>
          </form>
          <div className="mt-6 text-sm text-center text-slate-600">
            Noch keinen Account?{" "}
            <Link href="/register" className="text-bauplan-600 font-medium">
              Jetzt registrieren
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
