"use client";

import { useEffect, useState } from "react";

interface Plan {
  id: string;
  name: string;
  price_monthly: number | null;
  description: string;
  limits: {
    max_analysen_monthly: number | null;
    max_preislisten: number | null;
    max_users: number | null;
    watermark?: boolean;
  };
}

interface Sub {
  plan: string;
  status: string;
  is_active: boolean;
  trial_ends_at?: string | null;
  usage: {
    analysen_used: number;
    analysen_limit: number | null;
  };
}

export default function AboPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<Sub | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      fetch("/api/v1/subscription/plans", { signal: ctrl.signal }).then((r) => r.json()),
      fetch("/api/v1/subscription/me", { signal: ctrl.signal }).then((r) => r.json()),
    ])
      .then(([p, s]) => {
        setPlans(p.plans || []);
        setSub(s);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse h-8 bg-gray-200 rounded w-48" />
        <div className="animate-pulse h-32 bg-gray-200 rounded" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg md:text-2xl font-bold text-gray-900">Abonnement</h2>
        <p className="text-sm text-gray-500 mt-1">
          Ihr aktueller Plan und Nutzung
        </p>
      </div>

      {sub && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Aktueller Plan</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {plans.find((p) => p.id === sub.plan)?.name ?? sub.plan}
              </p>
              {sub.trial_ends_at && (
                <p className="text-sm text-gray-600 mt-1">
                  Testversion läuft ab: {new Date(sub.trial_ends_at).toLocaleDateString("de-DE")}
                </p>
              )}
            </div>
            <span
              className={`px-3 py-1 rounded-full text-xs font-medium ${
                sub.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
              }`}
            >
              {sub.is_active ? "aktiv" : "inaktiv"}
            </span>
          </div>
          {sub.usage.analysen_limit !== null && (
            <div className="mt-6">
              <div className="flex justify-between text-sm text-gray-700 mb-1">
                <span>Analysen diesen Monat</span>
                <span>
                  {sub.usage.analysen_used} / {sub.usage.analysen_limit}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-600 transition-all"
                  style={{
                    width: `${Math.min(
                      100,
                      (sub.usage.analysen_used / sub.usage.analysen_limit) * 100,
                    )}%`,
                  }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Verfügbare Pläne</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map((p) => (
            <div
              key={p.id}
              className={`bg-white rounded-xl border p-6 flex flex-col ${
                p.id === sub?.plan ? "border-primary-500 ring-2 ring-primary-200" : "border-gray-200"
              }`}
            >
              <p className="text-sm font-medium text-gray-500">{p.name}</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {p.price_monthly === null
                  ? "auf Anfrage"
                  : p.price_monthly === 0
                  ? "Gratis"
                  : `${p.price_monthly} €`}
                {p.price_monthly !== null && p.price_monthly > 0 && (
                  <span className="text-sm text-gray-500 font-normal"> / Monat</span>
                )}
              </p>
              <p className="text-sm text-gray-600 mt-2 mb-4">{p.description}</p>
              <ul className="text-sm text-gray-700 space-y-1 flex-1">
                <li>
                  Analysen:{" "}
                  {p.limits.max_analysen_monthly === null
                    ? "unbegrenzt"
                    : `${p.limits.max_analysen_monthly}/Monat`}
                </li>
                <li>
                  Preislisten:{" "}
                  {p.limits.max_preislisten === null
                    ? "unbegrenzt"
                    : p.limits.max_preislisten}
                </li>
                <li>
                  Nutzer:{" "}
                  {p.limits.max_users === null ? "unbegrenzt" : p.limits.max_users}
                </li>
                {p.limits.watermark && (
                  <li className="text-orange-700">PDF mit Wasserzeichen</li>
                )}
              </ul>
              <button
                className={`mt-4 px-4 py-2 rounded-lg font-medium ${
                  p.id === sub?.plan
                    ? "bg-gray-100 text-gray-500 cursor-not-allowed"
                    : "bg-primary-600 text-white hover:bg-primary-700"
                }`}
                disabled={p.id === sub?.plan}
              >
                {p.id === sub?.plan
                  ? "Aktuell aktiv"
                  : p.id === "enterprise"
                  ? "Kontakt aufnehmen"
                  : "Plan wählen"}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900">
        <strong>Stripe-Integration in Vorbereitung.</strong> Für Plan-Wechsel, Rechnung oder
        Enterprise-Angebote kontaktieren Sie uns bitte direkt.
      </div>
    </div>
  );
}
