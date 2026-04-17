"use client";

import { useEffect, useState } from "react";

interface SubscriptionData {
  plan: string;
  status: string;
  is_active: boolean;
  trial_ends_at?: string | null;
  usage: {
    analysen_used: number;
    analysen_limit: number | null;
  };
}

const PLAN_LABELS: Record<string, string> = {
  trial: "Testversion",
  starter: "Starter",
  business: "Business",
  enterprise: "Enterprise",
};

export function SubscriptionBanner() {
  const [sub, setSub] = useState<SubscriptionData | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch("/api/v1/subscription/me", { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setSub(d); })
      .catch(() => {});
    return () => ctrl.abort();
  }, []);

  if (!sub) return null;

  const { plan, is_active, trial_ends_at, usage } = sub;
  const daysLeft = trial_ends_at
    ? Math.max(0, Math.ceil((new Date(trial_ends_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
    : null;

  // Only show banner for trial/inactive or near quota
  const nearQuota =
    usage.analysen_limit !== null && usage.analysen_used >= usage.analysen_limit * 0.8;
  const shouldShow = plan === "trial" || !is_active || nearQuota;

  if (!shouldShow) return null;

  let message: React.ReactNode;
  let bgClass = "bg-blue-50 border-blue-200 text-blue-900";

  if (!is_active) {
    bgClass = "bg-red-50 border-red-200 text-red-900";
    message = (
      <>
        <strong>Abonnement abgelaufen.</strong> Bitte aktualisieren Sie Ihren Plan um das System weiter zu nutzen.
      </>
    );
  } else if (plan === "trial" && daysLeft !== null) {
    if (daysLeft <= 3) {
      bgClass = "bg-orange-50 border-orange-200 text-orange-900";
    }
    const quotaTxt =
      usage.analysen_limit !== null
        ? ` · ${usage.analysen_used}/${usage.analysen_limit} Analysen genutzt`
        : "";
    message = (
      <>
        <strong>Testversion</strong> — noch {daysLeft} Tag{daysLeft !== 1 ? "e" : ""}{quotaTxt}
      </>
    );
  } else if (nearQuota) {
    bgClass = "bg-orange-50 border-orange-200 text-orange-900";
    message = (
      <>
        <strong>Fast am Limit:</strong> {usage.analysen_used}/{usage.analysen_limit} Analysen diesen Monat genutzt. Bitte Plan erweitern.
      </>
    );
  }

  return (
    <div className={`rounded-lg border p-3 text-sm ${bgClass} flex items-start justify-between gap-3`}>
      <span>{message}</span>
      <a
        href="/dashboard/abo"
        className="underline font-medium whitespace-nowrap hover:opacity-80"
      >
        Plan ansehen
      </a>
    </div>
  );
}
