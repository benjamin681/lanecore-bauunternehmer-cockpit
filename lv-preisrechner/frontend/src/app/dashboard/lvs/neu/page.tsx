"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Dropzone } from "@/components/Dropzone";
import { ProgressBar } from "@/components/ProgressBar";
import { Button } from "@/components/ui/button";
import { api, Job, pollJob } from "@/lib/api";

export default function NeuesLvPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);

  async function upload() {
    if (!file) {
      toast.error("Bitte PDF auswählen");
      return;
    }
    const form = new FormData();
    form.set("file", file);
    setBusy(true);
    try {
      const j = await api<Job>("/lvs/upload-async", { method: "POST", form });
      setJob(j);
      const final = await pollJob(j.id, { onProgress: (u) => setJob(u) });
      if (final.status === "error") {
        toast.error(final.error_message || "Parsing fehlgeschlagen");
        return;
      }
      toast.success("LV verarbeitet");
      router.replace(`/dashboard/lvs/${final.target_id}`);
    } catch (e: any) {
      const msg = e?.detail || e?.message || "Upload fehlgeschlagen";
      toast.error(`Upload fehlgeschlagen: ${msg}`);
      console.error("Upload error:", e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold text-slate-900">Neues LV hochladen</h1>
      <p className="text-slate-600 mt-1">
        LV-PDF vom Auftraggeber. Wir extrahieren jede Position automatisch.
      </p>

      <div className="mt-8 rounded-2xl bg-white border border-slate-200 p-6 space-y-5">
        <Dropzone
          onFile={setFile}
          busy={busy}
          hint={file ? `Ausgewählt: ${file.name}` : "PDF bis 50 MB"}
        />

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
            {busy ? "Wird verarbeitet…" : "Hochladen & analysieren"}
          </Button>
        </div>
      </div>

      <div className="mt-6 rounded-xl bg-bauplan-50 border border-bauplan-100 p-5 text-sm text-slate-700 leading-relaxed">
        <div className="font-medium text-slate-900">So geht's weiter:</div>
        <ol className="list-decimal list-inside mt-2 space-y-1">
          <li>Claude Vision liest jede Position (OZ, Menge, Einheit, Kurztext, System).</li>
          <li>Sie prüfen die erkannten Positionen und korrigieren bei Bedarf.</li>
          <li>Die Kalkulation rechnet automatisch gegen Ihre aktive Preisliste.</li>
          <li>Sie bekommen ein fertiges PDF mit EP und GP zum Download.</li>
        </ol>
      </div>
    </div>
  );
}
