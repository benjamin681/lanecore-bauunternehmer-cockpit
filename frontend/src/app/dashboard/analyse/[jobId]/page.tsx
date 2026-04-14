"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type JobStatus = "pending" | "processing" | "completed" | "failed";

interface StatusData {
  job_id: string;
  status: JobStatus;
  progress: number;
  error_message?: string;
}

interface Raum {
  bezeichnung: string;
  raum_nr?: string | null;
  flaeche_m2?: number | null;
  hoehe_m?: number | null;
  nutzung?: string | null;
  deckentyp?: string | null;
}

interface Wand {
  id: string;
  typ: string;
  laenge_m: number;
  hoehe_m: number;
  flaeche_m2?: number | null;
  von_raum?: string | null;
  zu_raum?: string | null;
  unsicher?: boolean;
  notizen?: string | null;
}

interface Decke {
  raum: string;
  raum_nr?: string | null;
  typ: string;
  system?: string | null;
  flaeche_m2?: number | null;
  abhaengehoehe_m?: number | null;
  beplankung?: string | null;
  profil?: string | null;
  entfaellt?: boolean;
}

interface Detail {
  detail_nr?: string | null;
  bezeichnung: string;
  massstab?: string | null;
  beschreibung?: string | null;
}

interface GestrichenePosition {
  bezeichnung: string;
  grund: string;
  original_position?: string | null;
}

interface AnalyseResult {
  job_id: string;
  status: string;
  plantyp?: string | null;
  massstab?: string | null;
  geschoss?: string | null;
  raeume: Raum[];
  waende: Wand[];
  decken: Decke[];
  details: Detail[];
  gestrichene_positionen: GestrichenePosition[];
  konfidenz: number;
  warnungen: string[];
  model_used?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  cost_usd?: number | null;
}

const phaseLabels: Record<string, string> = {
  pending: "PDF wird vorbereitet",
  processing: "KI analysiert den Bauplan",
  completed: "Analyse abgeschlossen",
  failed: "Fehler bei der Analyse",
};

/** Null-safe number formatter */
function fmt(val: number | null | undefined, decimals = 2): string {
  if (val == null || isNaN(val)) return "—";
  return val.toFixed(decimals);
}

