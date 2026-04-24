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
import { ArrowRight, CheckCircle2, SkipForward, Tag } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  CatalogGapEntry,
  GapSeverity,
  LVGapsReport,
  UniqueMissingMaterial,
  fetchGaps,
  resolveGap,
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

      {/* B+4.6 — Unique-Missing-Resolver: gruppiert pro Material-DNA */}
      {!loading &&
        !error &&
        data &&
        data.unique_missing_materials &&
        data.unique_missing_materials.length > 0 && (
          <UniqueMissingResolver
            lvId={lvId}
            items={data.unique_missing_materials}
            onResolved={load}
          />
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


// -------------------------------------------------------------------
// B+4.6 — UniqueMissingResolver: pro Material-DNA eine Karte mit
//          Preis-manuell-setzen + Ueberspringen
// -------------------------------------------------------------------
type ManualPriceState = {
  dna: string;
  name: string;
  unit: string;
  price: string;
} | null;

function UniqueMissingResolver({
  lvId,
  items,
  onResolved,
}: {
  lvId: string;
  items: UniqueMissingMaterial[];
  onResolved: () => void;
}) {
  const [pending, setPending] = useState<string | null>(null); // material_dna in-flight
  const [manual, setManual] = useState<ManualPriceState>(null);

  async function doResolve(
    dna: string,
    type: "skip" | "manual_price",
    value: Record<string, unknown>,
  ) {
    setPending(dna);
    try {
      const res = await resolveGap(lvId, {
        material_dna: dna,
        resolution_type: type,
        value,
      });
      toast.success(
        type === "skip"
          ? "Übersprungen — Position bleibt bei EP 0."
          : res.recalculated
            ? "Preis gesetzt + LV neu kalkuliert."
            : "Preis gesetzt.",
      );
      onResolved();
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail;
      toast.error(detail || (e instanceof Error ? e.message : "Fehler"));
    } finally {
      setPending(null);
    }
  }

  async function submitManual() {
    if (!manual) return;
    const n = Number.parseFloat(manual.price.replace(",", "."));
    if (!Number.isFinite(n) || n <= 0) {
      toast.error("Bitte einen gültigen Preis > 0 eingeben.");
      return;
    }
    await doResolve(manual.dna, "manual_price", {
      price_net: n,
      unit: manual.unit.trim() || "Stk",
    });
    setManual(null);
  }

  return (
    <div className="space-y-2">
      <div className="text-sm font-semibold text-slate-900">
        Zum Beheben ({items.length} Material{items.length === 1 ? "" : "ien"})
      </div>
      {items.map((it) => {
        const isPending = pending === it.material_dna;
        return (
          <div
            key={it.material_dna}
            className="rounded-lg border border-slate-200 bg-slate-50/40 p-3"
          >
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="font-medium text-slate-900 truncate">
                  {it.material_name || it.material_dna}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {it.betroffene_positionen.length} Position
                  {it.betroffene_positionen.length === 1 ? "" : "en"}{" "}
                  betroffen · {it.total_required_amount.toFixed(2)} {it.unit}
                </div>
                <div className="mt-1 text-xs text-slate-400 truncate max-w-xl">
                  OZ: {it.betroffene_positionen.join(", ")}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  variant="primary"
                  size="sm"
                  disabled={isPending}
                  onClick={() =>
                    setManual({
                      dna: it.material_dna,
                      name: it.material_name,
                      unit: it.unit || "Stk",
                      price: "",
                    })
                  }
                >
                  <Tag className="w-4 h-4 mr-1" /> Preis setzen
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={isPending}
                  onClick={() => doResolve(it.material_dna, "skip", {})}
                >
                  <SkipForward className="w-4 h-4 mr-1" /> Überspringen
                </Button>
              </div>
            </div>
          </div>
        );
      })}

      <Dialog
        open={manual !== null}
        onClose={() => setManual(null)}
        title="Manuellen Preis setzen"
        description={
          manual
            ? `${manual.name} — wird als Tenant-Override gespeichert und gilt ab sofort für alle LVs.`
            : undefined
        }
        actions={[
          { label: "Abbrechen", variant: "ghost", autoClose: true },
          {
            label: "Speichern",
            variant: "primary",
            autoClose: false,
            onClick: submitManual,
          },
        ]}
      >
        {manual && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="gap-price">Preis (netto)</Label>
              <Input
                id="gap-price"
                inputMode="decimal"
                value={manual.price}
                onChange={(e) =>
                  setManual({ ...manual, price: e.target.value })
                }
                placeholder="z.B. 2,87"
              />
            </div>
            <div>
              <Label htmlFor="gap-unit">Einheit</Label>
              <Input
                id="gap-unit"
                value={manual.unit}
                onChange={(e) => setManual({ ...manual, unit: e.target.value })}
                placeholder="z.B. lfm, m², Stk"
              />
            </div>
            <p className="text-xs text-slate-500">
              Das LV wird anschließend automatisch neu kalkuliert.
            </p>
          </div>
        )}
      </Dialog>
    </div>
  );
}

export default CatalogGapsPanel;
