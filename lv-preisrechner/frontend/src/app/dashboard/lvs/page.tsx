"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, LV } from "@/lib/api";
import { OfferLvSummary, offersApi } from "@/lib/tenantApi";
import { OfferStatusBadge } from "@/components/OfferStatusBadge";
import { fmtDate, fmtEur } from "@/lib/format";

export default function LvsPage() {
  const [lvs, setLvs] = useState<LV[]>([]);
  const [offerSummary, setOfferSummary] = useState<Record<string, OfferLvSummary>>({});
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [data, summary] = await Promise.all([
      api<LV[]>("/lvs"),
      offersApi.lvSummary().catch(() => ({}) as Record<string, OfferLvSummary>),
    ]);
    setLvs(data);
    setOfferSummary(summary);
    setLoading(false);
  }
  useEffect(() => {
    load();
  }, []);

  async function remove(id: string) {
    if (!confirm("LV wirklich löschen?")) return;
    try {
      await api(`/lvs/${id}`, { method: "DELETE" });
      toast.success("Gelöscht");
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Löschen fehlgeschlagen");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Leistungsverzeichnisse</h1>
          <p className="text-slate-600 mt-1">Ihre hochgeladenen LVs und deren Kalkulationen.</p>
        </div>
        <Link href="/dashboard/lvs/neu">
          <Button>
            <Plus className="w-4 h-4" /> Neues LV
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="text-slate-500 py-20 text-center">Lade…</div>
      ) : lvs.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-12 text-center">
          <div className="text-slate-900 font-medium">Noch kein LV hochgeladen</div>
          <p className="text-sm text-slate-600 mt-1 mb-6">
            Laden Sie Ihr erstes LV-PDF hoch.
          </p>
          <Link href="/dashboard/lvs/neu">
            <Button>
              <Plus className="w-4 h-4" /> LV hochladen
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {lvs.map((lv) => (
            <div
              key={lv.id}
              className="rounded-xl bg-white border border-slate-200 p-5 flex items-center gap-4 hover:border-bauplan-300 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <Link
                  href={`/dashboard/lvs/${lv.id}`}
                  className="font-semibold text-slate-900 hover:text-bauplan-600 block truncate"
                >
                  {lv.projekt_name || lv.original_dateiname || "Unbenanntes LV"}
                </Link>
                {lv.auftraggeber && (
                  <div className="text-xs text-slate-500 mt-0.5 truncate">
                    {lv.auftraggeber}
                  </div>
                )}
                <div className="text-sm text-slate-500 mt-1 flex items-center gap-2 flex-wrap">
                  <StatusBadge status={lv.status} />
                  <span>· {lv.positionen_gesamt} Positionen</span>
                  {lv.positionen_unsicher > 0 && (
                    <Badge variant="warning">{lv.positionen_unsicher} unsicher</Badge>
                  )}
                  {/* B+4.9: Hinweis wenn LV noch keinem Projekt zugeordnet ist */}
                  {!lv.project_id && (
                    <Badge variant="default">Lose</Badge>
                  )}
                  {/* B+4.11: Offer-Summary fuer dieses LV */}
                  {offerSummary[lv.id] && (
                    <span className="inline-flex items-center gap-1">
                      <Badge variant="default">
                        {offerSummary[lv.id].offer_count} Angebot
                        {offerSummary[lv.id].offer_count === 1 ? "" : "e"}
                      </Badge>
                      <OfferStatusBadge
                        status={offerSummary[lv.id].latest_status}
                      />
                      {offerSummary[lv.id].expiring_soon && (
                        <Badge variant="warning">Frist läuft ab</Badge>
                      )}
                    </span>
                  )}
                  <span>· {fmtDate(lv.created_at)}</span>
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-semibold text-slate-900">
                  {fmtEur(lv.angebotssumme_netto)}
                </div>
                <div className="flex items-center gap-1 mt-1 justify-end">
                  <Link href={`/dashboard/lvs/${lv.id}`}>
                    <Button size="sm" variant="ghost">
                      Öffnen
                    </Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove(lv.id)}
                    aria-label="Löschen"
                  >
                    <Trash2 className="w-4 h-4 text-danger-500" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
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
