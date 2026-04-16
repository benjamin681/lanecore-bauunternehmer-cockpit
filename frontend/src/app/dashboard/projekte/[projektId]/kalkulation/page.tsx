"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

// ── Type definitions (same as analyse kalkulation) ──

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

interface ZusatzkostenPosition {
  bezeichnung: string;
  betrag: number;
}

interface Kundenangebot {
  material_einkauf: number;
  material_aufschlag_prozent: number;
  material_aufschlag_eur: number;
  material_verkauf: number;
  lohnstunden: number;
  stundensatz: number;
  stundensatz_eigen: number;
  stundensatz_sub: number;
  stunden_eigen: number;
  stunden_sub: number;
  lohnkosten_eigen: number;
  lohnkosten_sub: number;
  lohnkosten: number;
  anteil_eigenleistung: number;
  stunden_pro_m2_decke: number;
  stunden_pro_m2_wand: number;
  zusatzkosten: ZusatzkostenPosition[];
  zusatzkosten_summe: number;
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
  analysen_count: number;
  projekt_id?: string;
  projekt_name?: string;
}

type KalkSubTab = "material" | "bestellung" | "angebot";

/** EUR formatter */
function eur(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "\u2014";
  return val.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " EUR";
}

function fmt(val: number | null | undefined, decimals = 2): string {
  if (val == null || isNaN(val)) return "\u2014";
  return val.toFixed(decimals);
}

