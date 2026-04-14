"use client";

import { useEffect, useState } from "react";

interface Projekt {
  id: string;
  name: string;
  auftraggeber?: string;
  analyse_count: number;
  created_at: string;
}

export default function ProjektePage() {
  const [projekte, setProjekte] = useState<Projekt[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formAuftraggeber, setFormAuftraggeber] = useState("");

  useEffect(() => {
    fetch("/api/v1/projekte/")
      .then((r) => r.json())
      .then(setProjekte)
      .catch(() => {});
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const res = await fetch("/api/v1/projekte/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: formName, auftraggeber: formAuftraggeber || null }),
    });
    if (res.ok) {
      const p = await res.json();
      setProjekte((prev) => [p, ...prev]);
      setShowForm(false);
      setFormName("");
      setFormAuftraggeber("");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Projekte</h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-primary-600 text-white px-5 py-2.5 rounded-lg font-medium hover:bg-primary-700 transition-colors"
        >
          + Neues Projekt
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-white rounded-xl border border-gray-200 p-6 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Projektname *</label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              required
              minLength={2}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="z.B. Himmelweiler III — Kopfbau EG"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Auftraggeber</label>
            <input
              type="text"
              value={formAuftraggeber}
              onChange={(e) => setFormAuftraggeber(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="z.B. Max Mustermann GmbH"
            />
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              className="bg-primary-600 text-white px-5 py-2.5 rounded-lg font-medium hover:bg-primary-700"
            >
              Erstellen
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="text-gray-600 px-5 py-2.5 rounded-lg font-medium hover:bg-gray-100"
            >
              Abbrechen
            </button>
          </div>
        </form>
      )}

      {/* Project list */}
      {projekte.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500">
          Noch keine Projekte. Erstellen Sie Ihr erstes Projekt.
        </div>
      ) : (
        <div className="grid gap-4">
          {projekte.map((p) => (
            <div
              key={p.id}
              className="bg-white rounded-xl border border-gray-200 p-6 flex items-center justify-between hover:border-gray-300 transition-colors"
            >
              <div>
                <h3 className="font-semibold text-gray-900">{p.name}</h3>
                {p.auftraggeber && (
                  <p className="text-sm text-gray-500 mt-1">{p.auftraggeber}</p>
                )}
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-700">
                  {p.analyse_count} Analyse{p.analyse_count !== 1 ? "n" : ""}
                </p>
                <p className="text-xs text-gray-400">
                  {new Date(p.created_at).toLocaleDateString("de-DE")}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
