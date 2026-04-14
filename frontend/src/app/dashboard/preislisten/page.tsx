"use client";

import { useState, useEffect, useCallback } from "react";

interface Preisliste {
  id: string;
  anbieter: string;
  quelle: string;
  status: string;
  dateiname?: string | null;
  produkt_count: number;
  created_at?: string | null;
}

interface Produkt {
  id: string;
  artikel_nr?: string | null;
  bezeichnung: string;
  hersteller?: string | null;
  kategorie?: string | null;
  einheit: string;
  preis_netto: number;
  preis_brutto?: number | null;
}

interface PreislisteDetail extends Preisliste {
  error_message?: string | null;
  produkte: Produkt[];
}

interface PreisvergleichResult {
  anbieter: string;
  produkt: Produkt;
  gesamtpreis: number;
  ist_guenstigster: boolean;
}

interface PreisvergleichResponse {
  suche: string;
  ergebnisse: PreisvergleichResult[];
  guenstigster_anbieter?: string | null;
  preisdifferenz_prozent?: number | null;
}

export default function PreislistenPage() {
  const [preislisten, setPreislisten] = useState<Preisliste[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PreislisteDetail | null>(null);

  // Upload state
  const [anbieter, setAnbieter] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Preisvergleich state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PreisvergleichResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const loadPreislisten = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/preislisten/");
      if (res.ok) setPreislisten(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadPreislisten();
  }, [loadPreislisten]);

  // Poll for processing preislisten
  useEffect(() => {
    const processing = preislisten.filter((p) => p.status === "processing" || p.status === "pending");
    if (processing.length === 0) return;

    const interval = setInterval(loadPreislisten, 5000);
    return () => clearInterval(interval);
  }, [preislisten, loadPreislisten]);

  const handleUpload = async (file: File) => {
    if (!anbieter.trim()) {
      setUploadError("Bitte Anbieter-Name eingeben.");
      return;
    }
    setUploadError(null);
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("anbieter", anbieter.trim());

      const res = await fetch("/api/v1/preislisten/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Upload fehlgeschlagen (${res.status})`);
      }

      setAnbieter("");
      loadPreislisten();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setIsUploading(false);
    }
  };

  const loadDetail = async (id: string) => {
    setSelectedId(id);
    try {
      const res = await fetch(`/api/v1/preislisten/${id}`);
      if (res.ok) setDetail(await res.json());
    } catch { /* ignore */ }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await fetch(`/api/v1/preislisten/vergleich/suche?q=${encodeURIComponent(searchQuery)}`);
      if (res.ok) setSearchResults(await res.json());
    } catch { /* ignore */ }
    setIsSearching(false);
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Preislisten</h2>
          <p className="text-sm text-gray-500 mt-1">
            Laden Sie Preislisten von verschiedenen Anbietern hoch. Das System erkennt automatisch alle Produkte und findet den guenstigsten Preis.
          </p>
        </div>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Neue Preisliste hochladen</h3>
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Anbieter</label>
            <input
              type="text"
              value={anbieter}
              onChange={(e) => setAnbieter(e.target.value)}
              placeholder="z.B. KEMLER, Saint-Gobain, Knauf, Rigips..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <label className={`cursor-pointer ${isUploading ? "opacity-50 pointer-events-none" : ""}`}>
            <span className="bg-primary-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-primary-700 transition-colors inline-block">
              {isUploading ? "Wird hochgeladen..." : "PDF hochladen"}
            </span>
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onClick={(e) => { (e.target as HTMLInputElement).value = ""; }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
            />
          </label>
        </div>
        {uploadError && (
          <p className="mt-2 text-sm text-red-600">{uploadError}</p>
        )}
      </div>

      {/* Preisvergleich */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Preisvergleich</h3>
        <div className="flex gap-4">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Produkt suchen, z.B. 'CW 75' oder 'Knauf Diamant'..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
          <button
            onClick={handleSearch}
            disabled={isSearching}
            className="bg-green-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
          >
            {isSearching ? "Suche..." : "Vergleichen"}
          </button>
        </div>

        {searchResults && (
          <div className="mt-4">
            {searchResults.ergebnisse.length === 0 ? (
              <p className="text-gray-500 text-sm">Keine Produkte gefunden fuer &quot;{searchResults.suche}&quot;</p>
            ) : (
              <>
                {searchResults.preisdifferenz_prozent != null && searchResults.preisdifferenz_prozent > 0 && (
                  <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
                    Preisdifferenz: <strong>{searchResults.preisdifferenz_prozent}%</strong> zwischen guenstigstem und teuerstem Anbieter
                  </div>
                )}
                <table className="w-full text-sm">
                  <thead className="text-left text-gray-500 bg-gray-50">
                    <tr>
                      <th className="px-4 py-2">Anbieter</th>
                      <th className="px-4 py-2">Produkt</th>
                      <th className="px-4 py-2">Kategorie</th>
                      <th className="px-4 py-2 text-right">Preis (netto)</th>
                      <th className="px-4 py-2">Einheit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchResults.ergebnisse.map((r, i) => (
                      <tr key={i} className={`border-t border-gray-100 ${r.ist_guenstigster ? "bg-green-50 font-medium" : ""}`}>
                        <td className="px-4 py-3">{r.anbieter}</td>
                        <td className="px-4 py-3">{r.produkt.bezeichnung}</td>
                        <td className="px-4 py-3 text-gray-500">{r.produkt.kategorie ?? "—"}</td>
                        <td className="px-4 py-3 text-right">
                          {r.produkt.preis_netto.toFixed(2)} EUR
                          {r.ist_guenstigster && <span className="ml-2 text-green-600 text-xs">guenstigster</span>}
                        </td>
                        <td className="px-4 py-3">{r.produkt.einheit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}
      </div>

      {/* Preislisten-Übersicht */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <h3 className="px-6 py-4 font-semibold text-gray-900 bg-gray-50 border-b border-gray-200">
          Hochgeladene Preislisten ({preislisten.length})
        </h3>
        {preislisten.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            Noch keine Preislisten hochgeladen. Laden Sie PDFs Ihrer Lieferanten hoch.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-gray-500 bg-gray-50">
              <tr>
                <th className="px-6 py-2">Anbieter</th>
                <th className="px-6 py-2">Datei</th>
                <th className="px-6 py-2">Produkte</th>
                <th className="px-6 py-2">Status</th>
                <th className="px-6 py-2">Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {preislisten.map((p) => (
                <tr key={p.id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium">{p.anbieter}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs">{p.dateiname ?? "—"}</td>
                  <td className="px-6 py-3">{p.produkt_count}</td>
                  <td className="px-6 py-3">
                    {p.status === "completed" && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">fertig</span>
                    )}
                    {p.status === "processing" && (
                      <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded animate-pulse">wird verarbeitet...</span>
                    )}
                    {p.status === "pending" && (
                      <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">wartend</span>
                    )}
                    {p.status === "failed" && (
                      <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">Fehler</span>
                    )}
                  </td>
                  <td className="px-6 py-3">
                    {p.status === "completed" && (
                      <button
                        onClick={() => loadDetail(p.id)}
                        className="text-primary-600 hover:text-primary-800 text-sm font-medium"
                      >
                        Details
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail-Ansicht */}
      {detail && selectedId && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">
              {detail.anbieter} — {detail.produkt_count} Produkte
            </h3>
            <button onClick={() => { setSelectedId(null); setDetail(null); }} className="text-gray-400 hover:text-gray-600">
              Schliessen
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-gray-500 bg-gray-50">
                <tr>
                  <th className="px-4 py-2">Art.-Nr.</th>
                  <th className="px-4 py-2">Bezeichnung</th>
                  <th className="px-4 py-2">Hersteller</th>
                  <th className="px-4 py-2">Kategorie</th>
                  <th className="px-4 py-2 text-right">Preis (netto)</th>
                  <th className="px-4 py-2">Einheit</th>
                </tr>
              </thead>
              <tbody>
                {detail.produkte.map((p) => (
                  <tr key={p.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-xs">{p.artikel_nr ?? "—"}</td>
                    <td className="px-4 py-2 font-medium">{p.bezeichnung}</td>
                    <td className="px-4 py-2 text-gray-500">{p.hersteller ?? "—"}</td>
                    <td className="px-4 py-2 text-gray-500">{p.kategorie ?? "—"}</td>
                    <td className="px-4 py-2 text-right">{p.preis_netto.toFixed(2)} EUR</td>
                    <td className="px-4 py-2">{p.einheit}</td>
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
