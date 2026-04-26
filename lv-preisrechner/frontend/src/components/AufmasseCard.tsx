"use client";

/**
 * B+4.12 — Aufmaß-Karte auf der LV-Detail-Seite.
 *
 * Listet alle Aufmaße eines LVs mit Status, Datum und Quick-Link.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { Ruler } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  AUFMASS_STATUS_LABELS,
  Aufmass,
  AufmassStatus,
  aufmassApi,
} from "@/lib/tenantApi";
import { fmtDate } from "@/lib/format";

export function AufmasseCard({ lvId }: { lvId: string }) {
  const [items, setItems] = useState<Aufmass[] | null>(null);

  useEffect(() => {
    aufmassApi.listForLv(lvId).then(setItems).catch(() => setItems([]));
  }, [lvId]);

  // Wenn noch nicht geladen oder keine Aufmaße: nicht rendern, um die
  // Seite ruhig zu halten. Anlage erfolgt aus der OffersCard heraus.
  if (!items || items.length === 0) return null;

  return (
    <section className="rounded-xl bg-white border border-slate-200 p-5">
      <header className="flex items-center gap-2 mb-3">
        <Ruler className="w-4 h-4 text-slate-500" />
        <h2 className="text-lg font-semibold text-slate-900">Aufmaße</h2>
        <span className="text-sm text-slate-400">({items.length})</span>
      </header>
      <ul className="space-y-2">
        {items.map((a) => (
          <li
            key={a.id}
            className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 p-3 hover:border-bauplan-300"
          >
            <div className="flex items-center gap-3 min-w-0">
              <Link
                href={`/dashboard/aufmasse/${a.id}`}
                className="font-mono font-semibold text-slate-900 hover:text-bauplan-600"
              >
                {a.aufmass_number}
              </Link>
              <StatusBadge status={a.status} />
              {a.finalized_at && (
                <span className="text-xs text-slate-500">
                  Abgeschlossen: {fmtDate(a.finalized_at)}
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500 shrink-0">
              Erstellt: {fmtDate(a.created_at)}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant: "info" | "success" | "warning" | "default" =
    status === "in_progress"
      ? "info"
      : status === "finalized"
        ? "success"
        : status === "cancelled"
          ? "warning"
          : "default";
  return (
    <Badge variant={variant}>
      {AUFMASS_STATUS_LABELS[status as AufmassStatus] ?? status}
    </Badge>
  );
}
