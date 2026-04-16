"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface DashboardStats {
  projekte: number;
  analysen_gesamt: number;
  analysen_erfolgreich: number;
  eingesparte_stunden: number;
  kosten_usd_gesamt: number;
}

interface AnalyseBrief {
  id: string;
  filename?: string | null;
  status: string;
  progress: number;
  created_at?: string | null;
}

interface ProjektBrief {
  id: string;
  name: string;
  auftraggeber?: string | null;
  bauherr?: string | null;
  adresse?: string | null;
  status: string;
  analyse_count: number;
  analysen: AnalyseBrief[];
  updated_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [projekte, setProjekte] = useState<ProjektBrief[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/stats/dashboard")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});

    fetch("/api/v1/projekte?sort=updated_at&order=desc")
      .then((r) => r.json())
      .then(setProjekte)
      .catch(() => {});
  }, []);

  // Quick upload handler
  const handleFile = useCallback(
    async (file: File) => {
      setUploadError(null);
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setUploadError("Nur PDF-Dateien werden akzeptiert.");
        return;
      }
      if (file.size / (1024 * 1024) > 50) {
        setUploadError("Datei zu gross (Max: 50MB).");
        return;
      }
      setIsUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch("/api/v1/bauplan/upload", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || body?.error || `Upload fehlgeschlagen (${res.status})`);
        }
        const data = await res.json();
        router.push(`/dashboard/analyse/${data.job_id}`);
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
      } finally {
        setIsUploading(false);
      }
    },
    [router],
  );

  const s = stats ?? {
    projekte: 0,
    analysen_gesamt: 0,
    analysen_erfolgreich: 0,
    eingesparte_stunden: 0,
    kosten_usd_gesamt: 0,
  };

  // Derive recent completed analyses from projekte
  const recentAnalysen: Array<AnalyseBrief & { projektName: string }> = [];
  for (const p of projekte) {
    for (const a of (p.analysen ?? [])) {
      if (a.status === "completed") {
        recentAnalysen.push({ ...a, projektName: p.name });
      }
    }
  }
  recentAnalysen.sort((a, b) => {
    const da = a.created_at ? new Date(a.created_at).getTime() : 0;
    const db = b.created_at ? new Date(b.created_at).getTime() : 0;
    return db - da;
  });
  const last5Analysen = recentAnalysen.slice(0, 5);

  // Offene Angebote = aktive projekte
  const offeneAngebote = projekte.filter((p) => p.status === "aktiv").slice(0, 5);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4 md:p-6">
          <p className="text-sm text-gray-500">Projekte</p>
          <p className="text-xl md:text-3xl font-bold text-gray-900 mt-2">{s.projekte}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 md:p-6">
          <p className="text-sm text-gray-500">Analysen</p>
          <p className="text-xl md:text-3xl font-bold text-gray-900 mt-2">
            {s.analysen_erfolgreich}
            {s.analysen_gesamt > s.analysen_erfolgreich && (
              <span className="text-lg text-gray-400"> / {s.analysen_gesamt}</span>
            )}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 md:p-6">
          <p className="text-sm text-gray-500">Eingesparte Stunden</p>
          <p className="text-xl md:text-3xl font-bold text-green-600 mt-2">{s.eingesparte_stunden}h</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 md:p-6">
          <p className="text-sm text-gray-500">API-Kosten gesamt</p>
          <p className="text-xl md:text-3xl font-bold text-gray-900 mt-2">${(s.kosten_usd_gesamt ?? 0).toFixed(2)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
        {/* Quick Upload */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-3">Schnell-Upload</h3>
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              const file = e.dataTransfer.files[0];
              if (file) handleFile(file);
            }}
            className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
              isDragging ? "border-primary-500 bg-primary-50" : "border-gray-300 hover:border-primary-300"
            } ${isUploading ? "opacity-50 pointer-events-none" : ""}`}
          >
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              id="dashboard-upload"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />
            <label htmlFor="dashboard-upload" className="cursor-pointer">
              <p className="text-3xl mb-2">📄</p>
              {isUploading ? (
                <p className="text-sm text-primary-600 font-medium">Wird hochgeladen...</p>
              ) : (
                <>
                  <p className="text-sm font-medium text-gray-700">PDF hier ablegen</p>
                  <p className="text-xs text-gray-400 mt-1">oder klicken zum Auswaehlen</p>
                </>
              )}
            </label>
          </div>
          {uploadError && (
            <p className="text-xs text-red-600 mt-2">{uploadError}</p>
          )}
        </div>

        {/* Letzte Analysen */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-3">Letzte Analysen</h3>
          {last5Analysen.length === 0 ? (
            <p className="text-sm text-gray-400 py-4 text-center">Noch keine abgeschlossenen Analysen.</p>
          ) : (
            <div className="space-y-2">
              {last5Analysen.map((a) => (
                <Link
                  key={a.id}
                  href={`/dashboard/analyse/${a.id}`}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <span className="text-green-500">&#10003;</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{a.filename || "Unbekannt"}</p>
                    <p className="text-xs text-gray-400 truncate">{a.projektName}</p>
                  </div>
                  <span className="text-xs text-gray-400 whitespace-nowrap">
                    {a.created_at ? new Date(a.created_at).toLocaleDateString("de-DE") : ""}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Offene Angebote */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">Offene Angebote</h3>
            <Link href="/dashboard/angebote" className="text-xs text-primary-600 hover:text-primary-700 font-medium">
              Alle anzeigen
            </Link>
          </div>
          {offeneAngebote.length === 0 ? (
            <p className="text-sm text-gray-400 py-4 text-center">Keine offenen Projekte.</p>
          ) : (
            <div className="space-y-2">
              {offeneAngebote.map((p) => (
                <Link
                  key={p.id}
                  href="/dashboard/projekte"
                  className="block p-3 rounded-lg border border-gray-100 hover:border-primary-200 hover:bg-primary-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-900">{p.name}</p>
                    <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">
                      {p.analyse_count} Analyse{p.analyse_count !== 1 ? "n" : ""}
                    </span>
                  </div>
                  {(p.auftraggeber || p.bauherr) && (
                    <p className="text-xs text-gray-500 mt-1">{p.auftraggeber || p.bauherr}</p>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Schnellzugriff */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Schnellzugriff</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <a
            href="/dashboard/analyse"
            className="p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors text-center"
          >
            <p className="text-2xl mb-1">&#128208;</p>
            <p className="font-medium text-gray-900 text-sm md:text-base">Neuen Plan analysieren</p>
          </a>
          <a
            href="/dashboard/angebote"
            className="p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors text-center"
          >
            <p className="text-2xl mb-1">&#128203;</p>
            <p className="font-medium text-gray-900 text-sm md:text-base">Angebote-Pipeline</p>
          </a>
          <a
            href="/dashboard/projekte"
            className="p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors text-center"
          >
            <p className="text-2xl mb-1">&#128193;</p>
            <p className="font-medium text-gray-900 text-sm md:text-base">Projekte verwalten</p>
          </a>
          <a
            href="/dashboard/preislisten"
            className="p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors text-center"
          >
            <p className="text-2xl mb-1">&#128176;</p>
            <p className="font-medium text-gray-900 text-sm md:text-base">Preislisten</p>
          </a>
        </div>
      </div>
    </div>
  );
}
