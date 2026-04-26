"use client";

/**
 * B+4.13 — Invoice-Status-Badge mit konsistenter Farb-Codierung.
 *
 *   draft           -> default (grau)
 *   sent            -> info (blau)
 *   paid            -> success (gruen)
 *   partially_paid  -> warning (orange)
 *   overdue         -> danger (rot)
 *   cancelled       -> default + dunkler
 */
import { Badge } from "@/components/ui/badge";
import { INVOICE_STATUS_LABELS, InvoiceStatus } from "@/lib/tenantApi";

type Variant = "default" | "success" | "warning" | "danger" | "info";

const VARIANT_BY_STATUS: Record<InvoiceStatus, Variant> = {
  draft: "default",
  sent: "info",
  paid: "success",
  partially_paid: "warning",
  overdue: "danger",
  cancelled: "default",
};

export function InvoiceStatusBadge({ status }: { status: string }) {
  const variant = VARIANT_BY_STATUS[status as InvoiceStatus] ?? "default";
  const label = INVOICE_STATUS_LABELS[status as InvoiceStatus] ?? status;
  const isCancelled = status === "cancelled";
  return (
    <Badge
      variant={variant}
      className={isCancelled ? "!bg-slate-300 !text-slate-700" : undefined}
    >
      {label}
    </Badge>
  );
}
