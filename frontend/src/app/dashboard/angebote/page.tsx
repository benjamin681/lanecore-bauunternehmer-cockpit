"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface PipelineProjekt {
  id: string;
  name: string;
  auftraggeber?: string | null;
  bauherr?: string | null;
  adresse?: string | null;
  status: string;
  analyse_count: number;
  has_angebot: boolean;
  updated_at?: string | null;
}

interface PipelineData {
  offen: PipelineProjekt[];
  angebot_erstellt: PipelineProjekt[];
  beauftragt: PipelineProjekt[];
  abgeschlossen: PipelineProjekt[];
}

const columns = [
  { key: "offen" as const, label: "Offen", color: "bg-yellow-500", bg: "bg-yellow-50", border: "border-yellow-200" },
  { key: "angebot_erstellt" as const, label: "Angebot erstellt", color: "bg-blue-500", bg: "bg-blue-50", border: "border-blue-200" },
  { key: "beauftragt" as const, label: "Beauftragt", color: "bg-purple-500", bg: "bg-purple-50", border: "border-purple-200" },
  { key: "abgeschlossen" as const, label: "Abgeschlossen", color: "bg-green-500", bg: "bg-green-50", border: "border-green-200" },
];

export default function AngebotePipelinePage() {
  const [pipeline, setPipeline] = useState<PipelineData | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  const loadPipeline = async () => {
    try {
      const res = await fetch("/api/v1/projekte/pipeline");
      if (res.ok) setPipeline(await res.json());
    } catch { /* ignore */ }
  };

  useEffect(() => { loadPipeline(); }, []);

  const changeStatus = async (projektId: string, newStatus: string) => {
    setUpdating(projektId);
    try {
      const res = await fetch(`/api/v1/projekte/${projektId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) await loadPipeline();
    } catch { /* ignore */ }
    finally { setUpdating(null); }
  };

  if (!pipeline) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin h-8 w-8 border-4 border-primary-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  const totalCount = columns.reduce((sum, col) => sum + (pipeline[col.key]?.length || 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg md:text-2xl font-bold text-gray-900">Angebote-Pipeline</h2>
        <p className="text-sm text-gray-500 mt-1">
          {totalCount} Projekt{totalCount !== 1 ? "e" : ""} in der Pipeline
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {columns.map((col) => {
          const items = pipeline[col.key] || [];
          return (
            <div key={col.key} className="space-y-3">
              {/* Column Header */}
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${col.color}`} />
                <h3 className="font-semibold text-gray-900 text-sm">{col.label}</h3>
                <span className="text-xs text-gray-400 ml-auto">{items.length}</span>
              </div>

              {/* Cards */}
              <div className="space-y-2 min-h-[200px]">
                {items.length === 0 ? (
                  <div className={`rounded-lg border ${col.border} ${col.bg} p-4 text-center`}>
                    <p className="text-xs text-gray-400">Keine Projekte</p>
                  </div>
                ) : (
                  items.map((p) => (
                    <div
                      key={p.id}
                      className={`rounded-lg border ${col.border} bg-white p-4 shadow-sm hover:shadow-md transition-shadow`}
                    >
                      <Link
                        href={`/dashboard/projekte`}
                        className="block mb-2"
                      >
                        <h4 className="font-semibold text-gray-900 text-sm hover:text-primary-600 transition-colors">
                          {p.name}
                        </h4>
                      </Link>

                      <div className="space-y-1 text-xs text-gray-500 mb-3">
                        {(p.auftraggeber || p.bauherr) && (
                          <p>Auftraggeber: {p.auftraggeber || p.bauherr}</p>
                        )}
                        {p.adresse && <p>{p.adresse}</p>}
                        <p>{p.analyse_count} Analyse{p.analyse_count !== 1 ? "n" : ""}</p>
                      </div>

                      {/* Status change buttons */}
                      <div className="flex flex-wrap gap-1">
                        {col.key !== "offen" && (
                          <button
                            onClick={() => changeStatus(p.id, col.key === "angebot_erstellt" ? "aktiv" : col.key === "beauftragt" ? "angebot_erstellt" : "beauftragt")}
                            disabled={updating === p.id}
                            className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors disabled:opacity-50"
                          >
                            Zurueck
                          </button>
                        )}
                        {col.key === "offen" && (
                          <button
                            onClick={() => changeStatus(p.id, "angebot_erstellt")}
                            disabled={updating === p.id}
                            className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors disabled:opacity-50"
                          >
                            Angebot erstellt
                          </button>
                        )}
                        {col.key === "angebot_erstellt" && (
                          <button
                            onClick={() => changeStatus(p.id, "beauftragt")}
                            disabled={updating === p.id}
                            className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-700 hover:bg-purple-200 transition-colors disabled:opacity-50"
                          >
                            Beauftragt
                          </button>
                        )}
                        {col.key === "beauftragt" && (
                          <button
                            onClick={() => changeStatus(p.id, "abgeschlossen")}
                            disabled={updating === p.id}
                            className="text-xs px-2 py-1 rounded bg-green-100 text-green-700 hover:bg-green-200 transition-colors disabled:opacity-50"
                          >
                            Abschliessen
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
