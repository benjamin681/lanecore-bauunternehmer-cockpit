"use client";

/**
 * B+4.12 — Aufmaß-Detail-Seite.
 *
 * Header: Aufmaß-Nummer, LV-Name, Status, prominente Total-Differenz.
 * Body:   Tabelle aller Positionen mit inline editierbarer gemessene_menge,
 *         Live-Recalc des GP und der Total-Differenz.
 * Footer: Abschliessen + Final-Angebot erstellen.
 */
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  Download,
  FileCheck2,
  Lock,
  Pencil,
  Save,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AUFMASS_STATUS_LABELS,
  Aufmass,
  AufmassDetail,
  AufmassPosition,
  AufmassStatus,
  AufmassSummary,
  aufmassApi,
} from "@/lib/tenantApi";
import { LV, api } from "@/lib/api";
import { fmtDate, fmtEur, fmtNum } from "@/lib/format";

export default function AufmassDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [aufmass, setAufmass] = useState<AufmassDetail | null>(null);
  const [lv, setLv] = useState<LV | null>(null);
  const [summary, setSummary] = useState<AufmassSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [edits, setEdits] = useState<Record<string, { menge?: string; notes?: string }>>({});
  const [openNotes, setOpenNotes] = useState<Record<string, boolean>>({});

  async function loadAll() {
    setLoading(true);
    try {
      const a = await aufmassApi.get(id);
      setAufmass(a);
      const [s, lvData] = await Promise.all([
        aufmassApi.summary(id).catch(() => null),
        api<LV>(`/lvs/${a.lv_id}`).catch(() => null),
      ]);
      setSummary(s);
      setLv(lvData);
    } catch (e: any) {
      toast.error(e?.detail || "Aufmaß konnte nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const isLocked = aufmass?.status !== "in_progress";

  // Lokal berechnete Live-Total-Differenz (aus edits + persistierten Werten)
  const liveDiff = useMemo(() => {
    if (!aufmass) return { aufmass: 0, lv: 0, diff: 0 };
    let lvTotal = 0;
    let auTotal = 0;
    for (const p of aufmass.positions) {
      lvTotal += Number(p.gp_lv_snapshot);
      const edited = edits[p.id]?.menge;
      if (edited !== undefined && edited !== "" && !isNaN(Number(edited))) {
        auTotal += Number(edited) * Number(p.ep);
      } else {
        auTotal += Number(p.gp_aufmass);
      }
    }
    return { aufmass: auTotal, lv: lvTotal, diff: auTotal - lvTotal };
  }, [aufmass, edits]);

  async function saveAll() {
    if (!aufmass) return;
    const dirty = Object.entries(edits).filter(
      ([, v]) => (v.menge !== undefined && v.menge !== "") || v.notes !== undefined,
    );
    if (dirty.length === 0) {
      toast.info("Keine Änderungen.");
      return;
    }
    setBusy(true);
    try {
      for (const [posId, v] of dirty) {
        const body: Record<string, unknown> = {};
        if (v.menge !== undefined && v.menge !== "") {
          const n = Number(v.menge);
          if (!isNaN(n)) body.gemessene_menge = n;
        }
        if (v.notes !== undefined) body.notes = v.notes;
        if (Object.keys(body).length > 0) {
          await aufmassApi.patchPosition(aufmass.id, posId, body as any);
        }
      }
      toast.success(`${dirty.length} Position${dirty.length === 1 ? "" : "en"} gespeichert`);
      setEdits({});
      await loadAll();
    } catch (e: any) {
      toast.error(e?.detail || "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function finalize() {
    if (!aufmass) return;
    if (!confirm("Aufmaß abschließen? Danach sind keine Änderungen mehr möglich.")) return;
    setBusy(true);
    try {
      // Erst pending edits speichern
      const dirty = Object.entries(edits).filter(
        ([, v]) => (v.menge !== undefined && v.menge !== "") || v.notes !== undefined,
      );
      for (const [posId, v] of dirty) {
        const body: Record<string, unknown> = {};
        if (v.menge !== undefined && v.menge !== "") {
          const n = Number(v.menge);
          if (!isNaN(n)) body.gemessene_menge = n;
        }
        if (v.notes !== undefined) body.notes = v.notes;
        if (Object.keys(body).length > 0) {
          await aufmassApi.patchPosition(aufmass.id, posId, body as any);
        }
      }
      await aufmassApi.finalize(aufmass.id);
      toast.success("Aufmaß abgeschlossen");
      setEdits({});
      await loadAll();
    } catch (e: any) {
      toast.error(e?.detail || "Abschließen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function createFinalOffer() {
    if (!aufmass) return;
    setBusy(true);
    try {
      const offer = await aufmassApi.createFinalOffer(aufmass.id);
      toast.success(`Final-Angebot ${offer.offer_number} erstellt`);
      router.push(`/dashboard/lvs/${aufmass.lv_id}`);
    } catch (e: any) {
      toast.error(e?.detail || "Final-Angebot fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function downloadAufmassPdf() {
    if (!aufmass) return;
    try {
      const res = await fetch(aufmassApi.pdfUrl(aufmass.id), {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("lvp_token") ?? ""}`,
        },
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Aufmass-${aufmass.aufmass_number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("PDF-Download fehlgeschlagen");
    }
  }

  if (loading || !aufmass) {
    return <div className="text-slate-500 py-20 text-center">Lade…</div>;
  }

  const diffPositive = liveDiff.diff > 0;
  const diffZero = Math.abs(liveDiff.diff) < 0.005;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/dashboard/lvs/${aufmass.lv_id}`}
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-bauplan-600"
        >
          <ArrowLeft className="w-4 h-4" /> Zurück zum LV
        </Link>
      </div>

      <header className="rounded-xl bg-white border border-slate-200 p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-slate-900">
              Aufmaß <span className="font-mono">{aufmass.aufmass_number}</span>
            </h1>
            <div className="text-slate-600 mt-1 flex items-center gap-2 flex-wrap">
              <AufmassStatusBadge status={aufmass.status} />
              {lv && (
                <span className="text-sm">
                  · LV: <span className="font-medium">{lv.projekt_name}</span>
                  {lv.auftraggeber && ` · ${lv.auftraggeber}`}
                </span>
              )}
            </div>
            {aufmass.finalized_at && (
              <div className="text-xs text-slate-500 mt-1">
                Abgeschlossen: {fmtDate(aufmass.finalized_at)}
              </div>
            )}
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-500">Differenz zum LV (netto)</div>
            <div
              className={
                "text-3xl font-bold " +
                (diffZero
                  ? "text-slate-900"
                  : diffPositive
                    ? "text-success-600"
                    : "text-danger-600")
              }
            >
              {diffPositive && "+"}
              {fmtEur(liveDiff.diff)}
            </div>
            <div className="text-xs text-slate-500">
              LV {fmtEur(liveDiff.lv)} · Aufmaß {fmtEur(liveDiff.aufmass)}
            </div>
          </div>
        </div>
      </header>

      {summary && summary.by_group.length > 1 && (
        <section className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Differenz pro Hauptgruppe</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-600 bg-slate-50">
                <tr>
                  <Th>Gruppe</Th>
                  <Th className="text-right">Positionen</Th>
                  <Th className="text-right">LV netto</Th>
                  <Th className="text-right">Aufmaß netto</Th>
                  <Th className="text-right">Differenz</Th>
                </tr>
              </thead>
              <tbody>
                {summary.by_group.map((g) => (
                  <tr key={g.group} className="border-t border-slate-100">
                    <Td className="font-mono">{g.group}</Td>
                    <Td className="text-right tabular-nums">{g.position_count}</Td>
                    <Td className="text-right tabular-nums">{fmtEur(g.lv_netto)}</Td>
                    <Td className="text-right tabular-nums">{fmtEur(g.aufmass_netto)}</Td>
                    <Td
                      className={
                        "text-right tabular-nums font-medium " +
                        (g.diff_netto > 0
                          ? "text-success-600"
                          : g.diff_netto < 0
                            ? "text-danger-600"
                            : "text-slate-600")
                      }
                    >
                      {g.diff_netto > 0 && "+"}
                      {fmtEur(g.diff_netto)}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="rounded-xl bg-white border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <Th>OZ</Th>
                <Th>Kurztext</Th>
                <Th>Einh.</Th>
                <Th className="text-right">Menge LV</Th>
                <Th className="text-right">Menge Aufmaß</Th>
                <Th className="text-right">EP</Th>
                <Th className="text-right">GP LV</Th>
                <Th className="text-right">GP Aufmaß</Th>
                <Th className="text-right">Differenz</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {aufmass.positions.map((p) => (
                <PositionRow
                  key={p.id}
                  pos={p}
                  isLocked={isLocked}
                  edits={edits}
                  setEdits={setEdits}
                  notesOpen={!!openNotes[p.id]}
                  toggleNotes={() =>
                    setOpenNotes((prev) => ({ ...prev, [p.id]: !prev[p.id] }))
                  }
                />
              ))}
            </tbody>
            <tfoot className="bg-slate-50">
              <tr className="border-t-2 border-slate-200">
                <Td colSpan={6} className="font-medium text-right">
                  Summen netto
                </Td>
                <Td className="text-right tabular-nums font-medium">
                  {fmtEur(liveDiff.lv)}
                </Td>
                <Td className="text-right tabular-nums font-medium">
                  {fmtEur(liveDiff.aufmass)}
                </Td>
                <Td
                  className={
                    "text-right tabular-nums font-bold " +
                    (diffZero
                      ? "text-slate-900"
                      : diffPositive
                        ? "text-success-600"
                        : "text-danger-600")
                  }
                >
                  {diffPositive && "+"}
                  {fmtEur(liveDiff.diff)}
                </Td>
                <Td></Td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <footer className="rounded-xl bg-white border border-slate-200 p-4 flex items-center gap-2 flex-wrap">
        {!isLocked && (
          <>
            <Button onClick={saveAll} disabled={busy} variant="secondary">
              <Save className="w-4 h-4" /> Aufmaß speichern
            </Button>
            <Button onClick={finalize} disabled={busy}>
              <Lock className="w-4 h-4" /> Aufmaß abschließen
            </Button>
          </>
        )}
        {isLocked && aufmass.status === "finalized" && (
          <>
            <Button onClick={createFinalOffer} disabled={busy} variant="primary">
              <FileCheck2 className="w-4 h-4" /> Final-Angebot erstellen
            </Button>
            <Button onClick={downloadAufmassPdf} disabled={busy} variant="secondary">
              <Download className="w-4 h-4" /> Aufmaß-PDF
            </Button>
          </>
        )}
      </footer>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Sub-Components
// --------------------------------------------------------------------------- //
function PositionRow({
  pos,
  isLocked,
  edits,
  setEdits,
  notesOpen,
  toggleNotes,
}: {
  pos: AufmassPosition;
  isLocked: boolean;
  edits: Record<string, { menge?: string; notes?: string }>;
  setEdits: React.Dispatch<
    React.SetStateAction<Record<string, { menge?: string; notes?: string }>>
  >;
  notesOpen: boolean;
  toggleNotes: () => void;
}) {
  const liveMenge = (() => {
    const e = edits[pos.id]?.menge;
    if (e !== undefined && e !== "") {
      const n = Number(e);
      return isNaN(n) ? Number(pos.gemessene_menge) : n;
    }
    return Number(pos.gemessene_menge);
  })();
  const liveGp = liveMenge * Number(pos.ep);
  const diff = liveGp - Number(pos.gp_lv_snapshot);

  return (
    <>
      <tr className="border-t border-slate-100 hover:bg-slate-50">
        <Td className="font-mono whitespace-nowrap">{pos.oz}</Td>
        <Td className="max-w-md">
          <div className="truncate" title={pos.kurztext}>
            {pos.kurztext}
          </div>
        </Td>
        <Td>{pos.einheit}</Td>
        <Td className="text-right tabular-nums text-slate-500">
          {fmtNum(pos.lv_menge, 2)}
        </Td>
        <Td className="text-right tabular-nums">
          {isLocked ? (
            fmtNum(pos.gemessene_menge, 2)
          ) : (
            <input
              type="number"
              step="0.01"
              defaultValue={pos.gemessene_menge}
              onChange={(e) =>
                setEdits((prev) => ({
                  ...prev,
                  [pos.id]: { ...prev[pos.id], menge: e.target.value },
                }))
              }
              className="w-24 rounded border border-slate-300 px-2 py-1 text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-bauplan-500"
            />
          )}
        </Td>
        <Td className="text-right tabular-nums text-slate-500">
          {fmtEur(pos.ep)}
        </Td>
        <Td className="text-right tabular-nums text-slate-500">
          {fmtEur(pos.gp_lv_snapshot)}
        </Td>
        <Td className="text-right tabular-nums font-medium">
          {fmtEur(liveGp)}
        </Td>
        <Td
          className={
            "text-right tabular-nums " +
            (Math.abs(diff) < 0.005
              ? "text-slate-400"
              : diff > 0
                ? "text-success-600"
                : "text-danger-600")
          }
        >
          {diff > 0 && "+"}
          {Math.abs(diff) < 0.005 ? "—" : fmtEur(diff)}
        </Td>
        <Td>
          <button
            type="button"
            onClick={toggleNotes}
            className="text-slate-400 hover:text-bauplan-600"
            aria-label="Notiz"
          >
            <Pencil className="w-4 h-4" />
          </button>
        </Td>
      </tr>
      {notesOpen && (
        <tr>
          <td colSpan={10} className="px-4 py-2 bg-slate-50 border-t border-slate-100">
            <label className="block text-xs text-slate-500 mb-1">
              Notiz zur Position
            </label>
            {isLocked ? (
              <p className="text-sm text-slate-700">
                {pos.notes || <span className="text-slate-400">—</span>}
              </p>
            ) : (
              <textarea
                rows={2}
                defaultValue={pos.notes ?? ""}
                onChange={(e) =>
                  setEdits((prev) => ({
                    ...prev,
                    [pos.id]: { ...prev[pos.id], notes: e.target.value },
                  }))
                }
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bauplan-500"
                placeholder="z. B. Mehrmenge wegen Rohbauabweichung"
              />
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function AufmassStatusBadge({ status }: { status: string }) {
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

function Th({
  children,
  className = "",
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <th className={`text-left px-4 py-2.5 font-medium ${className}`}>{children}</th>
  );
}
function Td({
  children,
  className = "",
  colSpan,
}: {
  children?: React.ReactNode;
  className?: string;
  colSpan?: number;
}) {
  return (
    <td colSpan={colSpan} className={`px-4 py-2.5 text-slate-700 ${className}`}>
      {children}
    </td>
  );
}