export default function ProjektKalkulationPage() {
  const { projektId } = useParams<{ projektId: string }>();
  const [kalkulation, setKalkulation] = useState<KalkulationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kalkSubTab, setKalkSubTab] = useState<KalkSubTab>("material");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/v1/projekte/${projektId}/kalkulation`);
        if (!res.ok) {
          setError(`Fehler ${res.status}: ${res.statusText}`);
          return;
        }
        const data: KalkulationData = await res.json();
        setKalkulation(data);
      } catch {
        setError("Netzwerkfehler beim Laden der Kalkulation.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projektId]);

  if (loading) {
    return (
      <div className="p-12 text-center">
        <div className="animate-spin h-8 w-8 border-4 border-primary-600 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-500 mt-3">Projekt-Gesamtkalkulation wird berechnet...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-12 text-center">
        <p className="text-red-600 text-lg mb-2">Fehler</p>
        <p className="text-gray-500">{error}</p>
        <a href="/dashboard/projekte" className="mt-4 inline-block text-primary-600 hover:underline">
          Zurueck zu Projekte
        </a>
      </div>
    );
  }

  if (!kalkulation || kalkulation.analysen_count === 0) {
    return (
      <div className="p-12 text-center">
        <p className="text-gray-500 text-lg mb-2">Keine abgeschlossenen Analysen</p>
        <p className="text-sm text-gray-400">
          Dieses Projekt hat noch keine abgeschlossenen Bauplan-Analysen. Laden Sie zuerst Bauplaene hoch.
        </p>
        <a href="/dashboard/projekte" className="mt-4 inline-block text-primary-600 hover:underline">
          Zurueck zu Projekte
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <a href="/dashboard/projekte" className="text-sm text-primary-600 hover:underline mb-1 inline-block">
            &larr; Zurueck zu Projekte
          </a>
          <h2 className="text-lg md:text-2xl font-bold text-gray-900">
            Projekt-Gesamtkalkulation
          </h2>
          {kalkulation.projekt_name && (
            <p className="text-sm text-gray-500 mt-1">
              {kalkulation.projekt_name} &mdash; {kalkulation.analysen_count} Analyse{kalkulation.analysen_count !== 1 ? "n" : ""} zusammengefasst
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-primary-100 text-primary-700 text-sm font-medium rounded-lg">
            {kalkulation.analysen_count} Analyse{kalkulation.analysen_count !== 1 ? "n" : ""}
          </span>
        </div>
      </div>

      {/* Main Content */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Sub-Tabs */}
        <div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto">
          {([
            { key: "material" as KalkSubTab, label: "Materialkosten (Einkauf)" },
            { key: "bestellung" as KalkSubTab, label: "Bestellliste" },
            { key: "angebot" as KalkSubTab, label: "Kundenangebot" },
          ]).map((st) => (
            <button
              key={st.key}
              onClick={() => setKalkSubTab(st.key)}
              className={`px-3 md:px-5 py-2.5 text-xs md:text-sm font-medium transition-colors whitespace-nowrap ${
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

        {/* Material Sub-Tab */}
        {kalkSubTab === "material" && (
          <>
            <div className="px-3 md:px-6 py-3 bg-gray-50 border-b border-gray-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-2">
              <span className="text-sm text-gray-500">
                {kalkulation.positionen_gesamt} Positionen &mdash; {kalkulation.positionen_mit_preis} mit Preis
              </span>
              <span className="text-lg font-bold">Einkauf: {eur(kalkulation.gesamt_netto)}</span>
            </div>
            <div className="overflow-x-auto">
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
                {(kalkulation.positionen ?? []).map((pos, i) => (
                  <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{pos.bezeichnung}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{pos.kategorie}</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {(pos.menge ?? 0).toLocaleString("de-DE", { minimumFractionDigits: 1 })}
                    </td>
                    <td className="px-4 py-3">{pos.einheit}</td>
                    <td className="px-4 py-3 text-right">
                      {pos.einzelpreis != null ? eur(pos.einzelpreis) : <span className="text-orange-500">&mdash;</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">
                      {pos.gesamtpreis != null ? eur(pos.gesamtpreis) : <span className="text-orange-500">kein Preis</span>}
                    </td>
                    <td className="px-4 py-3">
                      {pos.anbieter
                        ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">{pos.anbieter}</span>
                        : <span className="text-xs text-gray-400">&mdash;</span>}
                    </td>
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
            </div>
          </>
        )}

        {/* Bestellliste Sub-Tab */}
        {kalkSubTab === "bestellung" && (
          <div className="divide-y divide-gray-200">
            {(kalkulation.bestellliste ?? []).length === 0 ? (
              <div className="p-8 text-center text-gray-500">Keine Bestellungen &mdash; erst Preislisten hochladen.</div>
            ) : (
              (kalkulation.bestellliste ?? []).map((gruppe, gi) => (
                <div key={gi}>
                  <div className="px-6 py-4 bg-gray-50 flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-gray-900">{gruppe.anbieter}</span>
                      <span className="text-sm text-gray-500 ml-3">{gruppe.anzahl_positionen} Positionen</span>
                    </div>
                    <span className="text-lg font-bold text-gray-900">{eur(gruppe.summe_netto)}</span>
                  </div>
                  <div className="overflow-x-auto">
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
                      {(gruppe.positionen ?? []).map((pos, pi) => (
                        <tr key={pi} className="border-t border-gray-50 hover:bg-gray-50">
                          <td className="px-6 py-2">{pos.bezeichnung}</td>
                          <td className="px-4 py-2 text-right font-mono">{(pos.menge ?? 0).toLocaleString("de-DE", { minimumFractionDigits: 1 })}</td>
                          <td className="px-4 py-2">{pos.einheit}</td>
                          <td className="px-4 py-2 text-right">{eur(pos.einzelpreis)}</td>
                          <td className="px-4 py-2 text-right font-medium">{eur(pos.gesamtpreis)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                </div>
              ))
            )}
            {(kalkulation.bestellliste ?? []).length > 0 && (
              <div className="px-6 py-4 bg-gray-100 flex items-center justify-between font-semibold">
                <span>Gesamtsumme alle Lieferanten</span>
                <span className="text-xl">{eur(kalkulation.gesamt_netto)}</span>
              </div>
            )}
          </div>
        )}

        {/* Kundenangebot Sub-Tab (read-only for project level) */}
        {kalkSubTab === "angebot" && kalkulation?.kundenangebot && (
          <div className="p-3 md:p-6 space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
              {/* Angebotskalkulation */}
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
                        Lohn eigene MA ({kalkulation.kundenangebot.stunden_eigen}h x {kalkulation.kundenangebot.stundensatz_eigen} EUR/h)
                      </td>
                      <td className="py-3 text-right font-mono">{eur(kalkulation.kundenangebot.lohnkosten_eigen)}</td>
                    </tr>
                    <tr className="border-b border-gray-100">
                      <td className="py-3 text-gray-600">
                        Lohn Sub ({kalkulation.kundenangebot.stunden_sub}h x {kalkulation.kundenangebot.stundensatz_sub} EUR/h)
                      </td>
                      <td className="py-3 text-right font-mono">{eur(kalkulation.kundenangebot.lohnkosten_sub)}</td>
                    </tr>
                    {(kalkulation.kundenangebot?.zusatzkosten_summe ?? 0) > 0 && (
                      <>
                        {(kalkulation.kundenangebot?.zusatzkosten ?? []).map((z, zi) => (
                          <tr key={zi} className="border-b border-gray-100">
                            <td className="py-3 text-gray-600">+ {z.bezeichnung || "Zusatzkosten"}</td>
                            <td className="py-3 text-right font-mono">{eur(z.betrag)}</td>
                          </tr>
                        ))}
                      </>
                    )}
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

              {/* Kennzahlen */}
              <div className="space-y-4">
                <h4 className="font-semibold text-gray-900 text-lg">Kennzahlen</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-blue-50 rounded-lg p-4">
                    <p className="text-xs text-blue-600">Deckenflaeche</p>
                    <p className="text-lg md:text-2xl font-bold text-blue-900">{kalkulation.kundenangebot?.deckenflaeche_m2 ?? 0} m2</p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4">
                    <p className="text-xs text-blue-600">Wandflaeche</p>
                    <p className="text-lg md:text-2xl font-bold text-blue-900">{kalkulation.kundenangebot?.wandflaeche_m2 ?? 0} m2</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4">
                    <p className="text-xs text-green-600">Montage-Stunden gesamt</p>
                    <p className="text-lg md:text-2xl font-bold text-green-900">{kalkulation.kundenangebot?.lohnstunden ?? 0}h</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4">
                    <p className="text-xs text-green-600">Mischkalkulation /h</p>
                    <p className="text-lg md:text-2xl font-bold text-green-900">{fmt(kalkulation.kundenangebot?.stundensatz, 2)} EUR</p>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-4">
                    <p className="text-xs text-purple-600">Material-Marge</p>
                    <p className="text-lg md:text-2xl font-bold text-purple-900">{kalkulation.kundenangebot?.material_aufschlag_prozent ?? 0}%</p>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-4">
                    <p className="text-xs text-purple-600">Analysen zusammengefasst</p>
                    <p className="text-lg md:text-2xl font-bold text-purple-900">{kalkulation.analysen_count}</p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-4">
                    <p className="text-xs text-orange-600">Preis / m2 Decke</p>
                    <p className="text-lg md:text-2xl font-bold text-orange-900">
                      {(kalkulation.kundenangebot?.deckenflaeche_m2 ?? 0) > 0
                        ? fmt((kalkulation.kundenangebot?.angebot_netto ?? 0) / ((kalkulation.kundenangebot?.deckenflaeche_m2 ?? 0) + (kalkulation.kundenangebot?.wandflaeche_m2 ?? 0) || 1), 2) + " EUR"
                        : "\u2014"}
                    </p>
                  </div>
                  <div className="bg-orange-50 rounded-lg p-4">
                    <p className="text-xs text-orange-600">Positionen mit Preis</p>
                    <p className="text-lg md:text-2xl font-bold text-orange-900">
                      {kalkulation.positionen_mit_preis} / {kalkulation.positionen_gesamt}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
