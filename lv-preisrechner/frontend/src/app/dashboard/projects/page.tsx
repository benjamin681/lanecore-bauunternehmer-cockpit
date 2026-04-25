"use client";

/**
 * B+4.9 Iteration 2 — Projects-Liste.
 * Zeigt alle Projekte des Tenants mit Customer-Name + Status + LV-Anzahl.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { FolderOpen, Plus } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import {
  Customer,
  Project,
  PROJECT_STATUS_LABELS,
  ProjectLV,
  customersApi,
  projectsApi,
} from "@/lib/tenantApi";
import { fmtDate } from "@/lib/format";

type Row = {
  project: Project;
  customer: Customer | undefined;
  lv_count: number;
};

export default function ProjectsListPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [projects, customers] = await Promise.all([
          projectsApi.list(),
          customersApi.list(),
        ]);
        // Pro Project die LVs zaehlen — eine Round-Trip pro Project,
        // bei kleinen Tenants ok. Bei groesseren spaeter Aggregat-Endpoint.
        const cust_map = new Map<string, Customer>();
        for (const c of customers) cust_map.set(c.id, c);
        const built: Row[] = [];
        for (const p of projects) {
          let lvs: ProjectLV[] = [];
          try {
            lvs = await projectsApi.listLvs(p.id);
          } catch {
            // 404 oder net-error — als 0 darstellen
          }
          built.push({
            project: p,
            customer: cust_map.get(p.customer_id),
            lv_count: lvs.length,
          });
        }
        if (active) setRows(built);
      } catch (e) {
        toast.error("Projekte konnten nicht geladen werden");
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
          <h1 className="text-3xl font-bold text-slate-900">Projekte</h1>
          <p className="text-slate-600 mt-1">
            Bauvorhaben verknüpfen Kunden mit ihren LVs.
          </p>
        </div>
      </header>

      {rows.length === 0 ? (
        <div className="rounded-xl bg-white border border-slate-200 p-10 text-center">
          <FolderOpen className="w-10 h-10 text-slate-400 mx-auto" />
          <p className="text-slate-600 mt-3">Noch keine Projekte angelegt.</p>
          <p className="text-xs text-slate-500 mt-1">
            Projekte entstehen automatisch beim LV-Upload, wenn der Parser
            Auftraggeber + Bauvorhaben aus dem LV-Header extrahiert.
          </p>
        </div>
      ) : (
        <div className="rounded-xl bg-white border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <Th>Projekt</Th>
                  <Th>Kunde</Th>
                  <Th>Status</Th>
                  <Th className="text-right">LVs</Th>
                  <Th>Letztes Update</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ project, customer, lv_count }) => (
                  <tr
                    key={project.id}
                    className="border-t border-slate-100 hover:bg-slate-50"
                  >
                    <Td>
                      <Link
                        href={`/dashboard/projects/${project.id}`}
                        className="font-medium text-slate-900 hover:text-bauplan-600"
                      >
                        {project.name}
                      </Link>
                    </Td>
                    <Td>
                      {customer ? (
                        <Link
                          href={`/dashboard/customers/${customer.id}`}
                          className="text-slate-700 hover:text-bauplan-600"
                        >
                          {customer.name}
                        </Link>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </Td>
                    <Td>
                      <StatusBadge status={project.status} />
                    </Td>
                    <Td className="text-right tabular-nums">{lv_count}</Td>
                    <Td className="text-slate-500">
                      {fmtDate(project.updated_at)}
                    </Td>
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
