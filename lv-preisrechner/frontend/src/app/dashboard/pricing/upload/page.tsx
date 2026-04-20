"use client";

/**
 * Upload-Seite fuer neue Lieferanten-Preislisten (B+3.2).
 *
 * Backend-Endpoint: POST /api/v1/pricing/upload  (Multipart)
 * Erlaubt: .pdf, .xlsx, .xls, .csv, max 50 MB.
 */

import { useRouter } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, Upload } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { pricingApi } from "@/lib/pricingApi";
import { cn } from "@/lib/cn";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const MAX_MB = 50;
const ALLOWED_EXT = [".pdf", ".xlsx", ".xls", ".csv"];

function hasAllowedExtension(name: string): boolean {
  return ALLOWED_EXT.some((ext) => name.toLowerCase().endsWith(ext));
}

type FormState = {
  supplier_name: string;
  supplier_location: string;
  list_name: string;
  valid_from: string;
  valid_until: string;
  auto_parse: boolean;
};

const INITIAL: FormState = {
  supplier_name: "",
  supplier_location: "",
  list_name: "",
  valid_from: new Date().toISOString().slice(0, 10), // heute
  valid_until: "",
  auto_parse: true,
};

export default function PricingUploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL);
  const [isOver, setIsOver] = useState(false);
  const [busy, setBusy] = useState(false);

  const setFileSafe = useCallback((f: File | null) => {
    if (!f) {
      setFile(null);
      return;
    }
    if (!hasAllowedExtension(f.name)) {
      toast.error(`Dateiformat nicht unterstuetzt. Erlaubt: ${ALLOWED_EXT.join(", ")}`);
      return;
    }
    const mb = f.size / (1024 * 1024);
    if (mb > MAX_MB) {
      toast.error(`Datei ${mb.toFixed(1)} MB > ${MAX_MB} MB`);
      return;
    }
    setFile(f);
  }, []);

  function patch(field: keyof FormState, value: string | boolean) {
    setForm((s) => ({ ...s, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      toast.error("Bitte eine Datei auswaehlen.");
      return;
    }
    if (!form.supplier_name.trim()) {
      toast.error("Lieferant-Name ist Pflicht.");
      return;
    }
    if (!form.list_name.trim()) {
      toast.error("Listen-Name ist Pflicht.");
      return;
    }
    if (!form.valid_from) {
      toast.error("Gueltig-ab-Datum ist Pflicht.");
      return;
    }
    if (form.valid_until && form.valid_until < form.valid_from) {
      toast.error("Gueltig-bis darf nicht vor Gueltig-ab liegen.");
      return;
    }

    setBusy(true);
    try {
      const pl = await pricingApi.uploadPricelist({
        file,
        supplier_name: form.supplier_name.trim(),
        supplier_location: form.supplier_location.trim() || undefined,
        list_name: form.list_name.trim(),
        valid_from: form.valid_from,
        valid_until: form.valid_until || undefined,
        auto_parse: form.auto_parse,
      });
      toast.success(
        form.auto_parse
          ? "Hochgeladen. Parse laeuft im Hintergrund."
          : "Hochgeladen. Du kannst den Parse manuell starten.",
      );
      router.push(`/dashboard/pricing/${pl.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          toast.error("Diese Datei wurde bereits hochgeladen (Duplikat).");
        } else if (err.status === 413) {
          toast.error(`Datei zu gross: ${err.detail ?? `> ${MAX_MB} MB`}`);
        } else {
          toast.error(err.detail ?? "Upload fehlgeschlagen");
        }
      } else {
        toast.error("Upload fehlgeschlagen");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Link
          href="/dashboard/pricing"
          className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-4 h-4" /> Zurueck zur Uebersicht
        </Link>
      </div>
      <header>
        <h1 className="text-3xl font-bold text-slate-900">Neue Preisliste hochladen</h1>
        <p className="text-slate-600 mt-1">
          PDF, Excel oder CSV deines Lieferanten. Nach dem Upload wird die Datei
          automatisch geparst.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Dropzone */}
        <Card>
          <CardHeader>
            <CardTitle>Datei</CardTitle>
          </CardHeader>
          <CardBody>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsOver(true);
              }}
              onDragLeave={() => setIsOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsOver(false);
                setFileSafe(e.dataTransfer.files?.[0] ?? null);
              }}
              onClick={() => !busy && inputRef.current?.click()}
              className={cn(
                "flex flex-col items-center justify-center h-48 rounded-xl border-2 border-dashed border-slate-300 bg-white text-center cursor-pointer transition-colors",
                isOver && "border-bauplan-500 bg-bauplan-50/40",
                busy && "opacity-60 cursor-wait",
                file && "border-success-500 bg-success-500/5",
              )}
            >
              <input
                ref={inputRef}
                type="file"
                accept={ALLOWED_EXT.join(",")}
                className="hidden"
                onChange={(e) => setFileSafe(e.target.files?.[0] ?? null)}
              />
              {file ? (
                <>
                  <CheckCircle2 className="w-10 h-10 text-success-500 mb-3" />
                  <div className="text-slate-900 font-medium truncate max-w-full px-4">
                    {file.name}
                  </div>
                  <div className="text-sm text-slate-500 mt-1">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="mt-3"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      setFile(null);
                    }}
                  >
                    Andere Datei waehlen
                  </Button>
                </>
              ) : (
                <>
                  <Upload className="w-10 h-10 text-bauplan-500 mb-3" />
                  <div className="text-slate-900 font-medium">
                    Datei hier ablegen oder klicken
                  </div>
                  <div className="text-sm text-slate-500 mt-1 px-6">
                    {ALLOWED_EXT.join(", ")} · max {MAX_MB} MB
                  </div>
                </>
              )}
            </div>
          </CardBody>
        </Card>

        {/* Metadaten */}
        <Card>
          <CardHeader>
            <CardTitle>Angaben zur Liste</CardTitle>
          </CardHeader>
          <CardBody className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="supplier_name">
                  Lieferant <span className="text-danger-500">*</span>
                </Label>
                <Input
                  id="supplier_name"
                  placeholder="z.B. Kemmler"
                  value={form.supplier_name}
                  onChange={(e) => patch("supplier_name", e.target.value)}
                  disabled={busy}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="supplier_location">Niederlassung (optional)</Label>
                <Input
                  id="supplier_location"
                  placeholder="z.B. Neu-Ulm"
                  value={form.supplier_location}
                  onChange={(e) => patch("supplier_location", e.target.value)}
                  disabled={busy}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="list_name">
                Listen-Name <span className="text-danger-500">*</span>
              </Label>
              <Input
                id="list_name"
                placeholder="z.B. Ausbau 2026-04"
                value={form.list_name}
                onChange={(e) => patch("list_name", e.target.value)}
                disabled={busy}
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="valid_from">
                  Gueltig ab <span className="text-danger-500">*</span>
                </Label>
                <Input
                  id="valid_from"
                  type="date"
                  value={form.valid_from}
                  onChange={(e) => patch("valid_from", e.target.value)}
                  disabled={busy}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="valid_until">Gueltig bis (optional)</Label>
                <Input
                  id="valid_until"
                  type="date"
                  value={form.valid_until}
                  onChange={(e) => patch("valid_until", e.target.value)}
                  disabled={busy}
                />
              </div>
            </div>

            <label className="flex items-center gap-2 pt-2 cursor-pointer text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.auto_parse}
                onChange={(e) => patch("auto_parse", e.target.checked)}
                disabled={busy}
                className="w-4 h-4"
              />
              Parse direkt nach Upload starten
            </label>
          </CardBody>
        </Card>

        <div className="flex justify-end gap-3">
          <Link href="/dashboard/pricing">
            <Button type="button" variant="ghost" disabled={busy}>
              Abbrechen
            </Button>
          </Link>
          <Button type="submit" disabled={busy || !file}>
            {busy ? "Wird hochgeladen …" : "Hochladen"}
          </Button>
        </div>
      </form>
    </div>
  );
}
