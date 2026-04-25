"use client";

/**
 * B+4.9 Iteration 2 — Project-Detail.
 * Zeigt Projekt-Stammdaten, zugeordneten Customer und alle LVs des Projekts.
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
  ProjectLV,
  customersApi,
  projectsApi,
} from "@/lib/tenantApi";
import { fmtDate, fmtEur } from "@/lib/format";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;

  const [project, setProject] = useState<Project | null>(null);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [lvs, setLvs] = useState<ProjectLV[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    (async () => {
      try {
        const p = await projectsApi.get(projectId);
        if (!active) return;
        setProject(p);
        const [c, lvList] = await Promise.all([
          customersApi.get(p.customer_id).catch(() => null),
          projectsApi.listLvs(projectId).catch(() => [] as ProjectLV[]),
        ]);
        if (!active) return;
        setCustomer(c);
        setLvs(lvList);
      } catch (e) {
        toast.error("Projekt konnte nicht geladen werden");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId]);

  if (loading || !project) {
    return <div className="text-slate-500 py-20 text-center">Lade…</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/projects"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-bauplan-600"
        >
          <ArrowLeft className="w-4 h-4" /> Projekte
        </Link>
      </div>

      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">{project.name}</h1>
          <div className="text-slate-600 mt-1 flex items-center gap-2 flex-wrap">
            <StatusBadge status={project.status} />
            {customer && (
              <>
                <span className="text-slate-400">·</span>
                <Link
                  href={`/dashboard/customers/${customer.id}`}
                  className="hover:text-bauplan-600"
                >
                  {customer.name}
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <section className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Projekt-Adresse</h2>
          {project.address_street || project.address_zip || project.address_city ? (
            <div className="text-sm text-slate-700 space-y-0.5">
              {project.address_street && <div>{project.address_street}</div>}
              {(project.address_zip || project.address_city) && (
                <div>
                  {project.address_zip} {project.address_city}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Keine Adresse hinterlegt.</p>
          )}
          {project.notes && (
            <>
              <h3 className="font-medium text-slate-900 mt-4 mb-1 text-sm">Notizen</h3>
              <p className="text-sm text-slate-600 whitespace-pre-wrap">{project.notes}</p>
            </>
          )}
        </div>

        <div className="rounded-xl bg-white border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Kunde</h2>
          {customer ? (
            <div className="text-sm text-slate-700 space-y-1">
              <div className="font-medium text-slate-900">{customer.name}</div>
              {customer.contact_person && (
                <div className="text-slate-600">{customer.contact_person}</div>
              )}
              {customer.email && (
                <div>
                  <a
                    href={`mailto:${customer.email}`}
                    className="text-bauplan-600 hover:underline"
                  >
                    {customer.email}
                  </a>
                </div>
              )}
              {customer.phone && <div>{customer.phone}</div>}
              <Link
                href={`/dashboard/customers/${customer.id}`}
                className="inline-block mt-2 text-bauplan-600 hover:underline"
              >
                Kundendetails öffnen →
              </Link>
            </div>
          ) : (
            <p className="text-sm text-slate-400">Kunde nicht verfügbar.</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="font-semibold text-slate-900 mb-3">
          Leistungsverzeichnisse{" "}
          <span className="text-slate-400 font-normal">({lvs?.length ?? 0})</span>
        </h2>
        {!lvs || lvs.length === 0 ? (
          <div className="rounded-xl bg-white border border-slate-200 p-10 text-center">
            <FolderOpen className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-slate-600 mt-3">Keine LVs in diesem Projekt.</p>
          </div>
        ) : (
          <div className="rounded-xl bg-white border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <Th>LV</Th>
                    <Th>Auftraggeber</Th>
                    <Th>Status</Th>
                    <Th className="text-right">Positionen</Th>
                    <Th className="text-right">Angebotssumme</Th>
                    <Th>Erstellt</Th>
                  </tr>
                </thead>
                <tbody>
                  {lvs.map((lv) => (
                    <tr
                      key={lv.id}
                      className="border-t border-slate-100 hover:bg-slate-50"
                    >
                      <Td>
                        <Link
                          href={`/dashboard/lvs/${lv.id}`}
                          className="font-medium text-slate-900 hover:text-bauplan-600"
                        >
                          {lv.projekt_name || "Unbenanntes LV"}
                        </Link>
                      </Td>
                      <Td className="text-slate-600">{lv.auftraggeber || "—"}</Td>
                      <Td>
                        <LvStatusBadge status={lv.status} />
                      </Td>
                      <Td className="text-right tabular-nums">{lv.positionen_gesamt}</Td>
                      <Td className="text-right tabular-nums">
                        {fmtEur(lv.angebotssumme_netto)}
                      </Td>
                      <Td className="text-slate-500">
                        {lv.created_at ? fmtDate(lv.created_at) : "—"}
                      </Td>
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
function LvStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; variant: "default" | "success" | "warning" | "info" }> =
    {
      uploaded: { label: "Hochgeladen", variant: "info" },
      extracting: { label: "Wird extrahiert…", variant: "info" },
      review_needed: { label: "Prüfung", variant: "warning" },
      calculated: { label: "Kalkuliert", variant: "success" },
      exported: { label: "Exportiert", variant: "success" },
      error: { label: "Fehler", variant: "warning" },
    };
  const meta = map[status] || { label: status, variant: "default" as const };
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}
