"use client";

/**
 * B+4.13 — Finanzen-Cockpit.
 *
 * Vier Kennzahl-Karten (Offen / Überfällig / Gezahlt / Diese Woche)
 * + Tabelle der überfälligen Rechnungen mit Mahn-Schnellaktion
 * + Tabelle aller offenen Rechnungen sortiert nach Fälligkeit.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock,
  Receipt,
  Wallet,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { InvoiceStatusBadge } from "@/components/InvoiceStatusBadge";
import {
  FinanceOverview,
  Invoice,
  OverdueInvoiceRow,
  financeApi,
  invoicesApi,
} from "@/lib/tenantApi";
import { api } from "@/lib/api";
import { fmtDate, fmtEur } from "@/lib/format";

export default function FinanzenPage() {
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [overdue, setOverdue] = useState<OverdueInvoiceRow[]>([]);
  const [openInvoices, setOpenInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      // Erst overdue-Check ausfuehren (Auto-Markierung) — danach Daten laden
      await financeApi.checkOverdue().catch(() => null);
      const [ov, od, all] = await Promise.all([
        financeApi.overview(),
        financeApi.overdueInvoices(),
        api<Invoice[]>("/invoices?_=" + Date.now()).catch(() => null),
      ]);
      setOverview(ov);
      setOverdue(od);
      // Backend hat keinen GET /invoices direkt — daher aus overdue + manuelle
      // Liste pro LV. Stattdessen: alle offenen aus overdue + abgeleitet.
      // Vereinfachung: nur overdue-Liste. Open total kann aus overview gelesen
      // werden. Wenn Backend spaeter Tenant-weiten /invoices-Endpoint
      // bekommt, kann hier erweitert werden.
      setOpenInvoices([]);
    } catch (e: any) {
      toast.error(e?.detail || "Finanz-Daten konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function quickDun(invoiceId: string) {
    setBusy(true);
    try {
      const d = await invoicesApi.createDunning(invoiceId, {});
      toast.success(`Mahnung Stufe ${d.dunning_level} erstellt`);
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Mahnung-Erstellung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !overview) {
    return <div className="text-slate-500 py-20 text-center">Lade Finanz-Cockpit…</div>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-slate-900">Finanzen</h1>
        <p className="text-slate-600 mt-1">
          Überblick über offene und überfällige Rechnungen.
        </p>
      </header>

      <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          icon={<Receipt className="w-5 h-5" />}
          label="Offene Rechnungen"
          value={String(overview.offene_rechnungen_count)}
          sub={fmtEur(overview.offene_summe_brutto)}
          tone="info"
        />
        <KpiCard
          icon={<AlertTriangle className="w-5 h-5" />}
          label="Überfällig"
          value={String(overview.ueberfaellige_count)}
          sub={fmtEur(overview.ueberfaellige_summe_brutto)}
          tone={overview.ueberfaellige_count > 0 ? "danger" : "default"}
        />
        <KpiCard
          icon={<CheckCircle2 className="w-5 h-5" />}
          label={`Gezahlt ${overview.year}`}
          value={fmtEur(overview.gezahlte_summe_jahr_aktuell)}
          tone="success"
        />
        <KpiCard
          icon={<Wallet className="w-5 h-5" />}
          label="Cashflow Woche"
          value="—"
          sub="Demnächst"
          tone="default"
        />
      </section>

      {overdue.length > 0 && (
        <section className="rounded-xl bg-white border border-danger-500/20 p-5">
          <header className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-danger-600" />
            <h2 className="text-lg font-semibold text-slate-900">
              Überfällige Rechnungen
            </h2>
            <span className="text-sm text-slate-400">
              ({overdue.length})
            </span>
          </header>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-600 bg-slate-50">
                <tr>
                  <Th>Rechnung</Th>
                  <Th>Fällig seit</Th>
                  <Th className="text-right">Tage</Th>
                  <Th className="text-right">Offen</Th>
                  <Th className="text-center">Mahnstufe</Th>
                  <Th></Th>
                </tr>
              </thead>
              <tbody>
                {overdue.map((row) => (
                  <tr
                    key={row.id}
                    className="border-t border-slate-100 hover:bg-slate-50"
                  >
                    <Td>
                      <Link
                        href={`/dashboard/invoices/${row.id}`}
                        className="font-mono font-semibold text-slate-900 hover:text-bauplan-600"
                      >
                        {row.invoice_number}
                      </Link>
                    </Td>
                    <Td className="text-slate-600">
                      {row.due_date ? fmtDate(row.due_date) : "—"}
                    </Td>
                    <Td className="text-right tabular-nums text-danger-600 font-medium">
                      {row.days_overdue ?? "—"}
                    </Td>
                    <Td className="text-right tabular-nums font-medium">
                      {fmtEur(row.open_amount)}
                    </Td>
                    <Td className="text-center">
                      {row.highest_dunning_level === 0 ? (
                        <span className="text-xs text-slate-400">Keine</span>
                      ) : (
                        <span className="text-xs font-medium">
                          Stufe {row.highest_dunning_level}
                        </span>
                      )}
                    </Td>
                    <Td className="text-right">
                      {row.highest_dunning_level < 3 && (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => quickDun(row.id)}
                          disabled={busy}
                        >
                          <Bell className="w-4 h-4" />
                          Stufe {row.highest_dunning_level + 1}
                        </Button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {overdue.length === 0 && overview.offene_rechnungen_count === 0 && (
        <section className="rounded-xl bg-white border border-slate-200 p-10 text-center">
          <Clock className="w-10 h-10 text-slate-400 mx-auto" />
          <p className="text-slate-600 mt-3">Keine offenen Rechnungen.</p>
          <p className="text-xs text-slate-500 mt-1">
            Sobald Sie Rechnungen aus angenommenen Angeboten erstellen, erscheint
            hier eine Übersicht.
          </p>
        </section>
      )}
    </div>
  );
}

function KpiCard({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  tone: "default" | "info" | "success" | "warning" | "danger";
}) {
  const tones: Record<typeof tone, string> = {
    default: "bg-white border-slate-200",
    info: "bg-bauplan-50 border-bauplan-100",
    success: "bg-success-500/5 border-success-500/20",
    warning: "bg-warning-500/5 border-warning-500/20",
    danger: "bg-danger-500/5 border-danger-500/30",
  };
  const iconTones: Record<typeof tone, string> = {
    default: "text-slate-500",
    info: "text-bauplan-600",
    success: "text-success-600",
    warning: "text-warning-600",
    danger: "text-danger-600",
  };
  return (
    <div className={"rounded-xl border p-4 " + tones[tone]}>
      <div className={"flex items-center gap-2 " + iconTones[tone]}>
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">
          {label}
        </span>
      </div>
      <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </div>
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
    <th className={`text-left px-4 py-2.5 font-medium ${className}`}>
      {children}
    </th>
  );
}
function Td({
  children,
  className = "",
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return <td className={`px-4 py-2.5 text-slate-700 ${className}`}>{children}</td>;
}
