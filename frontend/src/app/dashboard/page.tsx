"use client";

import { useEffect, useState } from "react";

interface DashboardStats {
  projekte: number;
  analysen_gesamt: number;
  analysen_erfolgreich: number;
  eingesparte_stunden: number;
  kosten_usd_gesamt: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    fetch("/api/v1/stats/dashboard")
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  const s = stats ?? {
    projekte: 0,
    analysen_gesamt: 0,
    analysen_erfolgreich: 0,
    eingesparte_stunden: 0,
    kosten_usd_gesamt: 0,
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-500">Projekte</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{s.projekte}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-500">Analysen</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {s.analysen_erfolgreich}
            {s.analysen_gesamt > s.analysen_erfolgreich && (
              <span className="text-lg text-gray-400"> / {s.analysen_gesamt}</span>
            )}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-500">Eingesparte Stunden</p>
          <p className="text-3xl font-bold text-green-600 mt-2">{s.eingesparte_stunden}h</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <p className="text-sm text-gray-500">API-Kosten gesamt</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">${s.kosten_usd_gesamt.toFixed(2)}</p>
        </div>
      </div>

      {s.analysen_erfolgreich === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <p className="text-gray-500 text-lg mb-4">
            Noch keine Analysen vorhanden.
          </p>
          <a
            href="/dashboard/analyse"
            className="inline-block bg-primary-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-primary-700 transition-colors"
          >
            Ersten Bauplan analysieren
          </a>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Schnellzugriff</h3>
          <div className="flex gap-4">
            <a
              href="/dashboard/analyse"
              className="flex-1 p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors text-center"
            >
              <p className="text-2xl mb-1">📐</p>
              <p className="font-medium text-gray-900">Neuen Plan analysieren</p>
            </a>
            <a
              href="/dashboard/projekte"
              className="flex-1 p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors text-center"
            >
              <p className="text-2xl mb-1">📁</p>
              <p className="font-medium text-gray-900">Projekte verwalten</p>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
