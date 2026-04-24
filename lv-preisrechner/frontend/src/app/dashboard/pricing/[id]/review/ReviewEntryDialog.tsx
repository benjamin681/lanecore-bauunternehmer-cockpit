"use client";

/**
 * Edit-Dialog fuer einen einzelnen Pricing-Entry (B+3.3).
 *
 * Felder: product_name, manufacturer, category, article_number, price_net,
 *         unit, effective_unit, price_per_effective_unit, needs_review,
 *         attributes (JSON-Textarea).
 * Spezial: Bundle-Preis-Helper wenn pieces_per_package + package_size gesetzt.
 */

import { useEffect, useMemo, useState } from "react";
import { Calculator, ExternalLink, Save } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { pricingApi } from "@/lib/pricingApi";
import type {
  SupplierPriceEntry,
  SupplierPriceEntryUpdate,
} from "@/lib/types/pricing";
import { REVIEW_REASON_LABELS } from "@/lib/types/pricing";

import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type FormState = {
  product_name: string;
  manufacturer: string;
  category: string;
  article_number: string;
  price_net: string;
  unit: string;
  effective_unit: string;
  price_per_effective_unit: string;
  needs_review: boolean;
  attributes_json: string;
};

function entryToForm(e: SupplierPriceEntry): FormState {
  return {
    product_name: e.product_name,
    manufacturer: e.manufacturer ?? "",
    category: e.category ?? "",
    article_number: e.article_number ?? "",
    price_net: String(e.price_net),
    unit: e.unit,
    effective_unit: e.effective_unit,
    price_per_effective_unit: String(e.price_per_effective_unit),
    needs_review: e.needs_review,
    attributes_json: JSON.stringify(e.attributes ?? {}, null, 2),
  };
}

function diffFormToPayload(
  initial: FormState,
  current: FormState,
  entry: SupplierPriceEntry,
): SupplierPriceEntryUpdate | null {
  const body: SupplierPriceEntryUpdate = {};

  const strOrNull = (v: string) => (v.trim() === "" ? null : v.trim());

  if (current.product_name.trim() !== initial.product_name.trim()) {
    body.product_name = current.product_name.trim();
  }
  if (strOrNull(current.manufacturer) !== strOrNull(initial.manufacturer)) {
    body.manufacturer = strOrNull(current.manufacturer);
  }
  if (strOrNull(current.category) !== strOrNull(initial.category)) {
    body.category = strOrNull(current.category);
  }
  if (strOrNull(current.article_number) !== strOrNull(initial.article_number)) {
    body.article_number = strOrNull(current.article_number);
  }

  const pNum = Number.parseFloat(current.price_net.replace(",", "."));
  if (Number.isFinite(pNum) && Math.abs(pNum - entry.price_net) > 1e-9) {
    body.price_net = pNum;
  }
  const ppeuNum = Number.parseFloat(
    current.price_per_effective_unit.replace(",", "."),
  );
  if (
    Number.isFinite(ppeuNum) &&
    Math.abs(ppeuNum - entry.price_per_effective_unit) > 1e-9
  ) {
    body.price_per_effective_unit = ppeuNum;
  }

  if (current.unit.trim() !== initial.unit.trim()) {
    body.unit = current.unit.trim();
  }
  if (current.effective_unit.trim() !== initial.effective_unit.trim()) {
    body.effective_unit = current.effective_unit.trim();
  }

  if (current.needs_review !== initial.needs_review) {
    body.needs_review = current.needs_review;
  }

  try {
    const parsedAttrs = JSON.parse(current.attributes_json);
    const initialAttrs = JSON.parse(initial.attributes_json);
    if (JSON.stringify(parsedAttrs) !== JSON.stringify(initialAttrs)) {
      body.attributes = parsedAttrs;
    }
  } catch {
    // JSON invalid — nicht mitschicken
  }

  return Object.keys(body).length === 0 ? null : body;
}

export type ReviewEntryDialogProps = {
  open: boolean;
  entry: SupplierPriceEntry | null;
  pricelistId: string;
  pdfSourceUrl?: string | null;
  onClose: () => void;
  onSaved: (updated: SupplierPriceEntry) => void;
};

