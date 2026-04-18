"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Dropzone } from "@/components/Dropzone";
import { ProgressBar } from "@/components/ProgressBar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, Job, pollJob } from "@/lib/api";

export default function NeuePreislistePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [haendler, setHaendler] = useState("");
  const [niederlassung, setNiederlassung] = useState("");
  const [stand, setStand] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);

  async function upload() {
    if (!file) {
      toast.error("Bitte PDF auswählen");
      return;
    }
    if (!haendler.trim()) {
      toast.error("Bitte Händler angeben");
      return;
    }
    const form = new FormData();
    form.set("file", file);
    form.set("haendler", haendler.trim());
    form.set("niederlassung", niederlassung.trim());
    form.set("stand_monat", stand.trim());
    setBusy(true);
    try {
      const j = await api<Job>("/price-lists/upload-async", {
        method: "POST",
        form,
        direct: true, // Umgeht Vercel-Proxy 4.5 MB Body-Limit
      });
      setJob(j);
      toast.success("Upload ok — Parsing läuft im Hintergrund");
      // Sofort zum Preislisten-Detail
      router.replace(`/dashboard/preislisten/${j.target_id}`);
    } catch (e: any) {
      const msg = e?.detail || e?.message || "Upload fehlgeschlagen";
      toast.error(`Upload fehlgeschlagen: ${msg}`);
      // Extra-Log in Console, damit man auf Handy per Remote-Debugging sehen kann
      console.error("Upload error:", e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold text-slate-900">Neue Preisliste hochladen</h1>
      <p className="text-slate-600 mt-1">
        Händler-PDF mit Ihren Einkaufspreisen. Wir extrahieren jeden Eintrag automatisch.
      </p>

      <div className="mt-8 rounded-2xl bg-white border border-slate-200 p-6 space-y-5">
        <Dropzone
          onFile={setFile}
          busy={busy}
          hint={file ? `Ausgewählt: ${file.name}` : "PDF bis 50 MB"}
        />

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="haendler">Händler *</Label>
            <Input
              id="haendler"
              placeholder="z.B. Kemmler, Wölpert, Raab Karcher"
              value={haendler}
              onChange={(e) => setHaendler(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="niederlassung">Niederlassung</Label>
            <Input
              id="niederlassung"
              placeholder="Neu-Ulm, Stuttgart …"
              value={niederlassung}
              onChange={(e) => setNiederlassung(e.target.value)}
            />
          </div>
        </div>
        <div>
          <Label htmlFor="stand">Stand (Monat/Jahr)</Label>
          <Input
            id="stand"
            placeholder="04/2026"
            value={stand}
            onChange={(e) => setStand(e.target.value)}
          />
        </div>

        {busy && job && (
          <div className="rounded-lg bg-bauplan-50 border border-bauplan-100 p-4 space-y-2">
            <div className="text-sm font-medium text-slate-900">
              {job.status === "queued" && "In Warteschlange…"}
              {job.status === "running" && (job.message || "Wird verarbeitet…")}
              {job.status === "done" && "Fertig!"}
              {job.status === "error" && "Fehler"}
            </div>
            <ProgressBar value={job.progress} />
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={() => history.back()} disabled={busy}>
            Abbrechen
          </Button>
          <Button onClick={upload} disabled={busy || !file}>
            {busy ? "Wird verarbeitet…" : "Hochladen & parsen"}
          </Button>
        </div>
      </div>

      <div className="mt-6 text-sm text-slate-500 leading-relaxed">
        <strong>Hinweis:</strong> Die Analyse läuft im Hintergrund. Bei großen
        Preislisten (20+ Seiten) kann es 2–5 Minuten dauern — der Fortschrittsbalken
        zeigt den aktuellen Status.
      </div>
    </div>
  );
}
