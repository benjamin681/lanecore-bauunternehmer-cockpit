"use client";

/**
 * B+4.9 Iteration 2 — Customer-Detail.
 * Zeigt Kunden-Stammdaten und alle Projekte des Kunden.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, FolderOpen } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import {
  Customer,
  Project,
  PROJECT_STATUS_LABELS,
  customersApi,
  projectsApi,
} from "@/lib/tenantApi";
import { fmtDate } from "@/lib/format";

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const customerId = params?.id;

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!customerId) return;
    let active = true;
    (async () => {
      try {
        const [c, ps] = await Promise.all([
          customersApi.get(customerId),
          projectsApi.list({ customer_id: customerId }).catch(() => [] as Project[]),
        ]);
        if (!active) return;
        setCustomer(c);
        setProjects(ps);
      } catch (e) {
        toast.error("Kunde konnte nicht geladen werden");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [customerId]);

  if (loading || !customer) {
    return <div className="text-slate-500 py-20 text-center">Lade…</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/customers"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-bauplan-600"
        >
          <ArrowLeft className="w-4 h-4" /> Kunden
        </Link>
      </div>

      <header>
        <h1 className="text-3xl font-bold text-slate-900">{customer.name}</h1>
        {customer.contact_person && (
          <p className="text-slate-600 mt-1">{customer.contact_person}</p>
        )}
      </header>

      <section className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Kontakt</h2>
          <dl className="text-sm text-slate-700 space-y-1.5">
            {customer.email && (
              <Row label="E-Mail">
                <a
                  href={`mailto:${customer.email}`}
                  className="text-bauplan-600 hover:underline"
                >
                  {customer.email}
                </a>
              </Row>
            )}
            {customer.phone && <Row label="Telefon">{customer.phone}</Row>}
            {!customer.email && !customer.phone && (
              <p className="text-sm text-slate-400">
                Keine Kontaktdaten hinterlegt.
              </p>
            )}
          </dl>
        </div>

        <div className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Adresse</h2>
          {customer.address_street ||
          customer.address_zip ||
          customer.address_city ? (
            <div className="text-sm text-slate-700 space-y-0.5">
              {customer.address_street && <div>{customer.address_street}</div>}
              {(customer.address_zip || customer.address_city) && (
                <div>
                  {customer.address_zip} {customer.address_city}
                </div>
              )}
              {customer.address_country &&
                customer.address_country !== "DE" && (
                  <div className="text-slate-500">{customer.address_country}</div>
                )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Keine Adresse hinterlegt.</p>
          )}
        </div>
      </section>

      {customer.notes && (
        <section className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-2">Notizen</h2>
          <p className="text-sm text-slate-600 whitespace-pre-wrap">
            {customer.notes}
          </p>
        </section>
      )}

      <section>
        <h2 className="font-semibold text-slate-900 mb-3">
          Projekte{" "}
          <span className="text-slate-400 font-normal">
            ({projects?.length ?? 0})
          </span>
        </h2>
        {!projects || projects.length === 0 ? (
          <div className="rounded-xl bg-white border border-slate-200 p-10 text-center">
            <FolderOpen className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-slate-600 mt-3">Noch keine Projekte für diesen Kunden.</p>
          </div>
        ) : (
          <div className="rounded-xl bg-white border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <Th>Projekt</Th>
                    <Th>Status</Th>
                    <Th>Letztes Update</Th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((p) => (
                    <tr
                      key={p.id}
                      className="border-t border-slate-100 hover:bg-slate-50"
                    >
                      <Td>
                        <Link
                          href={`/dashboard/projects/${p.id}`}
                          className="font-medium text-slate-900 hover:text-bauplan-600"
                        >
                          {p.name}
                        </Link>
                      </Td>
                      <Td>
                        <StatusBadge status={p.status} />
                      </Td>
                      <Td className="text-slate-500">{fmtDate(p.updated_at)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <dt className="w-24 shrink-0 text-slate-500">{label}</dt>
      <dd className="flex-1 min-w-0">{children}</dd>
    </div>
  );
}
function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <th className={`text-left px-4 py-2.5 font-medium ${className}`}>{children}</th>;
}
function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2.5 text-slate-700 ${className}`}>{children}</td>;
}
function StatusBadge({ status }: { status: string }) {
  const variant: "info" | "success" | "warning" | "default" =
    status === "active" ? "success"
    : status === "completed" ? "info"
    : status === "cancelled" ? "warning"
    : "default";
  return (
    <Badge variant={variant}>
      {PROJECT_STATUS_LABELS[status as keyof typeof PROJECT_STATUS_LABELS] ?? status}
    </Badge>
  );
}
