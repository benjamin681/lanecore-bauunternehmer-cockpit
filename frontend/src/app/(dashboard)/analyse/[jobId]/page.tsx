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

interface AnalyseResult {
  plantyp?: string;
  massstab?: string;
  geschoss?: string;
  konfidenz: number;
  raeume: Array<{ bezeichnung: string; flaeche_m2: number; hoehe_m?: number }>;
  waende: Array<{ id: string; typ: string; laenge_m: number; hoehe_m: number }>;
  decken: Array<{ raum: string; typ: string; flaeche_m2: number; system?: string }>;
  warnungen: string[];
}

const phaseLabels: Record<string, string> = {
  pending: "PDF wird vorbereitet",
  processing: "KI analysiert den Bauplan",
  completed: "Analyse abgeschlossen",
  failed: "Fehler bei der Analyse",
};

export default function AnalyseJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [status, setStatus] = useState<StatusData | null>(null);
  const [result, setResult] = useState<AnalyseResult | null>(null);

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
    fetch(`/api/v1/bauplan/${jobId}/status`)
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {});
  }, [jobId]);

  if (!status) {
    return <div className="text-gray-500">Lade Status...</div>;
  }

  // --- Loading / Processing ---
  if (status.status === "pending" || status.status === "processing") {
    return (
      <div className="max-w-xl mx-auto text-center py-16">
        <div className="text-5xl mb-6 animate-pulse">🔍</div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">
          {phaseLabels[status.status]}
        </h2>

        {/* Progress bar */}
        <div className="w-full bg-gray-200 rounded-full h-3 mb-3">
          <div
            className="bg-primary-600 h-3 rounded-full transition-all duration-500"
            style={{ width: `${status.progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-500">{status.progress}% abgeschlossen</p>
        <p className="text-xs text-gray-400 mt-4">
          Typische Analysedauer: 1–3 Minuten pro Seite
        </p>
      </div>
    );
  }

  // --- Error ---
  if (status.status === "failed") {
    return (
      <div className="max-w-xl mx-auto py-16">
        <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
          <div className="text-4xl mb-4">❌</div>
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
    return <div className="text-gray-500">Lade Ergebnis...</div>;
  }

  const konfidenzPct = Math.round(result.konfidenz * 100);
  const konfidenzColor =
    konfidenzPct >= 90 ? "text-green-700 bg-green-100" :
    konfidenzPct >= 70 ? "text-yellow-700 bg-yellow-100" :
    "text-red-700 bg-red-100";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Analyse-Ergebnis</h2>
          <p className="text-sm text-gray-500 mt-1">
            {result.plantyp && <span className="capitalize">{result.plantyp}</span>}
            {result.massstab && <span> — Maßstab {result.massstab}</span>}
            {result.geschoss && <span> — {result.geschoss}</span>}
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

      {/* Warnings */}
      {result.warnungen.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5">
          <p className="font-medium text-yellow-800 mb-2">
            ⚠ {result.warnungen.length} Hinweis{result.warnungen.length > 1 ? "e" : ""} — bitte prüfen
          </p>
          <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700">
            {result.warnungen.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Tabs: Räume | Wände | Decken */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Räume */}
        {result.raeume.length > 0 && (
          <div className="border-b border-gray-100">
            <h3 className="px-6 py-4 font-semibold text-gray-900 bg-gray-50">
              Räume ({result.raeume.length})
            </h3>
            <table className="w-full text-sm">
              <thead className="text-left text-gray-500 bg-gray-50">
                <tr>
                  <th className="px-6 py-2">Raum</th>
                  <th className="px-6 py-2 text-right">Fläche</th>
                  <th className="px-6 py-2 text-right">Höhe</th>
                </tr>
              </thead>
              <tbody>
                {result.raeume.map((r, i) => (
                  <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-6 py-3 font-medium">{r.bezeichnung}</td>
                    <td className="px-6 py-3 text-right">{r.flaeche_m2.toFixed(2)} m²</td>
                    <td className="px-6 py-3 text-right">{r.hoehe_m ? `${r.hoehe_m.toFixed(2)} m` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Wände */}
        {result.waende.length > 0 && (
          <div className="border-b border-gray-100">
            <h3 className="px-6 py-4 font-semibold text-gray-900 bg-gray-50">
              Wände ({result.waende.length})
            </h3>
            <table className="w-full text-sm">
              <thead className="text-left text-gray-500 bg-gray-50">
                <tr>
                  <th className="px-6 py-2">Typ</th>
                  <th className="px-6 py-2 text-right">Länge</th>
                  <th className="px-6 py-2 text-right">Höhe</th>
                  <th className="px-6 py-2 text-right">Fläche</th>
                </tr>
              </thead>
              <tbody>
                {result.waende.map((w, i) => (
                  <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-6 py-3 font-medium">{w.typ}</td>
                    <td className="px-6 py-3 text-right">{w.laenge_m.toFixed(2)} m</td>
                    <td className="px-6 py-3 text-right">{w.hoehe_m.toFixed(2)} m</td>
                    <td className="px-6 py-3 text-right">
                      {(w.laenge_m * w.hoehe_m).toFixed(2)} m²
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Decken */}
        {result.decken.length > 0 && (
          <div>
            <h3 className="px-6 py-4 font-semibold text-gray-900 bg-gray-50">
              Decken ({result.decken.length})
            </h3>
            <table className="w-full text-sm">
              <thead className="text-left text-gray-500 bg-gray-50">
                <tr>
                  <th className="px-6 py-2">Raum</th>
                  <th className="px-6 py-2">Typ</th>
                  <th className="px-6 py-2">System</th>
                  <th className="px-6 py-2 text-right">Fläche</th>
                </tr>
              </thead>
              <tbody>
                {result.decken.map((d, i) => (
                  <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-6 py-3">{d.raum}</td>
                    <td className="px-6 py-3 font-medium">{d.typ}</td>
                    <td className="px-6 py-3">{d.system ?? "—"}</td>
                    <td className="px-6 py-3 text-right">{d.flaeche_m2.toFixed(2)} m²</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