export default function AnalyseJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [status, setStatus] = useState<StatusData | null>(null);
  const [result, setResult] = useState<AnalyseResult | null>(null);
  const [activeTab, setActiveTab] = useState<"raeume" | "decken" | "waende" | "details">("raeume");

  // Poll status
  useEffect(() => {
    if (status?.status === "completed" || status?.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/v1/bauplan/${jobId}/status`);
        if (res.ok) {
          const data: StatusData = await res.json();
          setStatus(data);

          if (data.status === "completed") {
            const resultRes = await fetch(`/api/v1/bauplan/${jobId}/result`);
            if (resultRes.ok) setResult(await resultRes.json());
          }
        }
      } catch {
        // Ignore poll errors
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, status?.status]);

  // Initial fetch
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/v1/bauplan/${jobId}/status`);
        if (!res.ok) return;
        const data: StatusData = await res.json();
        setStatus(data);
        if (data.status === "completed") {
          const resultRes = await fetch(`/api/v1/bauplan/${jobId}/result`);
          if (resultRes.ok) setResult(await resultRes.json());
        }
      } catch { /* ignore */ }
    })();
  }, [jobId]);

  if (!status) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin h-8 w-8 border-4 border-primary-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  // --- Loading / Processing ---
  if (status.status === "pending" || status.status === "processing") {
    return (
      <div className="max-w-xl mx-auto text-center py-16">
        <div className="text-5xl mb-6 animate-pulse">🔍</div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          {phaseLabels[status.status]}
        </h2>
        <div className="w-full bg-gray-200 rounded-full h-3 mb-3">
          <div
            className="bg-primary-600 h-3 rounded-full transition-all duration-500"
            style={{ width: `${status.progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-500">{status.progress}% abgeschlossen</p>
        <p className="text-xs text-gray-400 mt-4">
          Typische Analysedauer: 1-3 Minuten pro Seite
        </p>
      </div>
    );
  }

  // --- Error ---
  if (status.status === "failed") {
    return (
      <div className="max-w-xl mx-auto py-16">
        <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
          <div className="text-4xl mb-4">&#10060;</div>
          <h2 className="text-xl font-bold text-red-800 mb-2">Analyse fehlgeschlagen</h2>
          <p className="text-red-600">{status.error_message ?? "Unbekannter Fehler"}</p>
          <a
            href="/dashboard/analyse"
            className="mt-6 inline-block bg-primary-600 text-white px-6 py-3 rounded-lg font-medium"
          >
            Neuen Plan hochladen
          </a>
        </div>
      </div>
    );
  }

  // --- Result ---
  if (!result) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin h-8 w-8 border-4 border-primary-600 border-t-transparent rounded-full" />
        <span className="ml-3 text-gray-500">Lade Ergebnis...</span>
      </div>
    );
  }

  const konfidenzPct = Math.round((result.konfidenz ?? 0) * 100);
  const konfidenzColor =
    konfidenzPct >= 90 ? "text-green-700 bg-green-100" :
    konfidenzPct >= 70 ? "text-yellow-700 bg-yellow-100" :
    "text-red-700 bg-red-100";

  const tabs = [
    { key: "raeume" as const, label: `Raume (${result.raeume.length})`, show: result.raeume.length > 0 },
    { key: "decken" as const, label: `Decken (${result.decken.length})`, show: result.decken.length > 0 },
    { key: "waende" as const, label: `Wande (${result.waende.length})`, show: result.waende.length > 0 },
    { key: "details" as const, label: `Details (${result.details.length})`, show: result.details.length > 0 },
  ].filter((t) => t.show);

  // Auto-select first available tab
  if (!tabs.find((t) => t.key === activeTab) && tabs.length > 0) {
    // This is safe because we only read activeTab below
  }
  const currentTab = tabs.find((t) => t.key === activeTab) ? activeTab : tabs[0]?.key ?? "raeume";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Analyse-Ergebnis</h2>
          <p className="text-sm text-gray-500 mt-1">
            {result.plantyp && <span className="capitalize">{result.plantyp}</span>}
            {result.massstab && <span> &mdash; Massstab {result.massstab}</span>}
            {result.geschoss && <span> &mdash; {result.geschoss}</span>}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href={`/api/v1/bauplan/${jobId}/export`}
            download
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
          >
            Excel herunterladen
          </a>
          <span className={`px-3 py-1.5 rounded-lg text-sm font-medium ${konfidenzColor}`}>
            Konfidenz: {konfidenzPct}%
          </span>
        </div>
      </div>

      {/* Audit Info */}
      {result.model_used && (
        <div className="flex gap-4 text-xs text-gray-400">
          <span>Modell: {result.model_used}</span>
          {result.input_tokens != null && <span>Input: {result.input_tokens.toLocaleString()} Tokens</span>}
          {result.output_tokens != null && <span>Output: {result.output_tokens.toLocaleString()} Tokens</span>}
          {result.cost_usd != null && <span>Kosten: ${result.cost_usd.toFixed(4)}</span>}
        </div>
      )}

      {/* Warnings */}
      {result.warnungen.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5">
          <p className="font-medium text-yellow-800 mb-2">
            {result.warnungen.length} Hinweis{result.warnungen.length > 1 ? "e" : ""} &mdash; bitte pruefen
          </p>
          <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700">
            {result.warnungen.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Gestrichene Positionen */}
      {result.gestrichene_positionen.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5">
          <p className="font-medium text-red-800 mb-2">
            {result.gestrichene_positionen.length} gestrichene Position{result.gestrichene_positionen.length > 1 ? "en" : ""} &mdash; NICHT kalkulieren
          </p>
          <ul className="space-y-2 text-sm text-red-700">
            {result.gestrichene_positionen.map((g, i) => (
              <li key={i}>
                <strong>{g.bezeichnung}</strong>: {g.grund}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-200">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-6 py-3 text-sm font-medium transition-colors ${
                currentTab === tab.key
                  ? "text-primary-700 border-b-2 border-primary-600 bg-primary-50"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Raeume Tab */}
        {currentTab === "raeume" && (
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500 bg-gray-50">
              <tr>
                <th className="px-6 py-2">Raum</th>
                <th className="px-6 py-2">Nr.</th>
                <th className="px-6 py-2">Nutzung</th>
                <th className="px-6 py-2">Deckentyp</th>
                <th className="px-6 py-2 text-right">Flaeche</th>
                <th className="px-6 py-2 text-right">Hoehe</th>
              </tr>
            </thead>
            <tbody>
              {result.raeume.map((r, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium">{r.bezeichnung}</td>
                  <td className="px-6 py-3 text-gray-500">{r.raum_nr ?? "—"}</td>
                  <td className="px-6 py-3 text-gray-500">{r.nutzung ?? "—"}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs">{r.deckentyp ?? "—"}</td>
                  <td className="px-6 py-3 text-right">{fmt(r.flaeche_m2)} m2</td>
                  <td className="px-6 py-3 text-right">{r.hoehe_m ? `${fmt(r.hoehe_m)} m` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Decken Tab */}
        {currentTab === "decken" && (
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500 bg-gray-50">
              <tr>
                <th className="px-6 py-2">Raum</th>
                <th className="px-6 py-2">Typ</th>
                <th className="px-6 py-2">System</th>
                <th className="px-6 py-2">Beplankung</th>
                <th className="px-6 py-2 text-right">Flaeche</th>
                <th className="px-6 py-2 text-right">Abhangeh.</th>
                <th className="px-6 py-2 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {result.decken.map((d, i) => (
                <tr key={i} className={`border-t border-gray-100 hover:bg-gray-50 ${d.entfaellt ? "opacity-50 line-through" : ""}`}>
                  <td className="px-6 py-3">{d.raum}</td>
                  <td className="px-6 py-3 font-medium">{d.typ}</td>
                  <td className="px-6 py-3">{d.system ?? "—"}</td>
                  <td className="px-6 py-3 text-xs text-gray-500">{d.beplankung ?? "—"}</td>
                  <td className="px-6 py-3 text-right">{fmt(d.flaeche_m2)} m2</td>
                  <td className="px-6 py-3 text-right">{d.abhaengehoehe_m ? `${fmt(d.abhaengehoehe_m)} m` : "—"}</td>
                  <td className="px-6 py-3 text-center">
                    {d.entfaellt ? (
                      <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">entfaellt</span>
                    ) : (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">aktiv</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Waende Tab */}
        {currentTab === "waende" && (
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500 bg-gray-50">
              <tr>
                <th className="px-6 py-2">ID</th>
                <th className="px-6 py-2">Typ</th>
                <th className="px-6 py-2 text-right">Laenge</th>
                <th className="px-6 py-2 text-right">Hoehe</th>
                <th className="px-6 py-2 text-right">Flaeche</th>
                <th className="px-6 py-2">Notizen</th>
              </tr>
            </thead>
            <tbody>
              {result.waende.map((w, i) => (
                <tr key={i} className={`border-t border-gray-100 hover:bg-gray-50 ${w.unsicher ? "bg-yellow-50" : ""}`}>
                  <td className="px-6 py-3 font-mono text-xs">{w.id}</td>
                  <td className="px-6 py-3 font-medium">{w.typ}</td>
                  <td className="px-6 py-3 text-right">{fmt(w.laenge_m)} m</td>
                  <td className="px-6 py-3 text-right">{fmt(w.hoehe_m)} m</td>
                  <td className="px-6 py-3 text-right">
                    {fmt(w.flaeche_m2 ?? ((w.laenge_m ?? 0) * (w.hoehe_m ?? 0)))} m2
                  </td>
                  <td className="px-6 py-3 text-xs text-gray-500">
                    {w.unsicher && <span className="text-yellow-600 mr-1">[unsicher]</span>}
                    {w.notizen ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Details Tab */}
        {currentTab === "details" && (
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500 bg-gray-50">
              <tr>
                <th className="px-6 py-2">Nr.</th>
                <th className="px-6 py-2">Bezeichnung</th>
                <th className="px-6 py-2">Massstab</th>
                <th className="px-6 py-2">Beschreibung</th>
              </tr>
            </thead>
            <tbody>
              {result.details.map((d, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-3 font-mono">{d.detail_nr ?? "—"}</td>
                  <td className="px-6 py-3 font-medium">{d.bezeichnung}</td>
                  <td className="px-6 py-3">{d.massstab ?? "—"}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs max-w-md truncate">{d.beschreibung ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
