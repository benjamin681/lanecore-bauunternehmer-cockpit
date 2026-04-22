"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle,
  Download,
  FileDown,
  Pencil,
  Play,
  Search,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { StageBadge } from "@/components/ui/stage-badge";
import { api, Job, LVDetail, Position, pollJob } from "@/lib/api";
import { fmtEur, fmtNum } from "@/lib/format";
import { NearMissDrawer } from "@/components/NearMissDrawer";

type Edit = { field: "menge" | "einheit" | "kurztext" | "erkanntes_system" | "ep"; value: string } | null;

export default function LvDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [lv, setLv] = useState<LVDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingPos, setEditingPos] = useState<string | null>(null);
  const [edit, setEdit] = useState<Edit>(null);
  const [busy, setBusy] = useState(false);

  // B+4.3.1b: Near-Miss-Drawer-State. active* bleiben nach Close
  // erhalten, damit die Slide-out-Animation nicht flackert; sie werden
  // ueberschrieben, sobald ein neuer Drawer geoeffnet wird.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activePosId, setActivePosId] = useState<string | null>(null);
  const [activeCurrentEp, setActiveCurrentEp] = useState<number | null>(null);

  function openDrawer(p: Position) {
    setActivePosId(p.id);
    setActiveCurrentEp(p.ep);
    setDrawerOpen(true);
  }
  function closeDrawer() {
    setDrawerOpen(false);
  }

  async function load() {
    setLoading(true);
    try {
      const data = await api<LVDetail>(`/lvs/${id}`);
      setLv(data);
    } catch {
      toast.error("LV nicht gefunden");
      router.replace("/dashboard/lvs");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Auto-Poll solange LV noch verarbeitet wird
  useEffect(() => {
    if (!lv) return;
    const inProgress = lv.status === "queued" || lv.status === "extracting";
    if (!inProgress) return;
    const timer = setInterval(() => load(), 3000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lv?.status]);

  async function savePosition(posId: string) {
    if (!edit) return;
    const body: Record<string, unknown> = {};
    if (edit.field === "menge" || edit.field === "ep") {
      const n = parseFloat(edit.value.replace(",", "."));
      if (!Number.isFinite(n)) {
        toast.error("Bitte eine gültige Zahl eingeben.");
        return;
      }
      body[edit.field] = n;
    } else {
      body[edit.field] = edit.value;
    }
    try {
      await api(`/lvs/${id}/positions/${posId}`, { method: "PATCH", body });
      toast.success("Gespeichert");
      setEditingPos(null);
      setEdit(null);
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Speichern fehlgeschlagen");
    }
  }

  async function retryParsing() {
    setBusy(true);
    try {
      const job = await api<Job>(`/lvs/${id}/retry-parse`, { method: "POST" });
      toast.info("Parsing neu gestartet");
      await pollJob(job.id, { onProgress: () => {} });
      toast.success("Parsing fertig");
      await load();
    } catch (e: any) {
      toast.error(`Neustart fehlgeschlagen: ${e?.detail || e?.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function runKalkulation() {
    setBusy(true);
    try {
      await api(`/lvs/${id}/kalkulation`, { method: "POST" });
      toast.success("Kalkulation abgeschlossen");
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Kalkulation fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function exportPdf() {
    setBusy(true);
    try {
      await api(`/lvs/${id}/export`, { method: "POST" });
      toast.success("PDF erstellt. Download startet.");
      await load();
      // Direkt Download öffnen
      downloadPdf();
    } catch (e: any) {
      toast.error(e?.detail || "Export fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function downloadPdf() {
    try {
      const blob = await api<Blob>(`/lvs/${id}/download`, { raw: true });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `LV_${lv?.projekt_name || id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast.error(e?.detail || "Download fehlgeschlagen");
    }
  }

  if (loading || !lv) {
    return <div className="text-slate-500 py-20 text-center">Lade…</div>;
  }

  const canCalculate = lv.status === "review_needed" || lv.status === "calculated";
  const canExport = lv.status === "calculated" || lv.status === "exported";
  const canDownload = lv.status === "exported";

  return (
    <div className="space-y-6">
      {/* Kopf */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <h1 className="text-3xl font-bold text-slate-900 truncate">
            {lv.projekt_name || lv.original_dateiname || "Unbenanntes LV"}
          </h1>
          {lv.auftraggeber && (
            <p className="text-slate-600 mt-1">Auftraggeber: {lv.auftraggeber}</p>
          )}
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <Badge variant="info">{lv.status}</Badge>
            <span className="text-sm text-slate-500">
              {lv.positionen_gesamt} Positionen · {lv.positionen_gematcht} sicher gematcht
              {lv.positionen_unsicher > 0 && ` · ${lv.positionen_unsicher} zu prüfen`}
            </span>
          </div>
        </div>

        <div className="text-right">
          <div className="text-sm text-slate-600">Angebotssumme netto</div>
          <div className="text-3xl font-bold text-success-600">
            {fmtEur(lv.angebotssumme_netto)}
          </div>
        </div>
      </div>

      {/* Parsing-Hinweis wenn stuck */}
      {(lv.status === "queued" || lv.status === "error" || lv.positionen_gesamt === 0) && (
        <div className="rounded-xl bg-warning-500/10 border border-warning-500/30 p-4 flex items-center justify-between gap-4">
          <div>
            <div className="font-medium text-slate-900">
              {lv.status === "error" ? "Parsing fehlgeschlagen" : "Parsing nicht abgeschlossen"}
            </div>
            <div className="text-sm text-slate-600 mt-0.5">
              Das LV hat noch keine Positionen. Starte das Parsing neu — der Upload wurde
              gespeichert.
            </div>
          </div>
          <Button onClick={retryParsing} disabled={busy}>
            <Play className="w-4 h-4" />
            {busy ? "Läuft…" : "Parsing neu starten"}
          </Button>
        </div>
      )}

      {/* Action-Bar */}
      <div className="rounded-xl bg-white border border-slate-200 p-4 flex items-center gap-2 flex-wrap">
        <Button onClick={runKalkulation} disabled={!canCalculate || busy}>
          <Play className="w-4 h-4" />
          {lv.status === "calculated" || lv.status === "exported"
            ? "Kalkulation wiederholen"
            : "Kalkulieren"}
        </Button>
        <Button onClick={exportPdf} disabled={!canExport || busy} variant="accent">
          <FileDown className="w-4 h-4" />
          Als PDF exportieren
        </Button>
        <Button onClick={downloadPdf} disabled={!canDownload} variant="secondary">
          <Download className="w-4 h-4" />
          PDF herunterladen
        </Button>
        <div className="flex-1" />
        <div className="text-sm text-slate-500">
          Klicken Sie auf einen Wert in der Tabelle, um ihn anzupassen.
        </div>
      </div>

      {/* Positions-Tabelle */}
      <div className="rounded-xl bg-white border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <Th>OZ</Th>
                <Th>Beschreibung</Th>
                <Th>System</Th>
                <Th className="text-right">Menge</Th>
                <Th>Einh.</Th>
                <Th className="text-right">Mat.</Th>
                <Th className="text-right">Lohn</Th>
                <Th className="text-right">Zuschl.</Th>
                <Th className="text-right">EP</Th>
                <Th className="text-right">GP</Th>
                <Th>Preisquelle</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {lv.positions.map((p) => (
                <PosRow
                  key={p.id}
                  pos={p}
                  editingPos={editingPos}
                  edit={edit}
                  setEdit={(v) => setEdit(v)}
                  setEditingPos={(v) => setEditingPos(v)}
                  onSave={() => savePosition(p.id)}
                  onOpenDrawer={() => openDrawer(p)}
                />
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 border-t-2 border-slate-200">
                <td colSpan={9} className="px-4 py-3 text-right font-semibold text-slate-700">
                  Angebotssumme netto
                </td>
                <td className="px-4 py-3 text-right font-bold text-success-600 text-base">
                  {fmtEur(lv.angebotssumme_netto)}
                </td>
                <td colSpan={2}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* B+4.3.1b: Near-Miss-Drawer, getriggert via StageBadge-Click in PosRow */}
      <NearMissDrawer
        open={drawerOpen}
        onClose={closeDrawer}
        lvId={id}
        posId={activePosId}
        currentEp={activeCurrentEp}
        onUpdated={load}
      />
    </div>
  );
}

function PosRow({
  pos,
  editingPos,
  edit,
  setEdit,
  setEditingPos,
  onSave,
  onOpenDrawer,
}: {
  pos: Position;
  editingPos: string | null;
  edit: Edit;
  setEdit: (e: Edit) => void;
  setEditingPos: (id: string | null) => void;
  onSave: () => void;
  onOpenDrawer: () => void;
}) {
  const isEditing = editingPos === pos.id;
  const hasWarn = !!pos.warnung;
  const unsure = pos.konfidenz < 0.85;

  const cell = (field: NonNullable<Edit>["field"], display: React.ReactNode, raw: string) => {
    if (isEditing && edit?.field === field) {
      return (
        <Input
          autoFocus
          value={edit.value}
          onChange={(e) => setEdit({ field, value: e.target.value })}
          onBlur={onSave}
          onKeyDown={(e) => e.key === "Enter" && onSave()}
        />
      );
    }
    return (
      <span
        className="cursor-pointer hover:bg-bauplan-50 rounded px-1 -mx-1"
        onClick={() => {
          setEditingPos(pos.id);
          setEdit({ field, value: raw });
        }}
      >
        {display}
      </span>
    );
  };

  return (
    <tr
      className={`border-t border-slate-100 ${hasWarn ? "bg-warning-500/5" : ""} hover:bg-slate-50`}
    >
      <Td className="font-mono text-xs text-slate-500">{pos.oz}</Td>
      <Td className="max-w-md">
        {cell("kurztext", (
          <span>
            <span className="font-medium text-slate-900 line-clamp-2">
              {pos.kurztext || pos.titel}
            </span>
            {hasWarn && (
              <span className="block text-xs text-warning-600 mt-1">
                <AlertTriangle className="w-3 h-3 inline mr-1" />
                {pos.warnung}
              </span>
            )}
          </span>
        ), pos.kurztext)}
      </Td>
      <Td>
        {cell(
          "erkanntes_system",
          <Badge variant={pos.erkanntes_system ? "info" : "default"}>
            {pos.erkanntes_system || "—"}
            {pos.feuerwiderstand ? ` · ${pos.feuerwiderstand}` : ""}
          </Badge>,
          pos.erkanntes_system,
        )}
      </Td>
      <Td className="text-right">
        {cell("menge", fmtNum(pos.menge, 2), String(pos.menge))}
      </Td>
      <Td className="text-slate-500">
        {cell("einheit", pos.einheit, pos.einheit)}
      </Td>
      <Td className="text-right text-slate-600">{fmtNum(pos.material_ep, 2)}</Td>
      <Td className="text-right text-slate-600">{fmtNum(pos.lohn_ep, 2)}</Td>
      <Td className="text-right text-slate-600">{fmtNum(pos.zuschlaege_ep, 2)}</Td>
      <Td className="text-right font-medium">
        {cell("ep", fmtNum(pos.ep, 2), String(pos.ep))}
      </Td>
      <Td className="text-right font-semibold text-slate-900">{fmtNum(pos.gp, 2)}</Td>
      <Td>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onOpenDrawer}
            aria-label={`Preis-Details fuer Position ${pos.oz}`}
            title="Preis-Details anzeigen"
            className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 -mx-1 hover:bg-slate-100 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-bauplan-500"
          >
            <StageBadge summary={pos.price_source_summary} />
          </button>
          {pos.needs_price_review && (
            <span title="Manuelle Prüfung empfohlen" aria-label="Review empfohlen">
              <Search className="w-3.5 h-3.5 text-warning-600" />
            </span>
          )}
        </div>
      </Td>
      <Td>
        <div className="flex items-center gap-1">
          {pos.manuell_korrigiert && <Pencil className="w-3.5 h-3.5 text-bauplan-600" />}
          {unsure && !pos.manuell_korrigiert && (
            <AlertTriangle className="w-3.5 h-3.5 text-warning-500" />
          )}
          {!unsure && !hasWarn && pos.ep > 0 && (
            <CheckCircle className="w-3.5 h-3.5 text-success-500" />
          )}
          {isEditing && (
            <button
              onClick={() => {
                setEditingPos(null);
                setEdit(null);
              }}
            >
              <X className="w-3.5 h-3.5 text-slate-500" />
            </button>
          )}
        </div>
      </Td>
    </tr>
  );
}

function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <th className={`text-left px-4 py-2.5 font-medium ${className}`}>{children}</th>;
}

function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2.5 text-slate-700 ${className}`}>{children}</td>;
}
