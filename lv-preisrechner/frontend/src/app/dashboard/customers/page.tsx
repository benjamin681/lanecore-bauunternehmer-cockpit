"use client";

/**
 * B+4.9 Iteration 2 — Customer-Liste.
 * Zeigt alle Kunden des Tenants mit Kontakt + Anzahl Projekte.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { toast } from "sonner";
import {
  Customer,
  Project,
  customersApi,
  projectsApi,
} from "@/lib/tenantApi";

type Row = {
  customer: Customer;
  project_count: number;
};

export default function CustomersListPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [customers, projects] = await Promise.all([
          customersApi.list(),
          projectsApi.list(),
        ]);
        const counts = new Map<string, number>();
        for (const p of projects) {
          counts.set(p.customer_id, (counts.get(p.customer_id) ?? 0) + 1);
        }
        const built: Row[] = customers.map((c) => ({
          customer: c,
          project_count: counts.get(c.id) ?? 0,
        }));
        if (active) setRows(built);
      } catch (e) {
        toast.error("Kunden konnten nicht geladen werden");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (loading || !rows) {
    return <div className="text-slate-500 py-20 text-center">Lade…</div>;
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Kunden</h1>
          <p className="text-slate-600 mt-1">
            Auftraggeber Ihrer Projekte.
          </p>
        </div>
      </header>

      {rows.length === 0 ? (
        <div className="rounded-xl bg-white border border-slate-200 p-10 text-center">
          <Users className="w-10 h-10 text-slate-400 mx-auto" />
          <p className="text-slate-600 mt-3">Noch keine Kunden angelegt.</p>
          <p className="text-xs text-slate-500 mt-1">
            Kunden entstehen automatisch beim LV-Upload, wenn der Parser einen
            Auftraggeber aus dem LV-Header extrahiert.
          </p>
        </div>
      ) : (
        <div className="rounded-xl bg-white border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <Th>Name</Th>
                  <Th>Kontakt</Th>
                  <Th>Stadt</Th>
                  <Th className="text-right">Projekte</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ customer, project_count }) => (
                  <tr
                    key={customer.id}
                    className="border-t border-slate-100 hover:bg-slate-50"
                  >
                    <Td>
                      <Link
                        href={`/dashboard/customers/${customer.id}`}
                        className="font-medium text-slate-900 hover:text-bauplan-600"
                      >
                        {customer.name}
                      </Link>
                      {customer.contact_person && (
                        <div className="text-xs text-slate-500 mt-0.5">
                          {customer.contact_person}
                        </div>
                      )}
                    </Td>
                    <Td className="text-slate-600">
                      {customer.email ? (
                        <a
                          href={`mailto:${customer.email}`}
                          className="hover:text-bauplan-600"
                        >
                          {customer.email}
                        </a>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                      {customer.phone && (
                        <div className="text-xs text-slate-500 mt-0.5">
                          {customer.phone}
                        </div>
                      )}
                    </Td>
                    <Td className="text-slate-600">
                      {customer.address_city || (
                        <span className="text-slate-400">—</span>
                      )}
                    </Td>
                    <Td className="text-right tabular-nums">{project_count}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <th className={`text-left px-4 py-2.5 font-medium ${className}`}>{children}</th>;
}
function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2.5 text-slate-700 ${className}`}>{children}</td>;
}
