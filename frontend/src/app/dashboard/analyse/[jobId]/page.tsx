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

interface KalkulationPosition {
  bezeichnung: string;
  kategorie: string;
  menge: number;
  einheit: string;
  einzelpreis?: number | null;
  gesamtpreis?: number | null;
  anbieter?: string | null;
  alternativen: Array<{
    anbieter: string;
    bezeichnung: string;
    preis_netto: number;
    einheit: string;
  }>;
  herkunft: string;
}

interface BestellPosition {
  bezeichnung: string;
  kategorie: string;
  menge: number;
  einheit: string;
  einzelpreis?: number | null;
  gesamtpreis?: number | null;
}

interface BestellGruppe {
  anbieter: string;
  positionen: BestellPosition[];
  anzahl_positionen: number;
  summe_netto: number;
}

interface Kundenangebot {
  material_einkauf: number;
  material_aufschlag_prozent: number;
  material_aufschlag_eur: number;
  material_verkauf: number;
  lohnstunden: number;
  stundensatz: number;
  lohnkosten: number;
  angebot_netto: number;
  mwst_prozent: number;
  mwst_eur: number;
  angebot_brutto: number;
  deckenflaeche_m2: number;
  wandflaeche_m2: number;
}

interface KalkulationData {
  positionen: KalkulationPosition[];
  gesamt_netto: number;
  positionen_mit_preis: number;
  positionen_ohne_preis: number;
  positionen_gesamt: number;
  bestellliste: BestellGruppe[];
  kundenangebot: Kundenangebot;
  filename?: string;
  plantyp?: string;
  geschoss?: string;
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

/** EUR formatter */
function eur(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "—";
  return val.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " EUR";
}

type KalkSubTab = "material" | "bestellung" | "angebot";

export default function AnalyseJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [status, setStatus] = useState<StatusData | null>(null);
  const [result, setResult] = useState<AnalyseResult | null>(null);
  const [activeTab, setActiveTab] = useState<"kalkulation" | "raeume" | "decken" | "waende" | "details">("kalkulation");
  const [kalkulation, setKalkulation] = useState<KalkulationData | null>(null);
  const [kalkulationLoading, setKalkulationLoading] = useState(false);
  const [kalkSubTab, setKalkSubTab] = useState<KalkSubTab>("material");

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
          // Auto-load Kalkulation
          setKalkulationLoading(true);
          const kalkRes = await fetch(`/api/v1/bauplan/${jobId}/kalkulation`);
          if (kalkRes.ok) setKalkulation(await kalkRes.json());
          setKalkulationLoading(false);
        }
      } catch { /* ignore */ }
    })();
  }, [jobId]);

  // Also load kalkulation when result first becomes available via polling
  useEffect(() => {
    if (result && !kalkulation && !kalkulationLoading) {
      setKalkulationLoading(true);
      fetch(`/api/v1/bauplan/${jobId}/kalkulation`)
        .then((r) => r.ok ? r.json() : null)
        .then((d) => { if (d) setKalkulation(d); })
        .catch(() => {})
        .finally(() => setKalkulationLoading(false));
    }
  }, [result, kalkulation, kalkulationLoading, jobId]);

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
    { key: "kalkulation" as const, label: `Kalkulation${kalkulation ? ` (${kalkulation.positionen_gesamt})` : ""}`, show: true },
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

        {/* Kalkulation Tab */}
        {currentTab === "kalkulation" && (
          <div>
            {kalkulationLoading ? (
              <div className="p-8 text-center">
                <div className="animate-spin h-8 w-8 border-4 border-primary-600 border-t-transparent rounded-full mx-auto" />
                <p className="text-gray-500 mt-3">Materialliste wird berechnet und Preise abgeglichen...</p>
              </div>
            ) : !kalkulation ? (
              <div className="p-8 text-center text-gray-500">Kalkulation konnte nicht geladen werden.</div>
            ) : (
              <>
                {/* Sub-Tabs */}
                <div className="flex border-b border-gray-200 bg-gray-50">
                  {([
                    { key: "material" as KalkSubTab, label: "Materialkosten (Einkauf)" },
                    { key: "bestellung" as KalkSubTab, label: "Bestellliste" },
                    { key: "angebot" as KalkSubTab, label: "Kundenangebot" },
                  ]).map((st) => (
                    <button
                      key={st.key}
                      onClick={() => setKalkSubTab(st.key)}
                      className={`px-5 py-2.5 text-sm font-medium transition-colors ${
                        kalkSubTab === st.key
                          ? "text-primary-700 border-b-2 border-primary-600 bg-white"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      {st.label}
                    </button>
                  ))}
                </div>

                {kalkulation.positionen_ohne_preis > 0 && kalkulation.positionen_mit_preis === 0 && (
                  <div className="px-6 py-3 bg-orange-50 border-b border-orange-200 text-sm text-orange-800">
                    Noch keine Preislisten hochgeladen. <a href="/dashboard/preislisten" className="underline font-medium">Preislisten hochladen</a>, um automatisch die guenstigsten Preise zu erhalten.
                  </div>
                )}

                {/* ═══ SUB-TAB: Materialkosten (Einkauf) ═══ */}
                {kalkSubTab === "material" && (
                  <>
                    <div className="px-6 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                      <span className="text-sm text-gray-500">{kalkulation.positionen_gesamt} Positionen &mdash; {kalkulation.positionen_mit_preis} mit Preis</span>
                      <span className="text-lg font-bold">Einkauf: {eur(kalkulation.gesamt_netto)}</span>
                    </div>
                    <table className="w-full text-sm">
                      <thead className="text-left text-gray-500 bg-gray-50">
                        <tr>
                          <th className="px-4 py-2">Material</th>
                          <th className="px-4 py-2">Kategorie</th>
                          <th className="px-4 py-2 text-right">Menge</th>
                          <th className="px-4 py-2">Einheit</th>
                          <th className="px-4 py-2 text-right">Einzelpreis</th>
                          <th className="px-4 py-2 text-right">Gesamt</th>
                          <th className="px-4 py-2">Anbieter</th>
                        </tr>
                      </thead>
                      <tbody>
                        {kalkulation.positionen.map((pos, i) => (
                          <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                            <td className="px-4 py-3 font-medium">{pos.bezeichnung}</td>
                            <td className="px-4 py-3"><span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{pos.kategorie}</span></td>
                            <td className="px-4 py-3 text-right font-mono">{pos.menge.toLocaleString("de-DE", { minimumFractionDigits: 1 })}</td>
                            <td className="px-4 py-3">{pos.einheit}</td>
                            <td className="px-4 py-3 text-right">{pos.einzelpreis != null ? eur(pos.einzelpreis) : <span className="text-orange-500">&mdash;</span>}</td>
                            <td className="px-4 py-3 text-right font-medium">{pos.gesamtpreis != null ? eur(pos.gesamtpreis) : <span className="text-orange-500">kein Preis</span>}</td>
                            <td className="px-4 py-3">{pos.anbieter ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">{pos.anbieter}</span> : <span className="text-xs text-gray-400">—</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-gray-50 font-semibold">
                        <tr className="border-t-2 border-gray-300">
                          <td className="px-4 py-3" colSpan={5}>Einkaufspreis gesamt (netto)</td>
                          <td className="px-4 py-3 text-right text-lg">{eur(kalkulation.gesamt_netto)}</td>
                          <td></td>
                        </tr>
                      </tfoot>
                    </table>
                  </>
                )}

                {/* ═══ SUB-TAB: Bestellliste ═══ */}
                {kalkSubTab === "bestellung" && (
                  <div className="divide-y divide-gray-200">
                    {kalkulation.bestellliste.length === 0 ? (
                      <div className="p-8 text-center text-gray-500">Keine Bestellungen &mdash; erst Preislisten hochladen.</div>
                    ) : (
                      kalkulation.bestellliste.map((gruppe, gi) => (
                        <div key={gi}>
                          <div className="px-6 py-4 bg-gray-50 flex items-center justify-between">
                            <div>
                              <span className="font-semibold text-gray-900">{gruppe.anbieter}</span>
                              <span className="text-sm text-gray-500 ml-3">{gruppe.anzahl_positionen} Positionen</span>
                            </div>
                            <span className="text-lg font-bold text-gray-900">{eur(gruppe.summe_netto)}</span>
                          </div>
                          <table className="w-full text-sm">
                            <thead className="text-left text-gray-400 text-xs">
                              <tr>
                                <th className="px-6 py-1">Material</th>
                                <th className="px-4 py-1 text-right">Menge</th>
                                <th className="px-4 py-1">Einheit</th>
                                <th className="px-4 py-1 text-right">Einzelpreis</th>
                                <th className="px-4 py-1 text-right">Gesamt</th>
                              </tr>
                            </thead>
                            <tbody>
                              {gruppe.positionen.map((pos, pi) => (
                                <tr key={pi} className="border-t border-gray-50 hover:bg-gray-50">
                                  <td className="px-6 py-2">{pos.bezeichnung}</td>
                                  <td className="px-4 py-2 text-right font-mono">{pos.menge.toLocaleString("de-DE", { minimumFractionDigits: 1 })}</td>
                                  <td className="px-4 py-2">{pos.einheit}</td>
                                  <td className="px-4 py-2 text-right">{eur(pos.einzelpreis)}</td>
                                  <td className="px-4 py-2 text-right font-medium">{eur(pos.gesamtpreis)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ))
                    )}
                    {kalkulation.bestellliste.length > 0 && (
                      <div className="px-6 py-4 bg-gray-100 flex items-center justify-between font-semibold">
                        <span>Gesamtsumme alle Lieferanten</span>
                        <span className="text-xl">{eur(kalkulation.gesamt_netto)}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* ═══ SUB-TAB: Kundenangebot ═══ */}
                {kalkSubTab === "angebot" && (
                  <div className="p-6 space-y-6">
                    <div className="grid grid-cols-2 gap-6">
                      {/* Linke Spalte: Kalkulation */}
                      <div className="space-y-4">
                        <h4 className="font-semibold text-gray-900 text-lg">Angebotskalkulation</h4>
                        <table className="w-full text-sm">
                          <tbody>
                            <tr className="border-b border-gray-100">
                              <td className="py-3 text-gray-600">Material (Einkauf netto)</td>
                              <td className="py-3 text-right font-mono">{eur(kalkulation.kundenangebot.material_einkauf)}</td>
                            </tr>
                            <tr className="border-b border-gray-100">
                              <td className="py-3 text-gray-600">+ Aufschlag Material ({kalkulation.kundenangebot.material_aufschlag_prozent}%)</td>
                              <td className="py-3 text-right font-mono">{eur(kalkulation.kundenangebot.material_aufschlag_eur)}</td>
                            </tr>
                            <tr className="border-b border-gray-200 font-medium">
                              <td className="py-3">= Material (Verkauf)</td>
                              <td className="py-3 text-right font-mono">{eur(kalkulation.kundenangebot.material_verkauf)}</td>
                            </tr>
                            <tr className="border-b border-gray-100">
                              <td className="py-3 text-gray-600">
                                Lohnkosten ({kalkulation.kundenangebot.lohnstunden}h x {kalkulation.kundenangebot.stundensatz} EUR/h)
                              </td>
                              <td className="py-3 text-right font-mono">{eur(kalkulation.kundenangebot.lohnkosten)}</td>
                            </tr>
                            <tr className="border-b border-gray-300 font-semibold text-lg">
                              <td className="py-4">Angebot netto</td>
                              <td className="py-4 text-right font-mono">{eur(kalkulation.kundenangebot.angebot_netto)}</td>
                            </tr>
                            <tr className="border-b border-gray-100">
                              <td className="py-3 text-gray-600">+ MwSt. ({kalkulation.kundenangebot.mwst_prozent}%)</td>
                              <td className="py-3 text-right font-mono">{eur(kalkulation.kundenangebot.mwst_eur)}</td>
                            </tr>
                            <tr className="font-bold text-xl">
                              <td className="py-4 text-primary-700">Angebotspreis brutto</td>
                              <td className="py-4 text-right font-mono text-primary-700">{eur(kalkulation.kundenangebot.angebot_brutto)}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      {/* Rechte Spalte: Kennzahlen */}
                      <div className="space-y-4">
                        <h4 className="font-semibold text-gray-900 text-lg">Kennzahlen</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="bg-blue-50 rounded-lg p-4">
                            <p className="text-xs text-blue-600">Deckenflaeche</p>
                            <p className="text-2xl font-bold text-blue-900">{kalkulation.kundenangebot.deckenflaeche_m2} m2</p>
                          </div>
                          <div className="bg-blue-50 rounded-lg p-4">
                            <p className="text-xs text-blue-600">Wandflaeche</p>
                            <p className="text-2xl font-bold text-blue-900">{kalkulation.kundenangebot.wandflaeche_m2} m2</p>
                          </div>
                          <div className="bg-green-50 rounded-lg p-4">
                            <p className="text-xs text-green-600">Montage-Stunden</p>
                            <p className="text-2xl font-bold text-green-900">{kalkulation.kundenangebot.lohnstunden}h</p>
                          </div>
                          <div className="bg-green-50 rounded-lg p-4">
                            <p className="text-xs text-green-600">Stundensatz</p>
                            <p className="text-2xl font-bold text-green-900">{kalkulation.kundenangebot.stundensatz} EUR</p>
                          </div>
                          <div className="bg-purple-50 rounded-lg p-4">
                            <p className="text-xs text-purple-600">Material-Marge</p>
                            <p className="text-2xl font-bold text-purple-900">{kalkulation.kundenangebot.material_aufschlag_prozent}%</p>
                          </div>
                          <div className="bg-purple-50 rounded-lg p-4">
                            <p className="text-xs text-purple-600">Preis / m2 Decke</p>
                            <p className="text-2xl font-bold text-purple-900">
                              {kalkulation.kundenangebot.deckenflaeche_m2 > 0
                                ? fmt(kalkulation.kundenangebot.angebot_netto / kalkulation.kundenangebot.deckenflaeche_m2, 2)
                                : "—"} EUR
                            </p>
                          </div>
                        </div>
                        <p className="text-xs text-gray-400 mt-4">
                          Aufschlaege und Stundensatz koennen in den Einstellungen angepasst werden.
                          Die Werte dienen als Kalkulationsgrundlage.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

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
