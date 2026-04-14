"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

export default function AnalysePage() {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);

      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("Nur PDF-Dateien werden akzeptiert.");
        return;
      }

      const sizeMb = file.size / (1024 * 1024);
      if (sizeMb > 50) {
        setError(`Datei zu groß: ${sizeMb.toFixed(1)}MB (Max: 50MB)`);
        return;
      }

      setIsUploading(true);

      try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch("/api/v1/bauplan/upload", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || body?.error || `Upload fehlgeschlagen (${res.status})`);
        }

        const data = await res.json();
        router.push(`/dashboard/analyse/${data.job_id}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
      } finally {
        setIsUploading(false);
      }
    },
    [router]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">Bauplan hochladen</h2>
      <p className="text-gray-500 mb-8">
        Laden Sie einen PDF-Bauplan hoch. Die KI analysiert automatisch Räume, Wände
        und Decken.
      </p>

      {/* Upload Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-16 text-center transition-colors ${
          isDragging
            ? "border-primary-500 bg-primary-50"
            : "border-gray-300 hover:border-gray-400"
        } ${isUploading ? "opacity-50 pointer-events-none" : ""}`}
      >
        <div className="text-5xl mb-4">📄</div>
        <p className="text-lg font-medium text-gray-900">
          {isUploading ? "Wird hochgeladen..." : "Bauplan hier ablegen"}
        </p>
        <p className="text-sm text-gray-500 mt-2">PDF bis 50MB — Grundrisse, Deckenspiegel, Schnitte</p>

        <label className="mt-6 inline-block cursor-pointer">
          <span className="bg-primary-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-primary-700 transition-colors inline-block">
            Datei auswählen
          </span>
          <input
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
        </label>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
          {error}
        </div>
      )}

      <div className="mt-8 p-6 bg-gray-50 rounded-lg text-sm text-gray-600 space-y-2">
        <p className="font-medium text-gray-800">Unterstützte Plantypen:</p>
        <ul className="list-disc list-inside space-y-1">
          <li><strong>Grundrisse</strong> — Räume, Wandlängen, Wandtypen (W112, W115, W118)</li>
          <li><strong>Deckenspiegel</strong> — Deckentypen, Abhängehöhen, Nassraum-Kennzeichnung</li>
          <li><strong>Schnitte</strong> — Raumhöhen, Geschosshöhen</li>
          <li><strong>Details</strong> — Konstruktionsaufbau, Profiltypen</li>
        </ul>
        <p className="text-xs text-gray-400 mt-2">
          Typische Analysedauer: 1–3 Minuten pro Seite
        </p>
      </div>
    </div>
  );
}
