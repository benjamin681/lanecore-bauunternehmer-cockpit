"use client";

/**
 * Katalog-Luecken-Panel (B+4.3.1c).
 *
 * Presentation-Komponente mit lokalem Data-State. Parent steuert nur:
 *   - lvId
 *   - dataToken: inkrementiert nach Drawer-Save -> Refetch
 *   - onOpenPosition: Callback fuer Near-Miss-Drawer-Handoff
 *
 * Drawer-State bleibt in der Page (siehe lvs/[id]/page.tsx), damit die
 * bestehende Integration aus B+4.3.1b unveraendert mitverwendet wird.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CatalogGapEntry,
  GapSeverity,
  LVGapsReport,
  fetchGaps,
} from "@/lib/gapsApi";
import { cn } from "@/lib/cn";

// -------------------------------------------------------------------
// Wording (aus docs/ui_wording_guide.md)
// -------------------------------------------------------------------
type Variant = "default" | "success" | "warning" | "danger" | "info";

const SEVERITY_CONFIG: Record<
  GapSeverity,
  { label: string; variant: Variant }
> = {
  missing: { label: "Fehlt im Katalog", variant: "danger" },
  low_confidence: { label: "Unsicher, bitte pr\u00fcfen", variant: "warning" },
  estimated: { label: "Richtwert", variant: "default" },
};

// -------------------------------------------------------------------
// Props
// -------------------------------------------------------------------
export type CatalogGapsPanelProps = {
  lvId: string;
  /**
   * Refetch-Token: inkrementiert der Parent (z. B. nach einem
   * Drawer-Save) um das Panel zum Neulesen zu zwingen.
   */
  dataToken: number;
  /**
   * Wird vom Parent aufgerufen wenn der Nutzer bei einer Luecke den
   * Near-Miss-Drawer oeffnen will. Der Parent loest die Position ueber
   * ihre ID aus seinem eigenen LV-State auf und setzt den Drawer-State
   * entsprechend.
   */
  onOpenPosition: (positionId: string) => void;
};

// -------------------------------------------------------------------
// Einzelne Gap-Zeile
// -------------------------------------------------------------------
function GapRow({
  gap,
  onOpen,
}: {
  gap: CatalogGapEntry;
  onOpen: () => void;
}) {
  const cfg = SEVERITY_CONFIG[gap.severity];
  return (
    <div
      data-testid="gap-row"
      className={cn(
        "flex items-center gap-4 py-3 px-3 rounded-lg",
        "border border-slate-200 bg-white hover:bg-slate-50",
      )}
    >
      <div className="shrink-0 w-48">
        <Badge variant={cfg.variant}>{cfg.label}</Badge>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-slate-500 font-mono">
          {gap.position_oz || "\u2014"}
        </div>
        <div className="font-medium text-slate-900 text-sm truncate">
          {gap.position_name || "\u2014"}
        </div>
        <div className="text-xs text-slate-500 truncate">
          {gap.material_name || gap.material_dna || "\u2014"}
        </div>
      </div>
      <Button
        variant="secondary"
        size="sm"
        onClick={onOpen}
        data-testid="gap-open-button"
      >
        Kandidaten prüfen <ArrowRight className="w-4 h-4" />
      </Button>
    </div>
  );
}

// -------------------------------------------------------------------
// Panel
// -------------------------------------------------------------------
export function CatalogGapsPanel({
  lvId,
  dataToken,
  onOpenPosition,
}: CatalogGapsPanelProps) {
  const [data, setData] = useState<LVGapsReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [includeLowConfidence, setIncludeLowConfidence] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const report = await fetchGaps(lvId, includeLowConfidence);
      setData(report);
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail;
      const msg =
        detail || (e instanceof Error ? e.message : "Unbekannter Fehler");
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [lvId, includeLowConfidence]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lvId, dataToken, includeLowConfidence]);

  return (
    <div
      className="rounded-xl bg-white border border-slate-200 p-6 space-y-5"
      data-testid="catalog-gaps-panel"
    >
      {/* Header: Counter + Toggle */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-2xl font-bold text-slate-900">
            {data ? `${data.gaps_count} L\u00fccken` : "\u2014"}
          </div>
          {data && data.gaps_count > 0 && (
            <div className="mt-1 flex items-center gap-2 flex-wrap text-xs text-slate-500">
              {data.missing_count > 0 && (
                <span>{data.missing_count} fehlen</span>
              )}
              {data.low_confidence_count > 0 && (
                <>
                  <span>·</span>
                  <span>{data.low_confidence_count} unsicher</span>
                </>
              )}
              {data.estimated_count > 0 && (
                <>
                  <span>·</span>
                  <span>{data.estimated_count} Richtwerte</span>
                </>
              )}
            </div>
          )}
        </div>
        <label className="flex items-start gap-2 cursor-pointer text-sm text-slate-700">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-bauplan-600 focus:ring-bauplan-500"
            checked={includeLowConfidence}
            disabled={loading}
            onChange={(e) => setIncludeLowConfidence(e.target.checked)}
            data-testid="toggle-low-confidence"
          />
          <span>Unsichere Matches einbeziehen</span>
        </label>
      </div>

      {/* Loading */}
      {loading && (
        <div data-testid="gaps-loading" className="space-y-2">
          <div className="h-14 rounded-lg bg-slate-100 animate-pulse" />
          <div className="h-14 rounded-lg bg-slate-100 animate-pulse" />
          <div className="h-14 rounded-lg bg-slate-100 animate-pulse" />
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div
          role="alert"
          data-testid="gaps-error"
          className="rounded-lg border border-danger-500/30 bg-danger-500/5 p-4 space-y-2"
        >
          <div className="text-sm font-medium text-danger-600">
            Lücken konnten nicht geladen werden.
          </div>
          <div className="text-xs text-slate-500">{error}</div>
          <Button variant="secondary" size="sm" onClick={load}>
            Erneut versuchen
          </Button>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && data && data.gaps_count === 0 && (
        <div
          data-testid="gaps-empty"
          className="flex items-center gap-3 rounded-lg border border-success-500/30 bg-success-500/5 p-4"
        >
          <CheckCircle2 className="w-6 h-6 text-success-500 shrink-0" />
          <div className="text-sm text-slate-900">
            Alle Materialien haben einen Preis.
          </div>
        </div>
      )}

      {/* Loaded: Liste */}
      {!loading && !error && data && data.gaps_count > 0 && (
        <div className="space-y-2">
          {data.gaps.map((gap, i) => (
            <GapRow
              key={`${gap.position_id}-${gap.material_dna || i}`}
              gap={gap}
              onOpen={() => onOpenPosition(gap.position_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default CatalogGapsPanel;
