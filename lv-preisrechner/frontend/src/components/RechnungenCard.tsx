"use client";

/**
 * B+4.13 — Rechnungen-Karte fuer LV-Detail-Seite.
 *
 * Zeigt Rechnungen pro LV. Wenn ein accepted Final-Offer (oder draft
 * aufmass_basiert) existiert, kann pro Klick eine Rechnung daraus
 * angelegt werden.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { Download, FilePlus2, Receipt } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { InvoiceStatusBadge } from "@/components/InvoiceStatusBadge";
import {
  Invoice,
  Offer,
  invoicesApi,
  offersApi,
} from "@/lib/tenantApi";
import { fmtDate, fmtEur } from "@/lib/format";

export function RechnungenCard({ lvId }: { lvId: string }) {
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [eligibleOffers, setEligibleOffers] = useState<Offer[]>([]);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [inv, offers] = await Promise.all([
        invoicesApi.listForLv(lvId),
        offersApi.listForLv(lvId).catch(() => [] as Offer[]),
      ]);
      setInvoices(inv);
      // Akzeptierte Offers oder draft Final-Offers (aufmass_basiert)
      // koennen fakturiert werden.
      setEligibleOffers(
        offers.filter(
          (o) =>
            o.status === "accepted" ||
            (o.status === "draft" && o.pdf_format === "aufmass_basiert"),
        ),
      );
    } catch (e: any) {
      toast.error(e?.detail || "Rechnungen konnten nicht geladen werden");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lvId]);

  async function createFromOffer(offer: Offer) {
    setBusy(true);
    try {
      const inv = await invoicesApi.createFromOffer(offer.id, {});
      toast.success(`Rechnung ${inv.invoice_number} erstellt`);
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Rechnungs-Erstellung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  // Wenn keine Offers fakturierbar sind und keine Rechnungen existieren:
  // Karte ausblenden — lenkt nicht ab.
  if (
    invoices !== null &&
    invoices.length === 0 &&
    eligibleOffers.length === 0
  ) {
    return null;
  }

  return (
    <section className="rounded-xl bg-white border border-slate-200 p-5">
      <header className="flex items-center justify-between gap-2 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-slate-500" />
          <h2 className="text-lg font-semibold text-slate-900">Rechnungen</h2>
          {invoices && (
            <span className="text-sm text-slate-400">({invoices.length})</span>
          )}
        </div>
      </header>

      {invoices === null ? (
        <div className="text-slate-500 text-sm">Lade…</div>
      ) : invoices.length === 0 ? (
        <div className="text-center py-4">
          <p className="text-sm text-slate-600">Noch keine Rechnung erstellt.</p>
          <p className="text-xs text-slate-500 mt-1">
            Aus einem akzeptierten Angebot oder einem Final-Angebot lässt sich
            direkt eine Schlussrechnung erzeugen.
          </p>
        </div>
      ) : (
        <ul className="space-y-2 mb-3">
          {invoices.map((inv) => (
            <li
              key={inv.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 p-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link
                    href={`/dashboard/invoices/${inv.id}`}
                    className="font-mono font-semibold text-slate-900 hover:text-bauplan-600"
                  >
                    {inv.invoice_number}
                  </Link>
                  <InvoiceStatusBadge status={inv.status} />
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Datum: {fmtDate(inv.invoice_date)}
                  {inv.due_date && ` · Fällig: ${fmtDate(inv.due_date)}`}
                  {inv.paid_date && ` · Bezahlt: ${fmtDate(inv.paid_date)}`}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-semibold text-slate-900">
                  {fmtEur(inv.betrag_brutto)}
                </div>
                {inv.paid_amount > 0 && inv.status !== "paid" && (
                  <div className="text-xs text-slate-500">
                    Gez.: {fmtEur(inv.paid_amount)}
                  </div>
                )}
                <a
                  href={invoicesApi.pdfUrl(inv.id)}
                  className="text-xs text-bauplan-600 hover:underline inline-flex items-center gap-1 mt-1"
                  download
                  onClick={async (e) => {
                    e.preventDefault();
                    const res = await fetch(invoicesApi.pdfUrl(inv.id), {
                      headers: {
                        Authorization: `Bearer ${localStorage.getItem("lvp_token") ?? ""}`,
                      },
                    });
                    if (!res.ok) {
                      toast.error("PDF nicht verfügbar");
                      return;
                    }
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${inv.invoice_number}.pdf`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  <Download className="w-3 h-3" /> PDF
                </a>
              </div>
            </li>
          ))}
        </ul>
      )}

      {eligibleOffers.length > 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 p-3">
          <p className="text-xs text-slate-500 mb-2">
            Aus Angebot fakturieren:
          </p>
          <div className="flex flex-wrap gap-2">
            {eligibleOffers.map((o) => (
              <Button
                key={o.id}
                size="sm"
                variant="primary"
                disabled={busy}
                onClick={() => createFromOffer(o)}
              >
                <FilePlus2 className="w-4 h-4" />
                Rechnung aus {o.offer_number}
              </Button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
