"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckCircle, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, PriceList } from "@/lib/api";
import { fmtDate } from "@/lib/format";

export default function PreislistenPage() {
  const [lists, setLists] = useState<PriceList[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const data = await api<PriceList[]>("/price-lists");
    setLists(data);
    setLoading(false);
  }
  useEffect(() => {
    load();
  }, []);

  async function activate(id: string) {
    try {
      await api(`/price-lists/${id}/activate`, { method: "POST" });
      toast.success("Preisliste aktiviert");
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Aktivierung fehlgeschlagen");
    }
  }

  async function remove(id: string) {
    if (!confirm("Preisliste wirklich löschen?")) return;
    try {
      await api(`/price-lists/${id}`, { method: "DELETE" });
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
          <h1 className="text-3xl font-bold text-slate-900">Preislisten</h1>
          <p className="text-slate-600 mt-1">
            Ihre eigenen Einkaufspreise — jede Liste gehört nur Ihnen.
          </p>
        </div>
        <Link href="/dashboard/preislisten/neu">
          <Button>
            <Plus className="w-4 h-4" /> Neue Preisliste
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="text-slate-500 py-20 text-center">Lade…</div>
      ) : lists.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-12 text-center">
          <div className="text-slate-900 font-medium">Noch keine Preisliste hochgeladen</div>
          <p className="text-sm text-slate-600 mt-1 mb-6">
            Laden Sie Ihre Händler-Preisliste (z.B. Kemmler, Wölpert) als PDF hoch.
          </p>
          <Link href="/dashboard/preislisten/neu">
            <Button>
              <Plus className="w-4 h-4" /> Erste Preisliste hochladen
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {lists.map((pl) => (
            <div
              key={pl.id}
              className="rounded-xl bg-white border border-slate-200 p-5 flex items-center gap-4"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Link
                    href={`/dashboard/preislisten/${pl.id}`}
                    className="font-semibold text-slate-900 hover:text-bauplan-600"
                  >
                    {pl.haendler}
                    {pl.niederlassung && ` — ${pl.niederlassung}`}
                  </Link>
                  {pl.aktiv && (
                    <Badge variant="success">
                      <CheckCircle className="w-3 h-3 mr-1" /> aktiv
                    </Badge>
                  )}
                  {pl.eintraege_unsicher > 0 && (
                    <Badge variant="warning">{pl.eintraege_unsicher} zu prüfen</Badge>
                  )}
                </div>
                <div className="text-sm text-slate-500 mt-1">
                  {pl.stand_monat && `Stand ${pl.stand_monat} · `}
                  {pl.eintraege_gesamt} Einträge · hochgeladen {fmtDate(pl.created_at)}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {!pl.aktiv && (
                  <Button size="sm" variant="secondary" onClick={() => activate(pl.id)}>
                    Aktivieren
                  </Button>
                )}
                <Link href={`/dashboard/preislisten/${pl.id}`}>
                  <Button size="sm" variant="ghost">
                    Details
                  </Button>
                </Link>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => remove(pl.id)}
                  aria-label="Löschen"
                >
                  <Trash2 className="w-4 h-4 text-danger-500" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
