"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle, Pencil, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, PriceEntry, PriceListDetail } from "@/lib/api";
import { fmtEur, fmtNum } from "@/lib/format";

type EditState = { field: keyof PriceEntry; value: string } | null;

export default function PreislisteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [pl, setPl] = useState<PriceListDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditState>(null);
  const [filter, setFilter] = useState<"alle" | "unsicher">("alle");

  async function load() {
    setLoading(true);
    try {
      const data = await api<PriceListDetail>(`/price-lists/${id}`);
      setPl(data);
    } catch {
      toast.error("Preisliste nicht gefunden");
      router.replace("/dashboard/preislisten");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Auto-Poll solange Preisliste verarbeitet wird
  useEffect(() => {
    if (!pl) return;
    const inProgress = pl.status === "queued" || pl.status === "parsing";
    if (!inProgress) return;
    const timer = setInterval(() => load(), 3000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pl?.status]);

  async function activate() {
    try {
      await api(`/price-lists/${id}/activate`, { method: "POST" });
      toast.success("Aktiviert");
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Aktivierung fehlgeschlagen");
    }
  }

  async function saveEdit(entryId: string) {
    if (!editing) return;
    const body: Record<string, unknown> = {};
    if (editing.field === "preis") body.preis = parseFloat(editing.value.replace(",", "."));
    else body[editing.field] = editing.value;
    try {
      await api(`/price-lists/${id}/entries/${entryId}`, {
        method: "PATCH",
        body,
      });
      toast.success("Gespeichert");
      setEditingId(null);
      setEditing(null);
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Speichern fehlgeschlagen");
    }
  }

  if (loading || !pl) {
    return <div className="text-slate-500 py-20 text-center">Lade…</div>;
  }

  const filtered =
    filter === "unsicher" ? pl.entries.filter((e) => e.konfidenz < 0.85) : pl.entries;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-3xl font-bold text-slate-900">
            {pl.haendler}
            {pl.niederlassung && ` — ${pl.niederlassung}`}
          </h1>
          {pl.aktiv && (
            <Badge variant="success">
              <CheckCircle className="w-3.5 h-3.5 mr-1" /> aktiv
            </Badge>
          )}
        </div>
        <p className="text-slate-600 mt-1">
          {pl.stand_monat && `Stand ${pl.stand_monat} · `}
          {pl.eintraege_gesamt} Einträge
          {pl.eintraege_unsicher > 0 && ` · ${pl.eintraege_unsicher} zu prüfen`}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
          <button
            className={`px-3 py-1.5 text-sm rounded-md ${filter === "alle" ? "bg-white shadow text-slate-900" : "text-slate-600"}`}
            onClick={() => setFilter("alle")}
          >
            Alle ({pl.entries.length})
          </button>
          <button
            className={`px-3 py-1.5 text-sm rounded-md ${filter === "unsicher" ? "bg-white shadow text-slate-900" : "text-slate-600"}`}
            onClick={() => setFilter("unsicher")}
          >
            Zu prüfen ({pl.eintraege_unsicher})
          </button>
        </div>
        <div className="flex gap-2">
          {!pl.aktiv && <Button onClick={activate}>Aktiv setzen</Button>}
        </div>
      </div>

      {/* Tabelle */}
      <div className="rounded-xl bg-white border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <Th>Hersteller</Th>
                <Th>Kategorie</Th>
                <Th>Produkt</Th>
                <Th>Abmessungen</Th>
                <Th>Variante</Th>
                <Th className="text-right">Preis</Th>
                <Th>Einheit</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => {
                const editable = editingId === e.id;
                return (
                  <tr
                    key={e.id}
                    className={`border-t border-slate-100 hover:bg-slate-50 ${e.konfidenz < 0.85 ? "bg-warning-500/5" : ""}`}
                  >
                    <Td>{e.hersteller}</Td>
                    <Td>{e.kategorie}</Td>
                    <Td>
                      {editable && editing?.field === "produktname" ? (
                        <Input
                          autoFocus
                          value={editing.value}
                          onChange={(ev) => setEditing({ field: "produktname", value: ev.target.value })}
                          onBlur={() => saveEdit(e.id)}
                          onKeyDown={(ev) => ev.key === "Enter" && saveEdit(e.id)}
                        />
                      ) : (
                        <span
                          className="cursor-pointer"
                          onClick={() => {
                            setEditingId(e.id);
                            setEditing({ field: "produktname", value: e.produktname });
                          }}
                        >
                          {e.produktname || "—"}
                        </span>
                      )}
                    </Td>
                    <Td>{e.abmessungen}</Td>
                    <Td className="text-slate-500">{e.variante}</Td>
                    <Td className="text-right font-medium">
                      {editable && editing?.field === "preis" ? (
                        <Input
                          autoFocus
                          value={editing.value}
                          onChange={(ev) => setEditing({ field: "preis", value: ev.target.value })}
                          onBlur={() => saveEdit(e.id)}
                          onKeyDown={(ev) => ev.key === "Enter" && saveEdit(e.id)}
                        />
                      ) : (
                        <span
                          className="cursor-pointer"
                          onClick={() => {
                            setEditingId(e.id);
                            setEditing({ field: "preis", value: String(e.preis) });
                          }}
                        >
                          {fmtNum(e.preis, 2)}
                        </span>
                      )}
                    </Td>
                    <Td className="text-slate-500">{e.einheit}</Td>
                    <Td>
                      {e.manuell_korrigiert ? (
                        <Badge variant="info">
                          <Pencil className="w-3 h-3 mr-1" /> manuell
                        </Badge>
                      ) : e.konfidenz < 0.85 ? (
                        <Badge variant="warning">
                          <AlertTriangle className="w-3 h-3 mr-1" /> {(e.konfidenz * 100).toFixed(0)}%
                        </Badge>
                      ) : (
                        <Badge variant="success">
                          <CheckCircle className="w-3 h-3 mr-1" /> sicher
                        </Badge>
                      )}
                    </Td>
                    <Td>
                      {editable && (
                        <button
                          onClick={() => {
                            setEditingId(null);
                            setEditing(null);
                          }}
                          className="text-slate-500 hover:text-slate-900"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <th className={`text-left px-4 py-2.5 font-medium ${className}`}>{children}</th>;
}

function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2.5 text-slate-700 ${className}`}>{children}</td>;
}
