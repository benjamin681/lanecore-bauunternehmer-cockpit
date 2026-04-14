"use client";

import { useState, useEffect } from "react";

interface AnalyseBrief {
  id: string;
  filename?: string | null;
  status: string;
  progress: number;
  created_at?: string | null;
}

interface Projekt {
  id: string;
  name: string;
  auftraggeber?: string | null;
  bauherr?: string | null;
  architekt?: string | null;
  adresse?: string | null;
  plan_nr?: string | null;
  status: string;
  beschreibung?: string | null;
  created_at: string;
  updated_at: string;
  analyse_count: number;
  analysen: AnalyseBrief[];
}

type SortField = "auftraggeber" | "name" | "updated_at" | "created_at" | "status";

export default function ProjektePage() {
  const [projekte, setProjekte] = useState<Projekt[]>([]);
  const [sort, setSort] = useState<SortField>("updated_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadProjekte = async () => {
    const params = new URLSearchParams();
    params.set("sort", sort);
    params.set("order", order);
    if (statusFilter) params.set("status", statusFilter);
    if (search.trim()) params.set("search", search.trim());

    try {
      const res = await fetch(`/api/v1/projekte/?${params}`);
      if (res.ok) setProjekte(await res.json());
    } catch { /* ignore */ }
  };

  useEffect(() => { loadProjekte(); }, [sort, order, statusFilter]);

  const handleSort = (field: SortField) => {
    if (sort === field) {
      setOrder(order === "asc" ? "desc" : "asc");
    } else {
      setSort(field);
      setOrder("asc");
    }
  };

  const sortIcon = (field: SortField) => {
    if (sort !== field) return "";
    return order === "asc" ? " \u25B2" : " \u25BC";
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      aktiv: "bg-green-100 text-green-700",
      abgeschlossen: "bg-blue-100 text-blue-700",
      archiviert: "bg-gray-100 text-gray-500",
    };
    return (
      <span className={`text-xs px-2 py-0.5 rounded ${colors[status] || "bg-gray-100 text-gray-500"}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Projekte</h2>
          <p className="text-sm text-gray-500 mt-1">
            Projekte werden automatisch aus dem Bauplan erstellt. Sortieren Sie nach Auftraggeber, Name oder Datum.
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex gap-4 items-center">
        <div className="flex-1">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadProjekte()}
            placeholder="Suchen: Projektname, Auftraggeber, Adresse..."
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg bg-white"
        >
          <option value="">Alle Status</option>
          <option value="aktiv">Aktiv</option>
          <option value="abgeschlossen">Abgeschlossen</option>
          <option value="archiviert">Archiviert</option>
        </select>
        <button
          onClick={loadProjekte}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700"
        >
          Suchen
        </button>
      </div>

      {/* Projekte Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {projekte.length === 0 ? (
          <div className="p-12 text-center">
            <div className="text-5xl mb-4">📁</div>
            <p className="text-gray-500 text-lg mb-2">Noch keine Projekte</p>
            <p className="text-sm text-gray-400 mb-6">
              Projekte werden automatisch erstellt wenn Sie einen Bauplan hochladen.
            </p>
            <a
              href="/dashboard/analyse"
              className="inline-block bg-primary-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-primary-700"
            >
              Ersten Bauplan analysieren
            </a>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500 bg-gray-50">
              <tr>
                <th
                  className="px-6 py-3 cursor-pointer hover:text-gray-800 select-none"
                  onClick={() => handleSort("auftraggeber")}
                >
                  Auftraggeber{sortIcon("auftraggeber")}
                </th>
                <th
                  className="px-6 py-3 cursor-pointer hover:text-gray-800 select-none"
                  onClick={() => handleSort("name")}
                >
                  Projekt{sortIcon("name")}
                </th>
                <th className="px-4 py-3">Adresse</th>
                <th className="px-4 py-3 text-center">Analysen</th>
                <th
                  className="px-4 py-3 cursor-pointer hover:text-gray-800 select-none"
                  onClick={() => handleSort("status")}
                >
                  Status{sortIcon("status")}
                </th>
                <th
                  className="px-4 py-3 cursor-pointer hover:text-gray-800 select-none"
                  onClick={() => handleSort("updated_at")}
                >
                  Aktualisiert{sortIcon("updated_at")}
                </th>
              </tr>
            </thead>
            <tbody>
              {projekte.map((p) => (
                <tr
                  key={p.id}
                  className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}
                >
                  <td className="px-6 py-4 font-semibold text-gray-900">
                    {p.auftraggeber || p.bauherr || <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-6 py-4">
                    <div className="font-medium text-gray-900">{p.name}</div>
                    {p.plan_nr && <div className="text-xs text-gray-400">{p.plan_nr}</div>}
                  </td>
                  <td className="px-4 py-4 text-gray-500 text-xs">{p.adresse || "—"}</td>
                  <td className="px-4 py-4 text-center">
                    <span className="inline-flex items-center justify-center w-8 h-8 bg-primary-100 text-primary-700 rounded-full font-bold text-sm">
                      {p.analyse_count}
                    </span>
                  </td>
                  <td className="px-4 py-4">{statusBadge(p.status)}</td>
                  <td className="px-4 py-4 text-gray-500 text-xs">
                    {new Date(p.updated_at).toLocaleDateString("de-DE")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Expanded Detail */}
      {expandedId && (() => {
        const p = projekte.find(pr => pr.id === expandedId);
        if (!p) return null;
        return (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">{p.name}</h3>
              <button onClick={() => setExpandedId(null)} className="text-gray-400 hover:text-gray-600 text-sm">Schliessen</button>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div><span className="text-gray-500">Auftraggeber:</span> <strong>{p.auftraggeber || "—"}</strong></div>
              <div><span className="text-gray-500">Bauherr:</span> <strong>{p.bauherr || "—"}</strong></div>
              <div><span className="text-gray-500">Architekt:</span> <strong>{p.architekt || "—"}</strong></div>
              <div><span className="text-gray-500">Adresse:</span> <strong>{p.adresse || "—"}</strong></div>
              <div><span className="text-gray-500">Plan-Nr:</span> <strong>{p.plan_nr || "—"}</strong></div>
              <div><span className="text-gray-500">Status:</span> {statusBadge(p.status)}</div>
            </div>
            {p.analysen.length > 0 && (
              <div className="space-y-2 mt-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-gray-500">Analysen:</p>
                  {p.analysen.some((a) => a.status === "completed") && (
                    <a
                      href={`/dashboard/projekte/${p.id}/kalkulation`}
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
                    >
                      Gesamtkalkulation
                    </a>
                  )}
                </div>
                {p.analysen.map((a) => (
                  <a
                    key={a.id}
                    href={`/dashboard/analyse/${a.id}`}
                    className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
                  >
                    <span className="text-lg">
                      {a.status === "completed" ? "\u2705" : a.status === "failed" ? "\u274C" : "\u23F3"}
                    </span>
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 text-sm">{a.filename || "Unbekannt"}</p>
                      <p className="text-xs text-gray-400">
                        {a.created_at ? new Date(a.created_at).toLocaleString("de-DE") : ""}
                      </p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      a.status === "completed" ? "bg-green-100 text-green-700" :
                      a.status === "failed" ? "bg-red-100 text-red-700" :
                      "bg-blue-100 text-blue-700"
                    }`}>
                      {a.status}
                    </span>
                  </a>
                ))}
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}
