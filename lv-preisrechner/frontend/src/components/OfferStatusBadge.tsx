"use client";

/**
 * B+4.11 — Offer-Status-Badge mit konsistenter Farb-Codierung.
 *
 * Mapping:
 *   draft        -> default (grau)
 *   sent         -> info (blau)
 *   accepted     -> success (gruen)
 *   rejected     -> danger (rot)
 *   negotiating  -> warning (orange)
 *   expired      -> default + dunkler Tone
 */
import { Badge } from "@/components/ui/badge";
import { OFFER_STATUS_LABELS, OfferStatus } from "@/lib/tenantApi";

type Variant = "default" | "success" | "warning" | "danger" | "info";

const VARIANT_BY_STATUS: Record<OfferStatus, Variant> = {
  draft: "default",
  sent: "info",
  accepted: "success",
  rejected: "danger",
  negotiating: "warning",
  expired: "default",
};

export function OfferStatusBadge({ status }: { status: string }) {
  const variant = VARIANT_BY_STATUS[status as OfferStatus] ?? "default";
  const label =
    OFFER_STATUS_LABELS[status as OfferStatus] ?? status;
  // Expired bekommt dunkleren Tone — einfach via className-Override.
  const isExpired = status === "expired";
  return (
    <Badge
      variant={variant}
      className={isExpired ? "!bg-slate-300 !text-slate-700" : undefined}
    >
      {label}
    </Badge>
  );
}