export function ReviewEntryDialog({
  open,
  entry,
  pricelistId,
  pdfSourceUrl,
  onClose,
  onSaved,
}: ReviewEntryDialogProps) {
  const initial = useMemo(
    () => (entry ? entryToForm(entry) : null),
    [entry],
  );
  const [form, setForm] = useState<FormState | null>(initial);
  const [busy, setBusy] = useState(false);
  const [attrError, setAttrError] = useState<string | null>(null);

  // B+4.4 P4: Bundgroesse-Widget (nur aktiv wenn review_reason = bundgroesse_fehlt).
  const [bundleInput, setBundleInput] = useState<string>("");
  const [bundlePersist, setBundlePersist] = useState<boolean>(true);

  // Reset form whenever a new entry comes in
  useEffect(() => {
    setForm(initial);
    setAttrError(null);
    setBundleInput("");
    setBundlePersist(true);
  }, [initial]);

  // Rechnet Live-Preview des resultierenden EUR/lfm-Werts.
  const bundlePreview = useMemo(() => {
    if (!entry) return null;
    const pieces = Number.parseInt(bundleInput, 10);
    const size = entry.package_size;
    if (!Number.isFinite(pieces) || pieces <= 0) return null;
    if (!size || size <= 0) {
      return {
        pieces,
        size: null,
        totalPerBundle: null,
        pricePerUnit: null,
        warning:
          "Für diesen Eintrag fehlt package_size — der effektive Preis kann nicht berechnet werden.",
      };
    }
    const totalPerBundle = size * pieces;
    if (totalPerBundle <= 0) return null;
    return {
      pieces,
      size,
      totalPerBundle,
      pricePerUnit: entry.price_net / totalPerBundle,
      warning: null as string | null,
    };
  }, [entry, bundleInput]);

  async function submitBundleCorrection() {
    if (!entry) return;
    const pieces = Number.parseInt(bundleInput, 10);
    if (!Number.isFinite(pieces) || pieces <= 0) {
      toast.error("Bitte eine gültige Stückzahl eingeben.");
      return;
    }
    setBusy(true);
    try {
      const res = await pricingApi.correctEntry(entry.id, {
        correction_type: "pieces_per_package",
        corrected_value: { pieces_per_package: pieces },
        persist: bundlePersist,
      });
      toast.success(
        res.correction_persisted
          ? "Gespeichert + für künftige Uploads gemerkt."
          : "Gespeichert.",
      );
      onSaved(res.entry);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.detail ?? "Speichern fehlgeschlagen");
      } else {
        toast.error("Speichern fehlgeschlagen");
      }
    } finally {
      setBusy(false);
    }
  }

  function patch<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((s) => (s ? { ...s, [field]: value } : s));
  }

  function validateAttrs(): boolean {
    if (!form) return false;
    try {
      const parsed = JSON.parse(form.attributes_json);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setAttrError("Attributes muessen ein JSON-Objekt sein (nicht Array/Primitive).");
        return false;
      }
      setAttrError(null);
      return true;
    } catch (e) {
      setAttrError(`Ungueltiges JSON: ${(e as Error).message}`);
      return false;
    }
  }

  function applyBundleHelper() {
    if (!entry || !form) return;
    // Erwartung: price_net gilt pro Bundle/Gebinde. Effektive Einheit:
    //   package_unit (z.B. "m", "kg"), effektive Menge:
    //   pieces_per_package * package_size (Einheitslos kombiniert).
    const price = Number.parseFloat(form.price_net.replace(",", "."));
    const size = entry.package_size;
    const pieces = entry.pieces_per_package;
    if (!Number.isFinite(price) || !size || !pieces || size <= 0 || pieces <= 0) {
      toast.error(
        "Bundle-Helper benoetigt package_size und pieces_per_package im Entry.",
      );
      return;
    }
    const effective = price / (pieces * size);
    patch("price_per_effective_unit", effective.toFixed(4));
    if (entry.package_unit) patch("effective_unit", entry.package_unit);
    toast.success(
      `Berechnet: ${price} / (${pieces} × ${size}) = ${effective.toFixed(4)} €/${entry.package_unit ?? "Einheit"}`,
    );
  }

  async function handleSave() {
    if (!entry || !form || !initial) return;
    if (!validateAttrs()) return;
    const payload = diffFormToPayload(initial, form, entry);
    if (!payload) {
      toast.info("Keine Aenderungen.");
      onClose();
      return;
    }
    setBusy(true);
    try {
      const updated = await pricingApi.updateEntry(pricelistId, entry.id, payload);
      toast.success("Gespeichert.");
      onSaved(updated);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.detail ?? "Speichern fehlgeschlagen");
      } else {
        toast.error("Speichern fehlgeschlagen");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!entry || !form) {
    return null;
  }

  const canUseBundleHelper = !!(entry.package_size && entry.pieces_per_package);
  const pdfLink =
    pdfSourceUrl && entry.source_page
      ? `${pdfSourceUrl}#page=${entry.source_page}`
      : null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Eintrag bearbeiten"
      description={
        <span className="text-slate-600 text-sm">
          ID <code className="font-mono text-xs">{entry.id.slice(0, 8)}…</code>
          {entry.source_page ? ` · Seite ${entry.source_page}` : null}
          {" · "}Confidence {(entry.parser_confidence * 100).toFixed(0)} %
        </span>
      }
      size="xl"
      actions={[
        { label: "Abbrechen", variant: "ghost", autoClose: true },
        {
          label: (
            <span className="inline-flex items-center gap-1">
              <Save className="w-4 h-4" /> Speichern
            </span>
          ),
          variant: "primary",
          autoClose: false,
          disabled: busy,
          onClick: handleSave,
        },
      ]}
    >
      <div className="space-y-4">
        {pdfLink && (
          <a
            href={pdfLink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-bauplan-600 hover:underline"
          >
            <ExternalLink className="w-4 h-4" /> Seite {entry.source_page} im
            Original-PDF ansehen
          </a>
        )}

        {/* source_row_raw: Originale PDF-Zeile als Kontext */}
        {entry.source_row_raw && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
            <div className="text-xs text-slate-500 mb-1">Originale Zeile aus dem PDF</div>
            <div className="font-mono text-xs text-slate-800 whitespace-pre-wrap break-words">
              {entry.source_row_raw}
            </div>
          </div>
        )}

        {/* B+4.4 P4: Bundgroesse-Widget — nur wenn review_reason = bundgroesse_fehlt */}
        {(entry.attributes?.review_reason as string | undefined) ===
          "bundgroesse_fehlt" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-4 space-y-3">
            <div>
              <div className="text-sm font-semibold text-amber-900">
                Bundgröße nachtragen
              </div>
              <div className="text-xs text-amber-800/80 mt-0.5">
                {REVIEW_REASON_LABELS.bundgroesse_fehlt} — im PDF-Text ist die
                Stückzahl pro Bund nicht erkennbar. Trag sie ein, der effektive
                Preis wird daraus neu berechnet.
              </div>
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="bundle_pieces" className="text-amber-900">
                  Stück pro Bund
                </Label>
                <Input
                  id="bundle_pieces"
                  inputMode="numeric"
                  type="number"
                  min={1}
                  step={1}
                  value={bundleInput}
                  onChange={(e) => setBundleInput(e.target.value)}
                  className="w-32"
                />
              </div>

              {entry.package_size && (
                <div className="text-xs text-amber-900/80 pb-2.5">
                  × {entry.package_size}{" "}
                  {entry.package_unit ?? entry.effective_unit ?? "Einheit"} pro
                  Stück
                </div>
              )}
            </div>

            {bundlePreview && (
              <div className="text-sm text-amber-900 bg-white/60 rounded border border-amber-200 px-3 py-2">
                {bundlePreview.pricePerUnit !== null ? (
                  <>
                    <span className="font-mono">{bundlePreview.pieces}</span>{" "}
                    Stück ×{" "}
                    <span className="font-mono">{bundlePreview.size}</span>{" "}
                    {entry.package_unit ?? entry.effective_unit} ={" "}
                    <span className="font-mono">
                      {bundlePreview.totalPerBundle!.toFixed(2)}
                    </span>{" "}
                    {entry.effective_unit} pro Bund
                    <div className="mt-1">
                      →{" "}
                      <span className="font-mono font-semibold">
                        {bundlePreview.pricePerUnit.toFixed(4)}
                      </span>{" "}
                      €/{entry.effective_unit}{" "}
                      <span className="text-xs text-amber-900/60">
                        (aus {entry.price_net.toFixed(2)} € Bundpreis)
                      </span>
                    </div>
                  </>
                ) : (
                  <span className="text-amber-900/80">
                    {bundlePreview.warning}
                  </span>
                )}
              </div>
            )}

            <label className="flex items-center gap-2 text-xs text-amber-900 cursor-pointer">
              <input
                type="checkbox"
                checked={bundlePersist}
                onChange={(e) => setBundlePersist(e.target.checked)}
                className="w-4 h-4"
              />
              Für künftige Uploads derselben Preisliste merken
            </label>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={submitBundleCorrection}
                disabled={busy || bundleInput.trim() === ""}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-4 h-4" /> Bundgröße anwenden
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="product_name">Produktname</Label>
            <Input
              id="product_name"
              value={form.product_name}
              onChange={(e) => patch("product_name", e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="manufacturer">Hersteller</Label>
            <Input
              id="manufacturer"
              value={form.manufacturer}
              onChange={(e) => patch("manufacturer", e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="article_number">Artikel-Nr.</Label>
            <Input
              id="article_number"
              value={form.article_number}
              onChange={(e) => patch("article_number", e.target.value)}
            />
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="category">Kategorie</Label>
            <Input
              id="category"
              value={form.category}
              onChange={(e) => patch("category", e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="price_net">Preis (netto)</Label>
            <Input
              id="price_net"
              inputMode="decimal"
              value={form.price_net}
              onChange={(e) => patch("price_net", e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="unit">Original-Einheit</Label>
            <Input
              id="unit"
              value={form.unit}
              onChange={(e) => patch("unit", e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="effective_unit">Effektive Einheit</Label>
            <Input
              id="effective_unit"
              value={form.effective_unit}
              onChange={(e) => patch("effective_unit", e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="price_per_effective_unit">
              Preis pro effektiver Einheit
            </Label>
            <div className="flex gap-2">
              <Input
                id="price_per_effective_unit"
                inputMode="decimal"
                value={form.price_per_effective_unit}
                onChange={(e) =>
                  patch("price_per_effective_unit", e.target.value)
                }
              />
              <button
                type="button"
                onClick={applyBundleHelper}
                disabled={!canUseBundleHelper}
                title={
                  canUseBundleHelper
                    ? `Berechnung: Preis / (pieces_per_package × package_size) — ${entry.pieces_per_package} × ${entry.package_size}`
                    : "Bundle-Helper benoetigt package_size und pieces_per_package"
                }
                className="shrink-0 h-10 w-10 grid place-items-center rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Calculator className="w-4 h-4" />
              </button>
            </div>
            {canUseBundleHelper && (
              <p className="text-xs text-slate-500">
                Bundle: {entry.pieces_per_package} × {entry.package_size}{" "}
                {entry.package_unit ?? ""} pro Paket
              </p>
            )}
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer pt-2 border-t border-slate-100">
          <input
            type="checkbox"
            checked={form.needs_review}
            onChange={(e) => patch("needs_review", e.target.checked)}
            className="w-4 h-4"
          />
          Dieser Eintrag braucht noch Review
          <span className="text-xs text-slate-500">
            (Uncheck = reviewed → Counter steigt)
          </span>
        </label>

        <div className="space-y-1.5">
          <Label htmlFor="attributes_json">Attributes (JSON)</Label>
          <textarea
            id="attributes_json"
            value={form.attributes_json}
            onChange={(e) => patch("attributes_json", e.target.value)}
            onBlur={validateAttrs}
            rows={5}
            className="w-full font-mono text-xs rounded-lg bg-white border border-slate-200 p-3 focus:outline-none focus:border-bauplan-500 focus:ring-2 focus:ring-bauplan-100"
          />
          {attrError && (
            <p className="text-xs text-danger-600">{attrError}</p>
          )}
        </div>
      </div>
    </Dialog>
  );
}

export default ReviewEntryDialog;
