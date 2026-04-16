"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

/** Editable kalkulation parameters (sent via POST) */
interface KalkParams {
  material_aufschlag_prozent: number;
  stundensatz_eigen: number;
  stundensatz_sub: number;
  stunden_pro_m2_decke: number;
  stunden_pro_m2_wand: number;
  anteil_eigenleistung: number;
  zusatzkosten: ZusatzkostenPosition[];
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
  keine_elemente?: boolean;
  hinweis?: string;
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

/** Default kalkulation params — extracted from first server response */
function defaultKalkParams(angebot?: Kundenangebot): KalkParams {
  return {
    material_aufschlag_prozent: angebot?.material_aufschlag_prozent ?? 15,
    stundensatz_eigen: angebot?.stundensatz_eigen ?? 45,
    stundensatz_sub: angebot?.stundensatz_sub ?? 35,
    stunden_pro_m2_decke: angebot?.stunden_pro_m2_decke ?? 0.5,
    stunden_pro_m2_wand: angebot?.stunden_pro_m2_wand ?? 0.8,
    anteil_eigenleistung: angebot?.anteil_eigenleistung ?? 0.3,
    zusatzkosten: angebot?.zusatzkosten ?? [],
  };
}

/** Inline editable number input with German formatting */
function EditNum({
  value,
  onChange,
  step = 1,
  min,
  max,
  suffix,
  className = "",
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  suffix?: string;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      <input
        type="number"
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(e) => {
          const v = parseFloat(e.target.value);
          if (!isNaN(v)) onChange(v);
        }}
        className="w-20 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
      />
      {suffix && <span className="text-xs text-gray-500">{suffix}</span>}
    </span>
  );
}

