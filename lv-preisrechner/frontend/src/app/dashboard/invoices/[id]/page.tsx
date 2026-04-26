"use client";

/**
 * B+4.13 — Invoice-Detail-Seite.
 *
 * Header: Invoice-Nr, Status, Faelligkeit, Betraege.
 * Body:   Zahlungs-Sektion + Mahnungs-Sektion + History.
 * Aktionen: Versenden, Zahlung erfassen, Mahnung erstellen, PDFs.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Banknote,
  Bell,
  Download,
  Loader2,
  Mail,
  Send,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { InvoiceStatusBadge } from "@/components/InvoiceStatusBadge";
import {
  Dunning,
  InvoiceDetail,
  InvoiceStatus,
  invoicesApi,
} from "@/lib/tenantApi";
import { LV, api } from "@/lib/api";
import { fmtDate, fmtEur } from "@/lib/format";

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [lv, setLv] = useState<LV | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // Payment Form
  const [payAmount, setPayAmount] = useState("");
  const [payDate, setPayDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [payNote, setPayNote] = useState("");

  async function load() {
    setLoading(true);
    try {
      const inv = await invoicesApi.get(id);
      setInvoice(inv);
      const lvData = await api<LV>(`/lvs/${inv.lv_id}`).catch(() => null);
      setLv(lvData);
    } catch (e: any) {
      toast.error(e?.detail || "Rechnung nicht gefunden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function patchStatus(status: InvoiceStatus, reason?: string) {
    setBusy(true);
    try {
      await invoicesApi.updateStatus(id, { status, reason });
      toast.success("Status aktualisiert");
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Status-Wechsel fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function recordPayment() {
    const amount = Number(payAmount);
    if (!amount || amount <= 0) {
      toast.error("Bitte einen Betrag größer 0 eingeben");
      return;
    }
    setBusy(true);
    try {
      await invoicesApi.recordPayment(id, {
        amount,
        payment_date: payDate || undefined,
        note: payNote.trim() || undefined,
      });
      toast.success(`Zahlung über ${fmtEur(amount)} erfasst`);
      setPayAmount("");
      setPayNote("");
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Zahlung konnte nicht erfasst werden");
    } finally {
      setBusy(false);
    }
  }

  async function createDunning() {
    setBusy(true);
    try {
      const d = await invoicesApi.createDunning(id, {});
      toast.success(`Mahnung Stufe ${d.dunning_level} erstellt`);
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Mahnung-Erstellung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function downloadPdf(url: string, filename: string) {
    try {
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("lvp_token") ?? ""}`,
        },
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = u;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(u);
    } catch {
      toast.error("PDF-Download fehlgeschlagen");
    }
  }

  async function emailDraft() {
    try {
      const draft = await invoicesApi.emailDraft(id);
      window.location.href = draft.mailto;
    } catch {
      toast.error("E-Mail-Compose fehlgeschlagen");
    }
  }

  if (loading || !invoice) {
    return <div className="text-slate-500 py-20 text-center">Lade…</div>;
  }

  const offen =
    Number(invoice.betrag_brutto) - Number(invoice.paid_amount || 0);
  const isOverdue = invoice.status === "overdue";
  const isFinal = invoice.status === "paid" || invoice.status === "cancelled";

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/dashboard/lvs/${invoice.lv_id}`}
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-bauplan-600"
        >
          <ArrowLeft className="w-4 h-4" /> Zurück zum LV
        </Link>
      </div>

      <header className="rounded-xl bg-white border border-slate-200 p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-slate-900">
              <span className="font-mono">{invoice.invoice_number}</span>
            </h1>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <InvoiceStatusBadge status={invoice.status} />
              <span className="text-sm text-slate-600">
                {invoice.invoice_type === "abschlagsrechnung"
                  ? "Abschlagsrechnung"
                  : "Schlussrechnung"}
              </span>
              {lv && (
                <span className="text-sm text-slate-500">
                  · LV: {lv.projekt_name}
                </span>
              )}
            </div>
            <div className="mt-2 text-sm text-slate-500 flex flex-wrap gap-x-4">
              <span>Rechnungsdatum: {fmtDate(invoice.invoice_date)}</span>
              {invoice.sent_date && <span>Versendet: {fmtDate(invoice.sent_date)}</span>}
              {invoice.due_date && (
                <span className={isOverdue ? "text-danger-600 font-medium" : ""}>
                  Fällig: {fmtDate(invoice.due_date)}
                </span>
              )}
              {invoice.paid_date && (
                <span>Bezahlt: {fmtDate(invoice.paid_date)}</span>
              )}
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-500">Brutto</div>
            <div className="text-3xl font-bold text-slate-900">
              {fmtEur(invoice.betrag_brutto)}
            </div>
            <div className="text-xs text-slate-500">
              Netto {fmtEur(invoice.betrag_netto)} · USt {fmtEur(invoice.betrag_ust)}
            </div>
            {invoice.paid_amount > 0 && (
              <div className="mt-2 text-xs">
                <span className="text-slate-500">Gezahlt: </span>
                <span className="font-medium text-success-600">
                  {fmtEur(invoice.paid_amount)}
                </span>
                {offen > 0.005 && (
                  <span className="ml-2 text-danger-600 font-medium">
                    Offen: {fmtEur(offen)}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Action-Bar */}
        <div className="mt-4 flex items-center gap-2 flex-wrap pt-3 border-t border-slate-100">
          <Button
            size="sm"
            variant="secondary"
            onClick={() =>
              downloadPdf(invoicesApi.pdfUrl(id), `${invoice.invoice_number}.pdf`)
            }
          >
            <Download className="w-4 h-4" /> Rechnungs-PDF
          </Button>
          {!isFinal && invoice.status === "draft" && (
            <Button size="sm" onClick={() => patchStatus("sent")} disabled={busy}>
              <Send className="w-4 h-4" /> Als versendet markieren
            </Button>
          )}
          {!isFinal && invoice.status !== "draft" && (
            <Button size="sm" variant="ghost" onClick={emailDraft}>
              <Mail className="w-4 h-4" /> E-Mail vorbereiten
            </Button>
          )}
          {isOverdue && invoice.dunnings.length < 3 && (
            <Button
              size="sm"
              variant="primary"
              onClick={createDunning}
              disabled={busy}
            >
              <Bell className="w-4 h-4" /> Mahnung Stufe {invoice.dunnings.length + 1} erstellen
            </Button>
          )}
          {!isFinal && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                patchStatus("cancelled", "manuell storniert")
              }
              disabled={busy}
            >
              <X className="w-4 h-4" /> Stornieren
            </Button>
          )}
        </div>
      </header>

      {isOverdue && (
        <div className="rounded-md bg-danger-500/10 border border-danger-500/20 px-4 py-3 text-sm text-danger-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          Diese Rechnung ist überfällig.
          {invoice.due_date && ` Fälligkeit ${fmtDate(invoice.due_date)} überschritten.`}
        </div>
      )}

      {/* Zahlungen */}
      <section className="rounded-xl bg-white border border-slate-200 p-5">
        <h2 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
          <Banknote className="w-4 h-4 text-slate-500" /> Zahlungen
        </h2>
        <PaymentList invoice={invoice} />
        {!isFinal && invoice.status !== "draft" && offen > 0.005 && (
          <div className="mt-4 grid sm:grid-cols-3 gap-2">
            <input
              type="number"
              step="0.01"
              min={0}
              max={offen}
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              placeholder={`Betrag (offen: ${fmtEur(offen)})`}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bauplan-500"
            />
            <input
              type="date"
              value={payDate}
              onChange={(e) => setPayDate(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              type="text"
              value={payNote}
              onChange={(e) => setPayNote(e.target.value)}
              placeholder="Notiz (optional)"
              maxLength={500}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <div className="sm:col-span-3 flex justify-end">
              <Button onClick={recordPayment} disabled={busy}>
                {busy && <Loader2 className="w-4 h-4 animate-spin" />}
                <Banknote className="w-4 h-4" /> Zahlung erfassen
              </Button>
            </div>
          </div>
        )}
      </section>

      {/* Mahnungen */}
      {invoice.dunnings.length > 0 && (
        <section className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <Bell className="w-4 h-4 text-slate-500" /> Mahnungen
            <span className="text-sm text-slate-400">
              ({invoice.dunnings.length})
            </span>
          </h2>
          <ul className="space-y-2">
            {invoice.dunnings.map((d) => (
              <DunningRow
                key={d.id}
                d={d}
                onDownload={() =>
                  downloadPdf(
                    invoicesApi.dunningPdfUrl(id, d.id),
                    `Mahnung-Stufe${d.dunning_level}-${invoice.invoice_number}.pdf`,
                  )
                }
              />
            ))}
          </ul>
        </section>
      )}

      {/* Status-History */}
      {invoice.status_history.length > 0 && (
        <section className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Status-Verlauf</h2>
          <ul className="space-y-1.5">
            {invoice.status_history.map((h) => (
              <li
                key={h.id}
                className="text-xs text-slate-600 flex items-baseline gap-2"
              >
                <span className="text-slate-400 font-mono whitespace-nowrap">
                  {fmtDate(h.changed_at)}
                </span>
                <span className="text-slate-500">
                  {h.old_status ? `${h.old_status} →` : "neu →"}
                </span>
                <span className="font-medium text-slate-900">
                  {h.new_status}
                </span>
                {h.reason && (
                  <span className="text-slate-500 italic">— {h.reason}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function PaymentList({ invoice }: { invoice: InvoiceDetail }) {
  // Zahlungen werden im Audit-Trail mit reason="payment:..." erfasst
  const payments = invoice.status_history.filter(
    (h) => h.reason && h.reason.startsWith("payment:"),
  );
  if (payments.length === 0) {
    return (
      <p className="text-sm text-slate-400">Noch keine Zahlung erfasst.</p>
    );
  }
  return (
    <ul className="space-y-1.5 text-sm">
      {payments.map((h) => {
        const m = h.reason!.match(/payment:([0-9.]+)\s+cumulative:([0-9.]+)/);
        const amount = m ? Number(m[1]) : null;
        const cumulative = m ? Number(m[2]) : null;
        return (
          <li
            key={h.id}
            className="flex items-baseline justify-between gap-2 border-b border-slate-100 pb-1.5 last:border-b-0"
          >
            <span className="text-slate-500 text-xs font-mono">
              {fmtDate(h.changed_at)}
            </span>
            <span className="text-slate-700 flex-1 truncate">
              {amount !== null ? fmtEur(amount) : "Zahlung"}
            </span>
            {cumulative !== null && (
              <span className="text-xs text-slate-500">
                Σ {fmtEur(cumulative)}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function DunningRow({
  d,
  onDownload,
}: {
  d: Dunning;
  onDownload: () => void;
}) {
  const titleByLevel: Record<number, string> = {
    1: "Zahlungserinnerung",
    2: "Mahnung",
    3: "Letzte Mahnung",
  };
  const colorByLevel: Record<number, string> = {
    1: "bg-warning-500/10 text-warning-700 border-warning-500/30",
    2: "bg-danger-500/10 text-danger-700 border-danger-500/30",
    3: "bg-danger-700 text-white border-danger-700",
  };
  return (
    <li
      className={
        "flex items-center justify-between gap-3 rounded-lg border p-3 " +
        colorByLevel[d.dunning_level]
      }
    >
      <div>
        <div className="font-medium">
          Stufe {d.dunning_level} — {titleByLevel[d.dunning_level] ?? "Mahnung"}
        </div>
        <div className="text-xs opacity-80">
          Mahnungsdatum: {fmtDate(d.dunning_date)} · Frist: {fmtDate(d.due_date)}
          {d.mahngebuehr_betrag > 0 &&
            ` · Mahngebühr ${fmtEur(d.mahngebuehr_betrag)}`}
        </div>
      </div>
      <Button size="sm" variant="ghost" onClick={onDownload}>
        <Download className="w-4 h-4" /> PDF
      </Button>
    </li>
  );
}
