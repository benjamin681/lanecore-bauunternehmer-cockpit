"use client";

/**
 * Detailseite einer SupplierPriceList (B+3.2).
 *
 * Zeigt Stammdaten + Status + Kennzahlen. Bei PENDING_PARSE/PARSING
 * wird alle 5 Sekunden gepollt bis der Parser durch ist.
 *
 * Der Review-Button verweist auf /dashboard/pricing/[id]/review —
 * diese Route wird erst in B+3.3 gebaut, darum hier nur als Link
 * mit "Beta"-Hinweis.
 */

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Archive,
  CheckCircle,
  Loader2,
  RefreshCw,
  ClipboardCheck,
} from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { pricingApi } from "@/lib/pricingApi";
import { fmtDate } from "@/lib/format";
import {
  PRICING_STATUS_META,
  type SupplierPriceList,
} from "@/lib/types/pricing";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";

const POLL_INTERVAL_MS = 5000;

export default function PricingDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [pl, setPl] = useState<SupplierPriceList | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await pricingApi.getPricelist(id);
      setPl(data);
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Laden fehlgeschlagen";
      toast.error(msg || "Nicht gefunden");
      router.replace("/dashboard/pricing");
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-Poll waehrend Parse laeuft
  useEffect(() => {
    if (!pl) return;
    const inProgress = pl.status === "PENDING_PARSE" || pl.status === "PARSING";
    if (!inProgress) {
      if (pollTimer.current) clearInterval(pollTimer.current);
      pollTimer.current = null;
      return;
    }
    if (pollTimer.current) return;
    pollTimer.current = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      if (pollTimer.current) {
        clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [pl, load]);

  // Elapsed-Timer fuer Parse-Hinweis-Card.
  // Hinweis: Die Startzeit ist der Zeitpunkt, zu dem der User die Page
  // sieht und den Status zum ersten Mal als "in Progress" wahrnimmt —
  // nicht die echte Upload-Zeit (die liegt im Backend, wird aber nicht
  // serverseitig als started_at auf der Pricelist gefuehrt). Wenn ein
  // User mitten im Parse zurueckkommt, zeigt der Timer also "seit Mount"
  // statt "seit Upload". Das ist okay, weil die Grenze "1–3 Minuten"
  // ohnehin nur ein grober Richtwert ist.
  const [elapsedSec, setElapsedSec] = useState(0);
  const inProgressForTimer =
    pl?.status === "PENDING_PARSE" || pl?.status === "PARSING";
  useEffect(() => {
    if (!inProgressForTimer) {
      setElapsedSec(0);
      return;
    }
    const startedAt = Date.now();
    const tick = () =>
      setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const handle = setInterval(tick, 1000);
    return () => clearInterval(handle);
  }, [inProgressForTimer]);

  async function doActivate() {
    if (!pl) return;
    setBusy(true);
    try {
      const updated = await pricingApi.activatePricelist(pl.id);
      setPl(updated);
      toast.success("Aktiviert. Andere Listen dieses Lieferanten wurden deaktiviert.");
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Aktivierung fehlgeschlagen";
      toast.error(msg ?? "Aktivierung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function doArchive() {
    if (!pl) return;
    if (!confirm(`Preisliste "${pl.list_name}" archivieren?`)) return;
    setBusy(true);
    try {
      const updated = await pricingApi.deletePricelist(pl.id);
      setPl(updated);
      toast.success("Archiviert.");
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Archivierung fehlgeschlagen";
      toast.error(msg ?? "Archivierung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function doRetryParse() {
    if (!pl) return;
    setBusy(true);
    try {
      const updated = await pricingApi.parsePricelist(pl.id);
      setPl(updated);
      toast.success("Parse neu gestartet.");
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Parse-Retry fehlgeschlagen";
      toast.error(msg ?? "Parse-Retry fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  const meta = useMemo(() => (pl ? PRICING_STATUS_META[pl.status] : null), [pl]);

  if (loading || !pl || !meta) {
    return <div className="py-20 text-center text-slate-500">Lade …</div>;
  }

  const inProgress = pl.status === "PENDING_PARSE" || pl.status === "PARSING";
  const canActivate = pl.status === "APPROVED" && !pl.is_active;
  const canArchive = pl.status !== "ARCHIVED";
  const canReview =
    pl.status === "PARSED" ||
    pl.status === "REVIEWED" ||
    pl.status === "PARTIAL_PARSE";
  const hasError = pl.status === "ERROR";

  const total = pl.entries_total ?? 0;
  const reviewed = pl.entries_reviewed ?? 0;
  const reviewPct = total > 0 ? Math.round((reviewed / total) * 100) : 0;

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/pricing"
        className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" /> Zurueck zur Uebersicht
      </Link>

      {/* Header */}
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-3xl font-bold text-slate-900">
              {pl.supplier_name}
              {pl.supplier_location && (
                <span className="text-slate-500 font-normal"> — {pl.supplier_location}</span>
              )}
            </h1>
            <Badge variant={meta.badge}>
              {inProgress && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
              {meta.label}
            </Badge>
            {pl.is_active && (
              <Badge variant="success">
                <CheckCircle className="w-3 h-3 mr-1" /> aktiv
              </Badge>
            )}
          </div>
          <p className="text-slate-600 mt-1">
            <span className="font-medium">{pl.list_name}</span> · Gueltig{" "}
            {fmtDate(pl.valid_from)}
            {pl.valid_until ? ` – ${fmtDate(pl.valid_until)}` : " – offen"}
          </p>
        </div>

        <div className="flex gap-2 flex-wrap">
          {canActivate && (
            <Button onClick={doActivate} disabled={busy} variant="success">
              <CheckCircle className="w-4 h-4" /> Aktivieren
            </Button>
          )}
          {canArchive && (
            <Button onClick={doArchive} disabled={busy} variant="ghost">
              <Archive className="w-4 h-4" /> Archivieren
            </Button>
          )}
        </div>
      </header>

      {/* Progress-Hinweis — waehrend Parse laeuft */}
      {inProgress && (
        <Card className="border-bauplan-200 bg-bauplan-50/40 transition-opacity duration-500">
          <CardBody className="flex items-start gap-3">
            <Loader2 className="w-5 h-5 text-bauplan-600 shrink-0 mt-0.5 animate-spin" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="font-medium text-slate-900">
                  Preisliste wird analysiert
                </div>
                <div
                  className="text-sm font-mono tabular-nums text-slate-500"
                  aria-label="Verstrichene Zeit seit Seitenaufruf"
                >
                  {fmtElapsed(elapsedSec)}
                </div>
              </div>
              <div className="text-sm text-slate-600 mt-1">
                Unsere KI liest gerade die Preisliste und extrahiert alle
                Positionen. Das dauert typischerweise 1–3 Minuten. Du kannst
                den Tab offen lassen oder spaeter zurueck kommen — der Parser
                laeuft im Hintergrund weiter.
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* B+4.6 — PARTIAL_PARSE: gelbe Warnung + Liste der fehlgeschlagenen Seiten */}
      {pl.status === "PARTIAL_PARSE" && (
        <Card className="border-amber-200 bg-amber-500/5">
          <CardBody className="space-y-3">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-900">
                  Details unvollständiger Parse
                </div>
                {pl.parse_error && (
                  <div className="text-sm text-slate-700 mt-1">
                    {pl.parse_error}
                  </div>
                )}
                {pl.parse_error_details && pl.parse_error_details.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {pl.parse_error_details.map((d, i) => (
                      <div
                        key={`${d.batch_idx}-${i}`}
                        className="rounded-md bg-white border border-amber-200 p-2.5 text-sm"
                      >
                        <div className="font-medium text-slate-900">
                          Batch {d.batch_idx} · Seiten {d.page_range}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          {d.attempts} Versuch{d.attempts === 1 ? "" : "e"} ·{" "}
                          {d.error_class}
                        </div>
                        <div className="text-xs text-slate-600 mt-1 font-mono break-words">
                          {d.error_message}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="text-xs text-slate-500 mt-2">
                  Die verbleibenden Seiten wurden normal verarbeitet. Für einen
                  vollständigen Parse bitte die Datei erneut hochladen.
                </div>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Fehler-Fall */}
      {hasError && (
        <Card className="border-danger-200 bg-danger-500/5">
          <CardBody className="space-y-3">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-danger-500 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-900">Parse fehlgeschlagen</div>
                {pl.parse_error ? (
                  <pre className="mt-2 text-sm text-slate-700 whitespace-pre-wrap break-words bg-white rounded p-3 border border-slate-200 max-h-48 overflow-auto">
                    {pl.parse_error}
                  </pre>
                ) : (
                  <div className="text-sm text-slate-600 mt-1">
                    Keine Details verfuegbar.
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button onClick={doRetryParse} disabled={busy} variant="primary">
                <RefreshCw className="w-4 h-4" /> Parse neu starten
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Kennzahlen — waehrend Parse laeuft: Skeletons statt "0", damit der
          User nicht denkt "da sind gar keine Eintraege drin". */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardBody>
            <div className="text-sm text-slate-500">Eintraege</div>
            {inProgress ? (
              <div className="h-8 mt-1 w-20 rounded bg-slate-100 animate-pulse" />
            ) : (
              <div className="text-2xl font-bold text-slate-900 mt-1 tabular-nums">
                {total.toLocaleString("de-DE")}
              </div>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <div className="text-sm text-slate-500">Reviewed</div>
            {inProgress ? (
              <div className="h-8 mt-1 w-32 rounded bg-slate-100 animate-pulse" />
            ) : (
              <div className="text-2xl font-bold text-slate-900 mt-1 tabular-nums">
                {reviewed.toLocaleString("de-DE")}
                <span className="text-base font-normal text-slate-500 ml-2">
                  / {total.toLocaleString("de-DE")} ({reviewPct} %)
                </span>
              </div>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <div className="text-sm text-slate-500">Offen (noch zu pruefen)</div>
            {inProgress ? (
              <div className="h-8 mt-1 w-20 rounded bg-slate-100 animate-pulse" />
            ) : (
              <div className="text-2xl font-bold text-slate-900 mt-1 tabular-nums">
                {Math.max(0, total - reviewed).toLocaleString("de-DE")}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Review-Aktion */}
      {canReview && (
        <Card>
          <CardHeader>
            <CardTitle>Review</CardTitle>
          </CardHeader>
          <CardBody className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="text-slate-700">
                Pruefe die Eintraege mit niedriger Confidence und bestaetige oder
                korrigiere sie.
              </div>
              <div className="text-sm text-slate-500 mt-1">
                Filter, sortieren, bearbeiten — die Korrekturen werden sofort
                gespeichert.
              </div>
            </div>
            <Link href={`/dashboard/pricing/${pl.id}/review`}>
              <Button variant="primary">
                <ClipboardCheck className="w-4 h-4" /> Review starten
              </Button>
            </Link>
          </CardBody>
        </Card>
      )}

      {/* Rohdaten */}
      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardBody>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <dt className="text-slate-500">Pricelist-ID</dt>
              <dd className="text-slate-900 font-mono text-xs break-all">{pl.id}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Datei-Hash (SHA-256)</dt>
              <dd className="text-slate-900 font-mono text-xs break-all">
                {pl.source_file_hash.slice(0, 16)}…{pl.source_file_hash.slice(-8)}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Hochgeladen</dt>
              <dd className="text-slate-900">{fmtDate(pl.uploaded_at)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Freigegeben</dt>
              <dd className="text-slate-900">
                {pl.approved_at ? fmtDate(pl.approved_at) : "—"}
              </dd>
            </div>
          </dl>
        </CardBody>
      </Card>
    </div>
  );
}

/** Sekunden → "mm:ss" (zeigt Minuten ohne fuehrende Null, Sekunden immer
 *  zweistellig). Nur fuer Parse-Progress-Anzeige; keine i18n noetig. */
function fmtElapsed(totalSec: number): string {
  const mm = Math.floor(totalSec / 60);
  const ss = totalSec % 60;
  return `${mm}:${ss.toString().padStart(2, "0")}`;
}
