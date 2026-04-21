import { Badge } from "@/components/ui/badge";

/**
 * Stage-Badge fuer `Position.price_source_summary` (B+4.3.1).
 *
 * Der Backend-String hat die Form "2x supplier_price, 1x estimated"
 * oder "1x legacy" — von `summarize_sources` in price_resolution.py.
 *
 * Ampel-Regel (Worst-Case gewinnt):
 *   not_found    -> rot       "Keine Preisquelle"
 *   estimated    -> gelb      "Schätzwert"
 *   override     -> blau      "Manuell"
 *   supplier_price only -> grün "Lieferantenpreis"
 *   legacy       -> grau      "Altpreis"
 *
 * Bei gemischten Stages (> 1 Quelle in summary) bekommt der Badge die
 * volle summary als Tooltip (title-Attribut), damit das Detail
 * abrufbar ist, ohne das Layout zu belasten.
 */
export type StageVariant = "default" | "success" | "warning" | "danger" | "info";

export type StageKind =
  | "not_found"
  | "estimated"
  | "override"
  | "supplier_price"
  | "legacy"
  | "unknown";

const LABELS: Record<StageKind, string> = {
  not_found: "Keine Preisquelle",
  estimated: "Schätzwert",
  override: "Manuell",
  supplier_price: "Lieferantenpreis",
  legacy: "Altpreis",
  unknown: "—",
};

const VARIANTS: Record<StageKind, StageVariant> = {
  not_found: "danger",
  estimated: "warning",
  override: "info",
  supplier_price: "success",
  legacy: "default",
  unknown: "default",
};

/**
 * Worst-Case-Klassifikation einer Summary.
 * Reihenfolge der Prüfung: not_found > estimated > override > supplier_price > legacy.
 */
export function classifySummary(summary: string | undefined): StageKind {
  if (!summary) return "unknown";
  const s = summary.toLowerCase();
  if (s.includes("not_found")) return "not_found";
  if (s.includes("estimated")) return "estimated";
  if (s.includes("override")) return "override";
  if (s.includes("supplier_price")) return "supplier_price";
  if (s.includes("legacy")) return "legacy";
  return "unknown";
}

export function StageBadge({
  summary,
  className,
}: {
  summary: string | undefined;
  className?: string;
}) {
  const kind = classifySummary(summary);
  const label = LABELS[kind];
  const variant = VARIANTS[kind];
  // Detail-Tooltip nur anzeigen, wenn die Summary mehr als eine Stage enthält.
  const hasMixed = summary ? summary.split(",").length > 1 : false;
  const title = hasMixed && summary ? summary : undefined;
  return (
    <Badge variant={variant} className={className} title={title}>
      {label}
    </Badge>
  );
}

export default StageBadge;
