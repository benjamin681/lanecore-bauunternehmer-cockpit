"use client";

/**
 * Near-Miss-Drawer (B+4.3.1b, Option A).
 *
 * Informativer Drawer: zeigt pro Material der Position die Top-N
 * Kandidaten + den virtuellen Richtwert-Eintrag als Orientierung.
 * Der Nutzer setzt am Ende einen Gesamt-EP per Input — Klick auf
 * eine Kandidaten-Zeile befuellt den Input mit
 * ``candidate.price_net * required_amount`` als Vorschlag.
 *
 * Keine Material-granularen Overrides; ``PATCH /lvs/{id}/positions/
 * {pos_id}`` nimmt nur den Gesamt-EP entgegen. Follow-ups im
 * Abschluss-Report dokumentiert.
 */

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Drawer } from "@/components/ui/drawer";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Candidate,
  MaterialWithCandidates,
  PositionCandidates,
  Stage,
  fetchCandidates,
  updatePositionEp,
} from "@/lib/candidatesApi";
import { fmtEur, fmtNum } from "@/lib/format";
import { cn } from "@/lib/cn";

// -------------------------------------------------------------------
// Wording — aus docs/ui_wording_guide.md
// -------------------------------------------------------------------
const STAGE_LABEL: Record<Stage, string> = {
  supplier_price: "Preis gefunden",
  fuzzy: "\u00c4hnlicher Artikel",
  estimated: "Richtwert",
};

const STAGE_VARIANT: Record<Stage, "success" | "warning" | "default"> = {
  supplier_price: "success",
  fuzzy: "warning",
  estimated: "default",
};

function confidenceLabel(c: number): string {
  if (c >= 0.85) return "fast sicher";
  if (c >= 0.7) return "wahrscheinlich passend";
  if (c >= 0.5) return "eher unsicher";
  return "unsicher, bitte pr\u00fcfen";
}

// -------------------------------------------------------------------
// Kandidaten-Zeile
// -------------------------------------------------------------------
function CandidateRow({
  cand,
  onPick,
}: {
  cand: Candidate;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onPick}
      className={cn(
        "w-full text-left flex items-start gap-3 rounded-lg border border-slate-200",
        "px-3 py-2.5 hover:bg-slate-50 hover:border-slate-300",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-bauplan-500",
        "transition-colors",
      )}
      data-testid="candidate-row"
    >
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={STAGE_VARIANT[cand.stage] ?? "default"}>
            {STAGE_LABEL[cand.stage] ?? cand.stage}
          </Badge>
          <span className="text-xs text-slate-500">
            {confidenceLabel(cand.match_confidence)}
          </span>
        </div>
        <div className="font-medium text-slate-900 text-sm truncate">
          {cand.candidate_name || "(kein Name)"}
        </div>
        <div className="text-xs text-slate-500 truncate">
          {cand.pricelist_name}
        </div>
        {cand.match_reason && (
          <div className="text-xs text-slate-400 italic truncate">
            {cand.match_reason}
          </div>
        )}
      </div>
      <div className="text-right shrink-0">
        <div className="font-semibold text-slate-900 text-sm">
          {fmtEur(cand.price_net)}
        </div>
        <div className="text-xs text-slate-500">{cand.unit}</div>
      </div>
    </button>
  );
}