export default function AnalyseJobPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [status, setStatus] = useState<StatusData | null>(null);
  const [result, setResult] = useState<AnalyseResult | null>(null);
  const [activeTab, setActiveTab] = useState<"kalkulation" | "raeume" | "decken" | "waende" | "details">("kalkulation");
  const [kalkulation, setKalkulation] = useState<KalkulationData | null>(null);
  const [kalkulationLoading, setKalkulationLoading] = useState(false);
  const [kalkSubTab, setKalkSubTab] = useState<KalkSubTab>("material");

  // --- Editable analysis result state ---
  const [editedRaeume, setEditedRaeume] = useState<Record<string, Partial<Raum>>>({});
  const [editedDecken, setEditedDecken] = useState<Record<string, Partial<Decke>>>({});
  const [editedWaende, setEditedWaende] = useState<Record<string, Partial<Wand>>>({});
  const [analysisSaving, setAnalysisSaving] = useState(false);

  const unsavedCount =
    Object.keys(editedRaeume).length +
    Object.keys(editedDecken).length +
    Object.keys(editedWaende).length;

  /** Save edited analysis values via PATCH, then refresh kalkulation */
  const saveAnalysisEdits = useCallback(async () => {
    if (!result || unsavedCount === 0) return;
    setAnalysisSaving(true);
    try {
      const body: Record<string, unknown> = {};
      if (Object.keys(editedRaeume).length > 0) {
        body.raeume = (result.raeume ?? []).map((r, i) => ({
          ...r,
          ...editedRaeume[String(i)],
        }));
      }
      if (Object.keys(editedDecken).length > 0) {
        body.decken = (result.decken ?? []).map((d, i) => ({
          ...d,
          ...editedDecken[String(i)],
        }));
      }
      if (Object.keys(editedWaende).length > 0) {
        body.waende = (result.waende ?? []).map((w, i) => ({
          ...w,
          ...editedWaende[String(i)],
        }));
      }
      const res = await fetch(`/api/v1/bauplan/${jobId}/result`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const updated: AnalyseResult = await res.json();
        setResult(updated);
        setEditedRaeume({});
        setEditedDecken({});
        setEditedWaende({});
        // Refresh kalkulation with new values
        setKalkulationLoading(true);
        const kalkRes = await fetch(`/api/v1/bauplan/${jobId}/kalkulation`);
        if (kalkRes.ok) {
          const kalkData: KalkulationData = await kalkRes.json();
          setKalkulation(kalkData);
          setKalkParams(defaultKalkParams(kalkData.kundenangebot));
        }
        setKalkulationLoading(false);
      }
    } catch { /* ignore */ }
    finally { setAnalysisSaving(false); }
  }, [result, editedRaeume, editedDecken, editedWaende, jobId, unsavedCount]);

  // --- Editable kalkulation state ---
  const [kalkParams, setKalkParams] = useState<KalkParams | null>(null);
  const [mengenOverrides, setMengenOverrides] = useState<Record<string, number>>({});
  const [recalculating, setRecalculating] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** POST custom params to recalculate kalkulation */
  const recalculate = useCallback(
    (params: KalkParams, mengen: Record<string, number>) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        setRecalculating(true);
        try {
          const body: Record<string, unknown> = { ...params };
          if (Object.keys(mengen).length > 0) {
            body.mengen_overrides = mengen;
          }
          const res = await fetch(`/api/v1/bauplan/${jobId}/kalkulation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          if (res.ok) {
            const data: KalkulationData = await res.json();
            setKalkulation(data);
          }
        } catch {
          // silently ignore recalc errors
        } finally {
          setRecalculating(false);
        }
      }, 400); // 400ms debounce for "instant" feel
    },
    [jobId],
  );

  /** Update a single kalkulation param and trigger recalc */
  const updateParam = useCallback(
    <K extends keyof KalkParams>(key: K, value: KalkParams[K]) => {
      setKalkParams((prev) => {
        if (!prev) return prev;
        const next = { ...prev, [key]: value };
        recalculate(next, mengenOverrides);
        return next;
      });
    },
    [recalculate, mengenOverrides],
  );

  /** Update a material menge override and trigger recalc */
  const updateMenge = useCallback(
    (bezeichnung: string, menge: number) => {
      setMengenOverrides((prev) => {
        const next = { ...prev, [bezeichnung]: menge };
        if (kalkParams) recalculate(kalkParams, next);
        return next;
      });
    },
    [recalculate, kalkParams],
  );

  // SSE live progress
  useEffect(() => {
    if (status?.status === "completed" || status?.status === "failed") return;

    const es = new EventSource(`/api/v1/bauplan/${jobId}/stream`);
    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus((prev) => ({ ...prev, ...data, job_id: jobId }));

      if (data.status === "completed") {
        es.close();
        // Load result + kalkulation
        fetch(`/api/v1/bauplan/${jobId}/result`).then((r) => r.ok ? r.json() : null).then((d) => { if (d) setResult(d); });
        fetch(`/api/v1/bauplan/${jobId}/kalkulation`).then((r) => r.ok ? r.json() : null).then((d) => { if (d) setKalkulation(d); });
      }
      if (data.status === "failed") {
        es.close();
      }
    };
    es.onerror = () => { es.close(); };

    return () => es.close();
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

  // Initialize editable kalkParams from first kalkulation load
  useEffect(() => {
    if (kalkulation && !kalkParams) {
      setKalkParams(defaultKalkParams(kalkulation.kundenangebot));
    }
  }, [kalkulation, kalkParams]);

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

  // Normalize potentially null arrays from API
  const raeume = result.raeume ?? [];
  const decken = result.decken ?? [];
  const waende = result.waende ?? [];
  const details = result.details ?? [];
  const warnungen = result.warnungen ?? [];
  const gestrichene = result.gestrichene_positionen ?? [];

  // Detect empty results (no elements recognised)
  const hasNoElements = raeume.length === 0 && decken.length === 0 && waende.length === 0;

  const konfidenzPct = Math.round((result.konfidenz ?? 0) * 100);
  const konfidenzColor =
    hasNoElements ? "text-red-700 bg-red-100" :
    konfidenzPct >= 90 ? "text-green-700 bg-green-100" :
    konfidenzPct >= 70 ? "text-yellow-700 bg-yellow-100" :
    "text-red-700 bg-red-100";
  const konfidenzBarColor =
    konfidenzPct >= 80 ? "bg-green-500" :
    konfidenzPct >= 60 ? "bg-yellow-500" :
    "bg-red-500";
  const planqualitaet =
    konfidenzPct >= 80 ? { label: "Gut", color: "text-green-700" } :
    konfidenzPct >= 60 ? { label: "Mittel", color: "text-yellow-700" } :
    { label: "Schlecht", color: "text-red-700" };

  // Classify warnings by severity
  const classifyWarning = (w: string) => {
    const upper = w.toUpperCase();
    if (upper.includes("NOTWENDIG") || upper.includes("DRINGEND")) return "kritisch";
    return "warnung";
  };
  const kritischeWarnungen = warnungen.filter((w) => classifyWarning(w) === "kritisch");
  const normaleWarnungen = warnungen.filter((w) => classifyWarning(w) === "warnung");

  // Extract room number references from warnings for click-to-scroll
  const roomRefPattern = /\b(\d+\.\d+\.\d+)\b/;
  const scrollToRoom = (roomNr: string) => {
    setActiveTab("raeume");
    // Allow tab to render, then scroll
    setTimeout(() => {
      const el = document.getElementById(`raum-${roomNr}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 100);
  };

  const renderWarningText = (w: string) => {
    const match = w.match(roomRefPattern);
    if (!match) return <>{w}</>;
    const roomNr = match[1];
    const parts = w.split(roomNr);
    return (
      <>
        {parts[0]}
        <button
          onClick={() => scrollToRoom(roomNr)}
          className="underline font-medium hover:text-primary-600 cursor-pointer"
        >
          {roomNr}
        </button>
        {parts.slice(1).join(roomNr)}
      </>
    );
  };

  const tabs = [
    { key: "kalkulation" as const, label: `Kalkulation${kalkulation ? ` (${kalkulation.positionen_gesamt})` : ""}`, show: !hasNoElements },
    { key: "raeume" as const, label: `Raume (${raeume.length})`, show: raeume.length > 0 },
    { key: "decken" as const, label: `Decken (${decken.length})`, show: decken.length > 0 },
    { key: "waende" as const, label: `Wande (${waende.length})`, show: waende.length > 0 },
    { key: "details" as const, label: `Details (${details.length})`, show: details.length > 0 },
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
          <h2 className="text-lg md:text-2xl font-bold text-gray-900">Analyse-Ergebnis</h2>
          <p className="text-sm text-gray-500 mt-1">
            {result.plantyp && <span className="capitalize">{result.plantyp}</span>}
            {result.massstab && <span> &mdash; Massstab {result.massstab}</span>}
            {result.geschoss && <span> &mdash; {result.geschoss}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2 md:gap-3 flex-wrap">
          {!hasNoElements && (
            <>
              {kalkulation && kalkulation.positionen_mit_preis === 0 ? (
                <span
                  title="Preislisten erforderlich"
                  className="px-3 md:px-4 py-2 bg-gray-300 text-gray-500 rounded-lg text-xs md:text-sm font-medium cursor-not-allowed"
                >
                  Angebot als PDF
                </span>
              ) : (
                <a
                  href={`/api/v1/bauplan/${jobId}/angebot-pdf`}
                  download
                  className="px-3 md:px-4 py-2 bg-blue-600 text-white rounded-lg text-xs md:text-sm font-medium hover:bg-blue-700 transition-colors"
                >
                  Angebot als PDF
                </a>
              )}
              <a
                href={`/api/v1/bauplan/${jobId}/export`}
                download
                className="px-3 md:px-4 py-2 bg-green-600 text-white rounded-lg text-xs md:text-sm font-medium hover:bg-green-700 transition-colors"
              >
                Excel herunterladen
              </a>
            </>
          )}
          <span className={`px-3 py-1.5 rounded-lg text-sm font-medium ${konfidenzColor}`}>
            {hasNoElements ? "Keine Analyse moeglich" : `Konfidenz: ${konfidenzPct}%`}
          </span>
        </div>
      </div>

      {/* Audit Info */}
      {result.model_used && (
        <div className="flex flex-wrap gap-2 md:gap-4 text-xs text-gray-400">
          <span>Modell: {result.model_used}</span>
          {result.input_tokens != null && <span>Input: {result.input_tokens.toLocaleString()} Tokens</span>}
          {result.output_tokens != null && <span>Output: {result.output_tokens.toLocaleString()} Tokens</span>}
          {result.cost_usd != null && <span>Kosten: ${result.cost_usd.toFixed(4)}</span>}
        </div>
      )}

      {/* Empty results warning banner */}
      {hasNoElements && (
        <div className="bg-red-50 border-2 border-red-300 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="text-3xl flex-shrink-0">&#9888;</div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-red-800 mb-2">
                Keine Bauelemente erkannt
              </h3>
              <p className="text-red-700 mb-4">
                Moegliche Ursachen: Die hochgeladene Datei ist kein Bauplan
                (z.B. Angebot, Rechnung), der Plan ist zu niedrig aufgeloest,
                oder das Format wird nicht unterstuetzt.
              </p>
              <a
                href="/dashboard/analyse"
                className="inline-block bg-primary-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-primary-700 transition-colors"
              >
                Neuen Plan hochladen
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Qualitaets-Report */}
      <div className="bg-white rounded-xl border border-gray-200 p-3 md:p-5">
        <h3 className="font-semibold text-gray-900 mb-4">Qualitaets-Report</h3>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 md:gap-4">
          {/* Konfidenz-Bar */}
          <div>
            <p className="text-xs text-gray-500 mb-1">Konfidenz</p>
            {hasNoElements ? (
              <p className="text-sm font-bold text-red-700">Keine Analyse moeglich</p>
            ) : (
              <>
                <div className="w-full bg-gray-200 rounded-full h-3 mb-1">
                  <div
                    className={`h-3 rounded-full transition-all duration-500 ${konfidenzBarColor}`}
                    style={{ width: `${konfidenzPct}%` }}
                  />
                </div>
                <p className={`text-sm font-bold ${konfidenzPct >= 80 ? "text-green-700" : konfidenzPct >= 60 ? "text-yellow-700" : "text-red-700"}`}>
                  {konfidenzPct}%
                </p>
              </>
            )}
          </div>

          {/* Planqualitaet */}
          <div>
            <p className="text-xs text-gray-500 mb-1">Planqualitaet</p>
            <p className={`text-lg font-bold ${hasNoElements ? "text-red-700" : planqualitaet.color}`}>
              {hasNoElements ? "Nicht erkannt" : planqualitaet.label}
            </p>
          </div>

          {/* Erkannte Elemente */}
          <div>
            <p className="text-xs text-gray-500 mb-1">Erkannte Elemente</p>
            <p className="text-sm font-medium text-gray-900">
              {raeume.length} Raeume, {decken.length} Decken, {waende.length} Waende
            </p>
          </div>

          {/* Gestrichene Positionen */}
          <div>
            <p className="text-xs text-gray-500 mb-1">Gestrichene Pos.</p>
            <p className="text-lg font-bold text-gray-900">{gestrichene.length}</p>
          </div>

          {/* Empfehlung */}
          <div>
            <p className="text-xs text-gray-500 mb-1">Empfehlung</p>
            {hasNoElements ? (
              <p className="text-sm text-red-600 font-medium">Anderen Plan hochladen</p>
            ) : konfidenzPct < 70 ? (
              <p className="text-sm text-red-600 font-medium">Plan in hoeherer Aufloesung hochladen</p>
            ) : (
              <p className="text-sm text-green-600 font-medium">Ergebnis plausibel</p>
            )}
          </div>
        </div>
      </div>

      {/* Warnings - grouped by severity */}
      {warnungen.length > 0 && (
        <div className="space-y-3">
          {/* Kritische Warnungen */}
          {kritischeWarnungen.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-5">
              <p className="font-medium text-red-800 mb-2">
                {kritischeWarnungen.length} Kritisch{kritischeWarnungen.length > 1 ? "e" : "er"} Hinweis{kritischeWarnungen.length > 1 ? "e" : ""}
              </p>
              <ul className="list-disc list-inside space-y-1 text-sm text-red-700">
                {kritischeWarnungen.map((w, i) => (
                  <li key={i}>{renderWarningText(w)}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Normale Warnungen */}
          {normaleWarnungen.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5">
              <p className="font-medium text-yellow-800 mb-2">
                {normaleWarnungen.length} Warnung{normaleWarnungen.length > 1 ? "en" : ""}
              </p>
              <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700">
                {normaleWarnungen.map((w, i) => (
                  <li key={i}>{renderWarningText(w)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Gestrichene Positionen */}
      {gestrichene.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5">
          <p className="font-medium text-red-800 mb-2">
            {gestrichene.length} gestrichene Position{gestrichene.length > 1 ? "en" : ""} &mdash; NICHT kalkulieren
          </p>
          <ul className="space-y-2 text-sm text-red-700">
            {gestrichene.map((g, i) => (
              <li key={i}>
                <strong>{g.bezeichnung}</strong>: {g.grund}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Unsaved analysis edits bar */}
      {unsavedCount > 0 && (
        <div className="flex items-center justify-between bg-yellow-50 border border-yellow-200 rounded-xl px-5 py-3">
          <span className="text-sm text-yellow-800 font-medium">
            {unsavedCount} Wert{unsavedCount > 1 ? "e" : ""} geaendert
          </span>
          <button
            onClick={saveAnalysisEdits}
            disabled={analysisSaving}
            className="px-5 py-2 bg-yellow-600 text-white rounded-lg text-sm font-medium hover:bg-yellow-700 transition-colors disabled:opacity-50"
          >
            {analysisSaving ? "Speichern..." : "Speichern"}
          </button>
        </div>
      )}

      {/* Tabs */}
      {tabs.length > 0 && (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-200 overflow-x-auto -mx-px">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 md:px-6 py-3 text-xs md:text-sm font-medium transition-colors whitespace-nowrap ${
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
            ) : kalkulation.keine_elemente ? (
              <div className="p-8 text-center">
                <p className="text-red-600 font-medium mb-2">Keine kalkulierbaren Bauelemente vorhanden</p>
                <p className="text-gray-500 text-sm">{kalkulation.hinweis || "Die Analyse hat keine Waende oder Decken mit gueltigen Massen erkannt."}</p>
              </div>
            ) : (
              <>
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
                  <div className="mx-6 mt-4 p-4 bg-orange-50 border border-orange-300 rounded-lg">
                    <p className="font-semibold text-orange-800 mb-1">Noch keine Preislisten hochgeladen</p>
                    <p className="text-sm text-orange-700">
                      Laden Sie Preislisten Ihrer Lieferanten hoch um automatisch die guenstigsten Preise zu sehen.
                    </p>
                    <a
                      href="/dashboard/preislisten"
                      className="inline-block mt-2 px-4 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 transition-colors"
                    >
                      Preislisten hochladen
                    </a>
                  </div>
                )}

                {/* ═══ SUB-TAB: Materialkosten (Einkauf) ═══ */}
                {kalkSubTab === "material" && (
                  <>
                    <div className="px-3 md:px-6 py-3 bg-gray-50 border-b border-gray-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-2">
                      <span className="text-sm text-gray-500">
                        {kalkulation.positionen_gesamt} Positionen &mdash; {kalkulation.positionen_mit_preis} mit Preis
                        {recalculating && <span className="ml-2 text-primary-600 animate-pulse">Berechne...</span>}
                      </span>
                      <span className="text-lg font-bold">Einkauf: {eur(kalkulation.gesamt_netto)}</span>
                    </div>
                    <div className="overflow-x-auto -mx-0">
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
                        {(kalkulation.positionen ?? []).map((pos, i) => {
                          const editedMenge = mengenOverrides[pos.bezeichnung] ?? pos.menge;
                          const localGesamt = pos.einzelpreis != null ? editedMenge * pos.einzelpreis : null;
                          const isEdited = pos.bezeichnung in mengenOverrides;
                          return (
                            <tr key={i} className={`border-t border-gray-100 hover:bg-gray-50 ${isEdited ? "bg-yellow-50" : ""}`}>
                              <td className="px-4 py-3 font-medium">{pos.bezeichnung}</td>
                              <td className="px-4 py-3"><span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{pos.kategorie}</span></td>
                              <td className="px-4 py-2 text-right">
                                <input
                                  type="number"
                                  value={editedMenge}
                                  step={0.1}
                                  min={0}
                                  onChange={(e) => {
                                    const v = parseFloat(e.target.value);
                                    if (!isNaN(v) && v >= 0) updateMenge(pos.bezeichnung, v);
                                  }}
                                  className="w-20 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                                />
                              </td>
                              <td className="px-4 py-3">{pos.einheit}</td>
                              <td className="px-4 py-3 text-right">{pos.einzelpreis != null && pos.einzelpreis > 0 ? eur(pos.einzelpreis) : <span className="text-orange-500 font-medium">kein Preis</span>}</td>
                              <td className="px-4 py-3 text-right font-medium">{localGesamt != null && localGesamt > 0 ? eur(localGesamt) : <span className="text-orange-500">kein Preis</span>}</td>
                              <td className="px-4 py-3">{pos.anbieter ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">{pos.anbieter}</span> : <span className="text-xs text-gray-400">—</span>}</td>
                            </tr>
                          );
                        })}
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

                {/* ═══ SUB-TAB: Bestellliste ═══ */}
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

                {/* ═══ SUB-TAB: Kundenangebot (editable) ═══ */}
                {kalkSubTab === "angebot" && kalkParams && (
                  <div className="p-3 md:p-6 space-y-6">
                    {(kalkulation.kundenangebot?.material_einkauf ?? 0) === 0 && (
                      <div className="p-4 bg-orange-50 border border-orange-300 rounded-lg">
                        <p className="font-semibold text-orange-800">Material-Einkaufspreise fehlen</p>
                        <p className="text-sm text-orange-700 mt-1">
                          Bitte laden Sie zuerst{" "}
                          <a href="/dashboard/preislisten" className="underline font-medium hover:text-orange-900">Preislisten</a>{" "}
                          hoch, damit die Materialkalkulation korrekt berechnet werden kann.
                        </p>
                      </div>
                    )}
                    {recalculating && (
                      <div className="text-sm text-primary-600 animate-pulse">Kalkulation wird aktualisiert...</div>
                    )}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
                      {/* ── Linke Spalte: Editable Parameter ── */}
                      <div className="space-y-5">
                        <h4 className="font-semibold text-gray-900 text-lg">Parameter anpassen</h4>

                        {/* Material-Aufschlag */}
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Material-Aufschlag</label>
                          <EditNum
                            value={kalkParams.material_aufschlag_prozent}
                            onChange={(v) => updateParam("material_aufschlag_prozent", v)}
                            step={1}
                            min={0}
                            max={100}
                            suffix="%"
                          />
                        </div>

                        {/* Stundensatz eigene MA */}
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Stundensatz eigene MA</label>
                          <EditNum
                            value={kalkParams.stundensatz_eigen}
                            onChange={(v) => updateParam("stundensatz_eigen", v)}
                            step={0.5}
                            min={0}
                            suffix="EUR/h"
                          />
                        </div>

                        {/* Stundensatz Subunternehmer */}
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Stundensatz Subunternehmer</label>
                          <EditNum
                            value={kalkParams.stundensatz_sub}
                            onChange={(v) => updateParam("stundensatz_sub", v)}
                            step={0.5}
                            min={0}
                            suffix="EUR/h"
                          />
                        </div>

                        {/* Stunden/m2 Decke */}
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Stunden / m2 Decke</label>
                          <EditNum
                            value={kalkParams.stunden_pro_m2_decke}
                            onChange={(v) => updateParam("stunden_pro_m2_decke", v)}
                            step={0.1}
                            min={0}
                            suffix="h/m2"
                          />
                        </div>

                        {/* Stunden/m2 Wand */}
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Stunden / m2 Wand</label>
                          <EditNum
                            value={kalkParams.stunden_pro_m2_wand}
                            onChange={(v) => updateParam("stunden_pro_m2_wand", v)}
                            step={0.1}
                            min={0}
                            suffix="h/m2"
                          />
                        </div>

                        {/* Anteil Eigenleistung */}
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">
                            Anteil Eigenleistung: {Math.round(kalkParams.anteil_eigenleistung * 100)}%
                          </label>
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={kalkParams.anteil_eigenleistung}
                            onChange={(e) => updateParam("anteil_eigenleistung", parseFloat(e.target.value))}
                            className="w-full accent-primary-600"
                          />
                          <div className="flex justify-between text-xs text-gray-400 mt-1">
                            <span>0% (nur Sub)</span>
                            <span>100% (nur eigene MA)</span>
                          </div>
                        </div>

                        {/* Zusatzkosten */}
                        <div>
                          <label className="block text-xs text-gray-500 mb-2">Zusatzkosten</label>
                          {kalkParams.zusatzkosten.map((z, idx) => (
                            <div key={idx} className="flex gap-2 mb-2 items-center">
                              <input
                                type="text"
                                value={z.bezeichnung}
                                placeholder="Bezeichnung"
                                onChange={(e) => {
                                  const next = [...kalkParams.zusatzkosten];
                                  next[idx] = { ...next[idx], bezeichnung: e.target.value };
                                  updateParam("zusatzkosten", next);
                                }}
                                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-primary-500"
                              />
                              <input
                                type="number"
                                value={z.betrag}
                                step={100}
                                min={0}
                                onChange={(e) => {
                                  const next = [...kalkParams.zusatzkosten];
                                  next[idx] = { ...next[idx], betrag: parseFloat(e.target.value) || 0 };
                                  updateParam("zusatzkosten", next);
                                }}
                                className="w-24 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500"
                              />
                              <span className="text-xs text-gray-500">EUR</span>
                              <button
                                onClick={() => {
                                  const next = kalkParams.zusatzkosten.filter((_, j) => j !== idx);
                                  updateParam("zusatzkosten", next);
                                }}
                                className="text-red-500 hover:text-red-700 text-lg leading-none px-1"
                                title="Entfernen"
                              >&times;</button>
                            </div>
                          ))}
                          <button
                            onClick={() => {
                              updateParam("zusatzkosten", [
                                ...kalkParams.zusatzkosten,
                                { bezeichnung: "", betrag: 0 },
                              ]);
                            }}
                            className="text-sm text-primary-600 hover:text-primary-800 font-medium"
                          >
                            + Zusatzkosten hinzufuegen
                          </button>
                        </div>
                      </div>

                      {/* ── Mittlere Spalte: Angebotskalkulation ── */}
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

                      {/* ── Rechte Spalte: Kennzahlen ── */}
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
                            <p className="text-xs text-purple-600">Preis / m2 Decke</p>
                            <p className="text-lg md:text-2xl font-bold text-purple-900">
                              {(kalkulation.kundenangebot?.deckenflaeche_m2 ?? 0) > 0
                                ? fmt((kalkulation.kundenangebot?.angebot_netto ?? 0) / (kalkulation.kundenangebot?.deckenflaeche_m2 ?? 1), 2)
                                : "\u2014"} EUR
                            </p>
                          </div>
                          <div className="bg-orange-50 rounded-lg p-4">
                            <p className="text-xs text-orange-600">Eigenleistung</p>
                            <p className="text-lg md:text-2xl font-bold text-orange-900">{Math.round((kalkulation.kundenangebot?.anteil_eigenleistung ?? 0) * 100)}%</p>
                          </div>
                          {(kalkulation.kundenangebot?.zusatzkosten_summe ?? 0) > 0 && (
                            <div className="bg-orange-50 rounded-lg p-4">
                              <p className="text-xs text-orange-600">Zusatzkosten</p>
                              <p className="text-lg md:text-2xl font-bold text-orange-900">{eur(kalkulation.kundenangebot?.zusatzkosten_summe)}</p>
                            </div>
                          )}
                        </div>
                        <p className="text-xs text-gray-400 mt-4">
                          Alle Parameter links anpassen &mdash; die Kalkulation aktualisiert sich automatisch.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Raeume Tab (editable: flaeche_m2, hoehe_m) */}
        {currentTab === "raeume" && (
          <div className="overflow-x-auto">
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
              {raeume.map((r, i) => {
                const edits = editedRaeume[String(i)];
                const flaecheEdited = edits?.flaeche_m2 !== undefined;
                const hoeheEdited = edits?.hoehe_m !== undefined;
                const curFlaeche = edits?.flaeche_m2 ?? r.flaeche_m2;
                const curHoehe = edits?.hoehe_m ?? r.hoehe_m;
                return (
                  <tr key={i} id={r.raum_nr ? `raum-${r.raum_nr}` : undefined} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-6 py-3 font-medium">{r.bezeichnung}</td>
                    <td className="px-6 py-3 text-gray-500">{r.raum_nr ?? "—"}</td>
                    <td className="px-6 py-3 text-gray-500">{r.nutzung ?? "—"}</td>
                    <td className="px-6 py-3 text-gray-500 text-xs">{r.deckentyp ?? "—"}</td>
                    <td className={`px-6 py-2 text-right ${flaecheEdited ? "bg-yellow-50" : ""}`}>
                      <input
                        type="number"
                        value={curFlaeche ?? ""}
                        step={0.01}
                        min={0}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!isNaN(v) && v >= 0) {
                            setEditedRaeume((prev) => ({
                              ...prev,
                              [String(i)]: { ...prev[String(i)], flaeche_m2: v },
                            }));
                          }
                        }}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      />
                      <span className="ml-1 text-xs text-gray-400">m2</span>
                    </td>
                    <td className={`px-6 py-2 text-right ${hoeheEdited ? "bg-yellow-50" : ""}`}>
                      <input
                        type="number"
                        value={curHoehe ?? ""}
                        step={0.01}
                        min={0}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!isNaN(v) && v >= 0) {
                            setEditedRaeume((prev) => ({
                              ...prev,
                              [String(i)]: { ...prev[String(i)], hoehe_m: v },
                            }));
                          }
                        }}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      />
                      <span className="ml-1 text-xs text-gray-400">m</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}

        {/* Decken Tab (editable: flaeche_m2) */}
        {currentTab === "decken" && (
          <div className="overflow-x-auto">
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
              {decken.map((d, i) => {
                const edits = editedDecken[String(i)];
                const flaecheEdited = edits?.flaeche_m2 !== undefined;
                const curFlaeche = edits?.flaeche_m2 ?? d.flaeche_m2;
                return (
                  <tr key={i} className={`border-t border-gray-100 hover:bg-gray-50 ${d.entfaellt ? "opacity-50 line-through" : ""}`}>
                    <td className="px-6 py-3">{d.raum}</td>
                    <td className="px-6 py-3 font-medium">{d.typ}</td>
                    <td className="px-6 py-3">{d.system ?? "—"}</td>
                    <td className="px-6 py-3 text-xs text-gray-500">{d.beplankung ?? "—"}</td>
                    <td className={`px-6 py-2 text-right ${flaecheEdited ? "bg-yellow-50" : ""}`}>
                      <input
                        type="number"
                        value={curFlaeche ?? ""}
                        step={0.01}
                        min={0}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!isNaN(v) && v >= 0) {
                            setEditedDecken((prev) => ({
                              ...prev,
                              [String(i)]: { ...prev[String(i)], flaeche_m2: v },
                            }));
                          }
                        }}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      />
                      <span className="ml-1 text-xs text-gray-400">m2</span>
                    </td>
                    <td className="px-6 py-3 text-right">{d.abhaengehoehe_m ? `${fmt(d.abhaengehoehe_m)} m` : "—"}</td>
                    <td className="px-6 py-3 text-center">
                      {d.entfaellt ? (
                        <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">entfaellt</span>
                      ) : (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">aktiv</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}

        {/* Waende Tab (editable: laenge_m, hoehe_m) */}
        {currentTab === "waende" && (
          <div className="overflow-x-auto">
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
              {waende.map((w, i) => {
                const edits = editedWaende[String(i)];
                const laengeEdited = edits?.laenge_m !== undefined;
                const hoeheEdited = edits?.hoehe_m !== undefined;
                const curLaenge = edits?.laenge_m ?? w.laenge_m;
                const curHoehe = edits?.hoehe_m ?? w.hoehe_m;
                const computedFlaeche = (curLaenge ?? 0) * (curHoehe ?? 0);
                return (
                  <tr key={i} className={`border-t border-gray-100 hover:bg-gray-50 ${w.unsicher ? "bg-yellow-50" : ""}`}>
                    <td className="px-6 py-3 font-mono text-xs">{w.id}</td>
                    <td className="px-6 py-3 font-medium">{w.typ}</td>
                    <td className={`px-6 py-2 text-right ${laengeEdited ? "bg-yellow-50" : ""}`}>
                      <input
                        type="number"
                        value={curLaenge ?? ""}
                        step={0.01}
                        min={0}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!isNaN(v) && v >= 0) {
                            setEditedWaende((prev) => ({
                              ...prev,
                              [String(i)]: { ...prev[String(i)], laenge_m: v },
                            }));
                          }
                        }}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      />
                      <span className="ml-1 text-xs text-gray-400">m</span>
                    </td>
                    <td className={`px-6 py-2 text-right ${hoeheEdited ? "bg-yellow-50" : ""}`}>
                      <input
                        type="number"
                        value={curHoehe ?? ""}
                        step={0.01}
                        min={0}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!isNaN(v) && v >= 0) {
                            setEditedWaende((prev) => ({
                              ...prev,
                              [String(i)]: { ...prev[String(i)], hoehe_m: v },
                            }));
                          }
                        }}
                        className="w-20 px-2 py-1 border border-gray-300 rounded text-right font-mono text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      />
                      <span className="ml-1 text-xs text-gray-400">m</span>
                    </td>
                    <td className="px-6 py-3 text-right">
                      {fmt(w.flaeche_m2 ?? computedFlaeche)} m2
                    </td>
                    <td className="px-6 py-3 text-xs text-gray-500">
                      {w.unsicher && <span className="text-yellow-600 mr-1">[unsicher]</span>}
                      {w.notizen ?? ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}

        {/* Details Tab */}
        {currentTab === "details" && (
          <div className="overflow-x-auto">
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
              {details.map((d, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-6 py-3 font-mono">{d.detail_nr ?? "—"}</td>
                  <td className="px-6 py-3 font-medium">{d.bezeichnung}</td>
                  <td className="px-6 py-3">{d.massstab ?? "—"}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs max-w-md truncate">{d.beschreibung ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
