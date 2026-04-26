"use client";

/**
 * B+4.11 — Offers-Karte fuer LV-Detail-Seite.
 *
 * Listet alle Offers eines LVs, erlaubt Anlage neuer Offers,
 * Status-Wechsel und PDF-Download.
 */
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Check,
  Download,
  FilePlus2,
  HandshakeIcon,
  Loader2,
  Ruler,
  Send,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { OfferStatusBadge } from "@/components/OfferStatusBadge";
import {
  Offer,
  OfferDetail,
  OFFER_PDF_FORMAT_LABELS,
  OfferPdfFormat,
  OfferStatus,
  aufmassApi,
  offersApi,
} from "@/lib/tenantApi";
import { fmtDate, fmtEur } from "@/lib/format";

type Props = {
  lvId: string;
};

export function OffersCard({ lvId }: Props) {
  const router = useRouter();
  const [offers, setOffers] = useState<Offer[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // Create-Form
  const [createOpen, setCreateOpen] = useState(false);
  const [pdfFormat, setPdfFormat] = useState<OfferPdfFormat>("eigenes_layout");
  const [createNotes, setCreateNotes] = useState("");

  // Status-Action-Modal
  const [actionOffer, setActionOffer] = useState<Offer | null>(null);
  const [actionStatus, setActionStatus] = useState<OfferStatus | null>(null);
  const [actionReason, setActionReason] = useState("");
  const [actionDate, setActionDate] = useState<string>("");

  async function load() {
    setLoading(true);
    try {
      const data = await offersApi.listForLv(lvId);
      setOffers(data);
    } catch (e: any) {
      toast.error(e?.detail || "Offers konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lvId]);

  async function createOffer() {
    setBusy(true);
    try {
      await offersApi.createForLv(lvId, {
        pdf_format: pdfFormat,
        internal_notes: createNotes.trim() || undefined,
      });
      toast.success("Angebot erstellt");
      setCreateOpen(false);
      setCreateNotes("");
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Anlage fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  function openStatusAction(offer: Offer, status: OfferStatus) {
    setActionOffer(offer);
    setActionStatus(status);
    setActionReason("");
    setActionDate(new Date().toISOString().slice(0, 10));
  }

  async function applyStatusAction() {
    if (!actionOffer || !actionStatus) return;
    setBusy(true);
    try {
      await offersApi.updateStatus(actionOffer.id, {
        status: actionStatus,
        reason: actionReason.trim() || undefined,
        on_date: actionDate || undefined,
      });
      toast.success("Status aktualisiert");
      setActionOffer(null);
      setActionStatus(null);
      await load();
    } catch (e: any) {
      toast.error(e?.detail || "Status-Wechsel fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function startAufmass(offer: Offer) {
    if (offer.status !== "accepted") return;
    setBusy(true);
    try {
      const aufmass = await aufmassApi.createFromOffer(offer.id, {});
      toast.success(`Aufmaß ${aufmass.aufmass_number} angelegt`);
      router.push(`/dashboard/aufmasse/${aufmass.id}`);
    } catch (e: any) {
      toast.error(e?.detail || "Aufmaß konnte nicht angelegt werden");
      setBusy(false);
    }
  }

  async function downloadPdf(offer: Offer) {
    try {
      const res = await fetch(offersApi.pdfUrl(offer.id), {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("lvp_token") ?? ""}`,
        },
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${offer.offer_number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast.error("PDF-Download fehlgeschlagen");
    }
  }

  return (
    <section className="rounded-xl bg-white border border-slate-200 p-5">
      <header className="flex items-center justify-between gap-4 flex-wrap mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Angebote</h2>
        {offers && offers.length > 0 && (
          <Button
            size="sm"
            onClick={() => setCreateOpen((v) => !v)}
            disabled={busy}
          >
            <FilePlus2 className="w-4 h-4" /> Neues Angebot
          </Button>
        )}
      </header>

      {loading ? (
        <div className="text-slate-500 py-8 text-center">Lade…</div>
      ) : !offers || offers.length === 0 ? (
        <EmptyOrCreate
          createOpen={createOpen}
          setCreateOpen={setCreateOpen}
          pdfFormat={pdfFormat}
          setPdfFormat={setPdfFormat}
          createNotes={createNotes}
          setCreateNotes={setCreateNotes}
          onCreate={createOffer}
          busy={busy}
        />
      ) : (
        <>
          {createOpen && (
            <CreateForm
              pdfFormat={pdfFormat}
              setPdfFormat={setPdfFormat}
              createNotes={createNotes}
              setCreateNotes={setCreateNotes}
              onCreate={createOffer}
              onCancel={() => setCreateOpen(false)}
              busy={busy}
            />
          )}
          <ul className="space-y-3">
            {offers.map((o) => (
              <OfferRow
                key={o.id}
                offer={o}
                onAction={openStatusAction}
                onDownload={() => downloadPdf(o)}
                onStartAufmass={startAufmass}
                busy={busy}
              />
            ))}
          </ul>
        </>
      )}

      {actionOffer && actionStatus && (
        <ActionModal
          offer={actionOffer}
          status={actionStatus}
          reason={actionReason}
          setReason={setActionReason}
          actionDate={actionDate}
          setActionDate={setActionDate}
          onCancel={() => {
            setActionOffer(null);
            setActionStatus(null);
          }}
          onConfirm={applyStatusAction}
          busy={busy}
        />
      )}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Sub-Components
// --------------------------------------------------------------------------- //
function EmptyOrCreate({
  createOpen,
  setCreateOpen,
  pdfFormat,
  setPdfFormat,
  createNotes,
  setCreateNotes,
  onCreate,
  busy,
}: {
  createOpen: boolean;
  setCreateOpen: (v: boolean) => void;
  pdfFormat: OfferPdfFormat;
  setPdfFormat: (v: OfferPdfFormat) => void;
  createNotes: string;
  setCreateNotes: (v: string) => void;
  onCreate: () => void;
  busy: boolean;
}) {
  if (!createOpen) {
    return (
      <div className="text-center py-6">
        <p className="text-sm text-slate-600">
          Noch kein Angebot erstellt.
        </p>
        <p className="text-xs text-slate-500 mt-1 mb-4">
          Erzeugen Sie aus diesem LV ein verbindliches Angebot mit Snapshot
          der aktuellen Summe.
        </p>
        <Button onClick={() => setCreateOpen(true)} disabled={busy}>
          <FilePlus2 className="w-4 h-4" /> Angebot erstellen
        </Button>
      </div>
    );
  }
  return (
    <CreateForm
      pdfFormat={pdfFormat}
      setPdfFormat={setPdfFormat}
      createNotes={createNotes}
      setCreateNotes={setCreateNotes}
      onCreate={onCreate}
      onCancel={() => setCreateOpen(false)}
      busy={busy}
    />
  );
}

function CreateForm({
  pdfFormat,
  setPdfFormat,
  createNotes,
  setCreateNotes,
  onCreate,
  onCancel,
  busy,
}: {
  pdfFormat: OfferPdfFormat;
  setPdfFormat: (v: OfferPdfFormat) => void;
  createNotes: string;
  setCreateNotes: (v: string) => void;
  onCreate: () => void;
  onCancel: () => void;
  busy: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-3 mb-4">
      <div>
        <div className="text-sm font-medium text-slate-900 mb-2">
          PDF-Format
        </div>
        <div className="space-y-2">
          {(Object.keys(OFFER_PDF_FORMAT_LABELS) as OfferPdfFormat[]).map(
            (k) => (
              <label key={k} className="flex items-start gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="pdf_format"
                  value={k}
                  checked={pdfFormat === k}
                  onChange={() => setPdfFormat(k)}
                  className="mt-1"
                />
                <span className="text-sm text-slate-700">
                  {OFFER_PDF_FORMAT_LABELS[k]}
                  {k === "original_lv_filled" && (
                    <span className="block text-xs text-slate-500">
                      Erfordert ein hochgeladenes Original-PDF.
                    </span>
                  )}
                </span>
              </label>
            ),
          )}
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-slate-900 mb-1">
          Interne Notiz (optional)
        </label>
        <textarea
          value={createNotes}
          onChange={(e) => setCreateNotes(e.target.value)}
          rows={2}
          maxLength={2000}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bauplan-500"
          placeholder="z. B. Kontaktperson, besondere Konditionen…"
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
          Abbrechen
        </Button>
        <Button size="sm" onClick={onCreate} disabled={busy}>
          {busy && <Loader2 className="w-4 h-4 animate-spin" />}
          Angebot erstellen
        </Button>
      </div>
    </div>
  );
}

function OfferRow({
  offer,
  onAction,
  onDownload,
  onStartAufmass,
  busy,
}: {
  offer: Offer;
  onAction: (offer: Offer, status: OfferStatus) => void;
  onDownload: () => void;
  onStartAufmass: (offer: Offer) => void;
  busy: boolean;
}) {
  const expired = useMemo(
    () =>
      offer.status === "sent" &&
      offer.valid_until &&
      new Date(offer.valid_until).getTime() < Date.now(),
    [offer.status, offer.valid_until],
  );
  const expiringSoon = useMemo(() => {
    if (offer.status !== "sent" || !offer.valid_until) return false;
    const days =
      (new Date(offer.valid_until).getTime() - Date.now()) /
      (1000 * 60 * 60 * 24);
    return days >= 0 && days <= 7;
  }, [offer.status, offer.valid_until]);

  return (
    <li className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-semibold text-slate-900">
              {offer.offer_number}
            </span>
            <OfferStatusBadge status={offer.status} />
            {expired && (
              <span className="text-xs px-2 py-0.5 rounded bg-danger-500/10 text-danger-600 border border-danger-500/20">
                Frist abgelaufen
              </span>
            )}
            {!expired && expiringSoon && (
              <span className="text-xs px-2 py-0.5 rounded bg-warning-500/10 text-warning-600 border border-warning-500/20">
                Frist läuft ab
              </span>
            )}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Erstellt: {fmtDate(offer.created_at)}
            {offer.sent_date && ` · Versendet: ${fmtDate(offer.sent_date)}`}
            {offer.valid_until &&
              ` · Gültig bis: ${fmtDate(offer.valid_until)}`}
            {offer.accepted_date &&
              ` · Angenommen: ${fmtDate(offer.accepted_date)}`}
            {offer.rejected_date &&
              ` · Abgelehnt: ${fmtDate(offer.rejected_date)}`}
          </div>
          {offer.internal_notes && (
            <div className="text-xs text-slate-600 mt-2 italic">
              {offer.internal_notes}
            </div>
          )}
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm text-slate-500">Netto</div>
          <div className="font-semibold text-slate-900">
            {fmtEur(offer.betrag_netto)}
          </div>
          <div className="text-xs text-slate-500">
            Brutto {fmtEur(offer.betrag_brutto)} · {offer.position_count} Pos.
          </div>
        </div>
      </div>

      {offer.status === "accepted" && (
        <div className="mt-3 rounded-md bg-success-500/10 border border-success-500/20 px-3 py-2 text-sm text-success-700 flex items-center justify-between gap-3 flex-wrap">
          <span>✓ Angenommen — Aufmaß und Final-Kalkulation starten.</span>
          <button
            type="button"
            onClick={() => onStartAufmass(offer)}
            disabled={busy}
            className="inline-flex items-center gap-1 px-3 py-1 rounded bg-success-500 text-white text-sm font-medium hover:bg-success-600 disabled:opacity-60"
          >
            <Ruler className="w-4 h-4" /> Aufmaß starten
          </button>
        </div>
      )}

      <div className="flex items-center gap-2 mt-3 flex-wrap">
        <Button size="sm" variant="ghost" onClick={onDownload}>
          <Download className="w-4 h-4" /> PDF
        </Button>

        {offer.status === "draft" && (
          <>
            <Button
              size="sm"
              variant="primary"
              onClick={() => onAction(offer, "sent")}
              disabled={busy}
            >
              <Send className="w-4 h-4" /> Als versendet markieren
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onAction(offer, "rejected")}
              disabled={busy}
            >
              <X className="w-4 h-4" /> Verworfen
            </Button>
          </>
        )}

        {offer.status === "sent" && (
          <>
            <Button
              size="sm"
              variant="primary"
              onClick={() => onAction(offer, "accepted")}
              disabled={busy}
            >
              <Check className="w-4 h-4" /> Als angenommen
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onAction(offer, "rejected")}
              disabled={busy}
            >
              <X className="w-4 h-4" /> Als abgelehnt
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onAction(offer, "negotiating")}
              disabled={busy}
            >
              <HandshakeIcon className="w-4 h-4" /> In Verhandlung
            </Button>
          </>
        )}

        {offer.status === "negotiating" && (
          <>
            <Button
              size="sm"
              variant="primary"
              onClick={() => onAction(offer, "accepted")}
              disabled={busy}
            >
              <Check className="w-4 h-4" /> Als angenommen
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onAction(offer, "rejected")}
              disabled={busy}
            >
              <X className="w-4 h-4" /> Als abgelehnt
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onAction(offer, "sent")}
              disabled={busy}
            >
              Erneut versendet
            </Button>
          </>
        )}
      </div>
    </li>
  );
}

function ActionModal({
  offer,
  status,
  reason,
  setReason,
  actionDate,
  setActionDate,
  onCancel,
  onConfirm,
  busy,
}: {
  offer: Offer;
  status: OfferStatus;
  reason: string;
  setReason: (v: string) => void;
  actionDate: string;
  setActionDate: (v: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
}) {
  const labels: Record<OfferStatus, string> = {
    draft: "Entwurf",
    sent: "Versendet",
    accepted: "Angenommen",
    rejected: "Abgelehnt",
    negotiating: "In Verhandlung",
    expired: "Abgelaufen",
  };
  const showDate =
    status === "sent" || status === "accepted" || status === "rejected";
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-lg font-semibold text-slate-900">
          Status auf „{labels[status]}“ setzen
        </h3>
        <p className="text-sm text-slate-600 mt-1">
          Angebot {offer.offer_number}
        </p>
        <div className="mt-4 space-y-3">
          {showDate && (
            <div>
              <label className="block text-sm font-medium text-slate-900 mb-1">
                Datum
              </label>
              <input
                type="date"
                value={actionDate}
                onChange={(e) => setActionDate(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-slate-900 mb-1">
              Notiz (optional)
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={2000}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-bauplan-500"
              placeholder={
                status === "sent"
                  ? "z. B. per Mail an bauleitung@example.com"
                  : status === "rejected"
                    ? "z. B. zu hoher Preis, anderer Bieter"
                    : status === "negotiating"
                      ? "z. B. Preis-Anpassung verhandeln"
                      : ""
              }
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            Abbrechen
          </Button>
          <Button variant="primary" onClick={onConfirm} disabled={busy}>
            {busy && <Loader2 className="w-4 h-4 animate-spin" />}
            Bestätigen
          </Button>
        </div>
      </div>
    </div>
  );
}