// -------------------------------------------------------------------
// Material-Block
// -------------------------------------------------------------------
function MaterialBlock({
  mat,
  onPickCandidate,
}: {
  mat: MaterialWithCandidates;
  onPickCandidate: (c: Candidate, requiredAmount: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="text-xs text-slate-500">
        Benoetigte Menge: {fmtNum(mat.required_amount, 2)} {mat.unit}
      </div>
      {mat.candidates.length === 0 ? (
        <div className="text-sm text-slate-500 italic">
          Keine Kandidaten verf\u00fcgbar.
        </div>
      ) : (
        <div className="space-y-2">
          {mat.candidates.map((c, i) => (
            <CandidateRow
              key={`${c.pricelist_name}-${i}`}
              cand={c}
              onPick={() => onPickCandidate(c, mat.required_amount)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------------
// Drawer
// -------------------------------------------------------------------
export type NearMissDrawerProps = {
  open: boolean;
  onClose: () => void;
  lvId: string;
  posId: string | null;
  /** Aktueller EP der Position (fuer Anzeige im Footer). */
  currentEp: number | null;
  /** Parent soll nach erfolgreichem PATCH das LV neu laden. */
  onUpdated: () => void;
};

export function NearMissDrawer({
  open,
  onClose,
  lvId,
  posId,
  currentEp,
  onUpdated,
}: NearMissDrawerProps) {
  const [data, setData] = useState<PositionCandidates | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [epInput, setEpInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  // Fetch bei Open
  useEffect(() => {
    if (!open || !posId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    fetchCandidates(lvId, posId, 3)
      .then((d) => {
        if (cancelled) return;
        setData(d);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg =
          e instanceof Error ? e.message : "Unbekannter Fehler";
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, posId, lvId, reloadToken]);

  // Bei Close: State zuruecksetzen
  useEffect(() => {
    if (!open) {
      setData(null);
      setError(null);
      setEpInput("");
      setSubmitting(false);
    }
  }, [open]);

  const firstMaterialValue = useMemo(() => {
    if (!data?.materials?.length) return null;
    return "m-0";
  }, [data]);

  async function handleSubmit() {
    if (!posId) return;
    const ep = parseFloat(epInput.replace(",", "."));
    if (!Number.isFinite(ep) || ep <= 0) {
      toast.error("Bitte einen g\u00fcltigen Preis eingeben.");
      return;
    }
    setSubmitting(true);
    try {
      await updatePositionEp(lvId, posId, ep);
      toast.success("Preis \u00fcbernommen");
      onUpdated();
      onClose();
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail;
      const msg =
        detail || (e instanceof Error ? e.message : "Unbekannter Fehler");
      toast.error(`Fehler: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  function handlePickCandidate(cand: Candidate, requiredAmount: number) {
    const suggestion = cand.price_net * requiredAmount;
    setEpInput(suggestion.toFixed(2));
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={data?.position_name || "Details"}
      description={
        data
          ? `${data.materials.length} Materialien zum Vergleich`
          : undefined
      }
      size="md"
    >
      <div className="flex flex-col gap-6">
        {loading && (
          <div data-testid="nm-loading" className="space-y-3">
            <div className="h-4 w-1/2 rounded bg-slate-200 animate-pulse" />
            <div className="h-20 w-full rounded bg-slate-100 animate-pulse" />
            <div className="h-20 w-full rounded bg-slate-100 animate-pulse" />
          </div>
        )}

        {error && !loading && (
          <div
            role="alert"
            data-testid="nm-error"
            className="rounded-lg border border-danger-500/30 bg-danger-500/5 p-4 space-y-2"
          >
            <div className="text-sm font-medium text-danger-600">
              Kandidaten konnten nicht geladen werden.
            </div>
            <div className="text-xs text-slate-500">{error}</div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setReloadToken((n) => n + 1)}
            >
              Erneut versuchen
            </Button>
          </div>
        )}

        {!loading && !error && data && (
          <Accordion defaultValue={firstMaterialValue}>
            {data.materials.map((m, idx) => (
              <AccordionItem key={`m-${idx}`} value={`m-${idx}`}>
                <AccordionTrigger>
                  <span className="truncate">{m.material_name || "(unbenannt)"}</span>
                </AccordionTrigger>
                <AccordionContent>
                  <MaterialBlock mat={m} onPickCandidate={handlePickCandidate} />
                </AccordionContent>
              </AccordionItem>
            ))}
            {data.materials.length === 0 && (
              <div className="text-sm text-slate-500 italic py-4">
                Diese Position hat keine Materialzeilen. Du kannst den
                Preis trotzdem direkt eingeben.
              </div>
            )}
          </Accordion>
        )}

        {/* Footer: EP-Input + Submit */}
        <div
          data-testid="nm-footer"
          className="mt-auto border-t border-slate-200 pt-4 space-y-3"
        >
          {typeof currentEp === "number" && (
            <div className="text-xs text-slate-500">
              Aktueller EP: {fmtEur(currentEp)}
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="nm-ep-input">Neuer EP</Label>
            <Input
              id="nm-ep-input"
              data-testid="nm-ep-input"
              type="text"
              inputMode="decimal"
              placeholder="z.B. 42,50"
              value={epInput}
              onChange={(e) => setEpInput(e.target.value)}
              disabled={submitting}
            />
          </div>
          <div className="flex justify-end">
            <Button
              onClick={handleSubmit}
              disabled={submitting || !epInput.trim()}
            >
              {submitting ? "Wird gespeichert \u2026" : "Preis selbst eintragen"}
            </Button>
          </div>
        </div>
      </div>
    </Drawer>
  );
}

export default NearMissDrawer;
