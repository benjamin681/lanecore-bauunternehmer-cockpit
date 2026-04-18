"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, FileStack, FolderOpen, Plus, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, LV, PriceList } from "@/lib/api";

export default function DashboardHome() {
  const [lvs, setLvs] = useState<LV[]>([]);
  const [pls, setPls] = useState<PriceList[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      api<LV[]>("/lvs"),
      api<PriceList[]>("/price-lists"),
    ])
      .then(([lvData, plData]) => {
        if (!active) return;
        setLvs(lvData);
        setPls(plData);
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const aktivePl = pls.find((p) => p.aktiv);
  const summe = lvs.reduce((s, l) => s + l.angebotssumme_netto, 0);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Übersicht</h1>
          <p className="text-slate-600 mt-1">Ihre letzten Leistungsverzeichnisse und Preislisten</p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/preislisten/neu">
            <Button variant="secondary">
              <Plus className="w-4 h-4" />
              Preisliste
            </Button>
          </Link>
          <Link href="/dashboard/lvs/neu">
            <Button>
              <Plus className="w-4 h-4" />
              Neues LV
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Aktive Preisliste"
          value={aktivePl ? `${aktivePl.haendler} — ${aktivePl.stand_monat || "o. D."}` : "—"}
          hint={aktivePl ? `${aktivePl.eintraege_gesamt} Einträge` : "Noch keine Liste aktiviert"}
          icon={<FileStack className="w-5 h-5 text-bauplan-600" />}
        />
        <StatCard
          label="LVs gesamt"
          value={lvs.length.toString()}
          hint={`${lvs.filter((l) => l.status === "exported").length} exportiert`}
          icon={<FolderOpen className="w-5 h-5 text-success-500" />}
        />
        <StatCard
          label="Gesamtvolumen netto"
          value={fmtEur(summe)}
          hint="Summe aller kalkulierten LVs"
          icon={<TrendingUp className="w-5 h-5 text-accent-500" />}
        />
      </div>

      {/* Onboarding-Hinweis */}
      {!loading && pls.length === 0 && (
        <div className="rounded-xl bg-bauplan-50 border border-bauplan-100 p-6 flex items-start gap-4">
          <div className="w-10 h-10 grid place-items-center rounded-lg bg-bauplan-600 text-white font-bold">
            1
          </div>
          <div className="flex-1">
            <div className="font-semibold text-slate-900">Zuerst: Ihre Preisliste hochladen</div>
            <div className="text-sm text-slate-600 mt-1">
              Damit wir Ihre echten Einkaufspreise beim Matching verwenden — jeder Betrieb
              verhandelt andere Konditionen.
            </div>
          </div>
          <Link href="/dashboard/preislisten/neu">
            <Button>
              Preisliste hochladen <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      )}

      {!loading && pls.length > 0 && lvs.length === 0 && (
        <div className="rounded-xl bg-accent-500/5 border border-accent-500/20 p-6 flex items-start gap-4">
          <div className="w-10 h-10 grid place-items-center rounded-lg bg-accent-500 text-white font-bold">
            2
          </div>
          <div className="flex-1">
            <div className="font-semibold text-slate-900">
              Jetzt: Ihr erstes LV hochladen
            </div>
            <div className="text-sm text-slate-600 mt-1">
              Wir lesen jede Position aus, matchen sie gegen Ihre Preisliste und geben Ihnen ein
              kalkuliertes PDF zurück.
            </div>
          </div>
          <Link href="/dashboard/lvs/neu">
            <Button variant="accent">
              LV hochladen <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      )}

      {/* Letzte LVs */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Letzte LVs</h2>
        {lvs.length === 0 ? (
          <EmptyCard text="Noch keine LVs hochgeladen." />
        ) : (
          <div className="space-y-2">
            {lvs.slice(0, 6).map((lv) => (
              <Link
                key={lv.id}
                href={`/dashboard/lvs/${lv.id}`}
                className="flex items-center justify-between p-4 rounded-xl bg-white border border-slate-200 hover:border-bauplan-300 hover:shadow-sm transition-all"
              >
                <div className="min-w-0">
                  <div className="font-medium text-slate-900 truncate">
                    {lv.projekt_name || lv.original_dateiname || "Unbenanntes LV"}
                  </div>
                  <div className="text-sm text-slate-500 mt-0.5 flex items-center gap-2">
                    <StatusBadge status={lv.status} />
                    <span>· {lv.positionen_gesamt} Positionen</span>
                    {lv.positionen_unsicher > 0 && (
                      <Badge variant="warning">{lv.positionen_unsicher} unsicher</Badge>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-slate-900">
                    {fmtEur(lv.angebotssumme_netto)}
                  </div>
                  <div className="text-xs text-slate-500">
                    {new Date(lv.created_at).toLocaleDateString("de-DE")}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-white border border-slate-200 p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-600">{label}</div>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
    </div>
  );
}

function EmptyCard({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
      {text}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; variant: "default" | "success" | "warning" | "info" }> =
    {
      uploaded: { label: "Hochgeladen", variant: "info" },
      extracting: { label: "Wird extrahiert…", variant: "info" },
      review_needed: { label: "Prüfung", variant: "warning" },
      calculated: { label: "Kalkuliert", variant: "success" },
      exported: { label: "Exportiert", variant: "success" },
      error: { label: "Fehler", variant: "warning" },
    };
  const meta = map[status] || { label: status, variant: "default" as const };
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}

export function fmtEur(n: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(n);
}
