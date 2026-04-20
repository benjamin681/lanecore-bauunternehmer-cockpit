"use client";

/**
 * Showcase-Seite fuer die UI-Komponenten-Bibliothek.
 *
 * Nicht im Menue verlinkt. Direkt aufrufbar unter
 *   /dashboard/dev/components
 *
 * In Production sichtbar, aber unverlinkt — wer den Pfad kennt, kann rein.
 * Fuer echten Lockdown spaeter per ENV-Flag aufbauen.
 */

import { useState } from "react";
import Link from "next/link";
import { Beaker, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { Table, TableColumn, SortDirection } from "@/components/ui/table";

type DemoRow = {
  id: string;
  produkt: string;
  hersteller: string;
  preis: number;
  konfidenz: number;
};

const DEMO_ROWS: DemoRow[] = [
  { id: "1", produkt: "GKB 2000x1250x12,5 mm", hersteller: "Knauf", preis: 3.0, konfidenz: 1.0 },
  { id: "2", produkt: "Uniflott 25 kg/Sack", hersteller: "Knauf", preis: 1.06, konfidenz: 0.95 },
  { id: "3", produkt: "CW 50/50 BL=2600 mm", hersteller: "Knauf", preis: 112.8, konfidenz: 0.55 },
  { id: "4", produkt: "AKURIT MEP Kalkzementputz", hersteller: "AKURIT", preis: 0.315, konfidenz: 0.95 },
  { id: "5", produkt: "Primo Color Armierungsgewebe", hersteller: "Primo Color", preis: 0.81, konfidenz: 1.0 },
];

export default function ComponentsShowcase() {
  const [sortBy, setSortBy] = useState<string | undefined>("konfidenz");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [open, setOpen] = useState(false);
  const [select, setSelect] = useState("alle");
  const [page, setPage] = useState(3);

  const sortedRows = [...DEMO_ROWS].sort((a, b) => {
    if (!sortBy) return 0;
    const av = (a as unknown as Record<string, unknown>)[sortBy] as number | string;
    const bv = (b as unknown as Record<string, unknown>)[sortBy] as number | string;
    if (av === bv) return 0;
    const cmp = av > bv ? 1 : -1;
    return sortDir === "asc" ? cmp : -cmp;
  });

  const columns: TableColumn<DemoRow>[] = [
    {
      key: "produkt",
      label: "Produkt",
      sortable: true,
      render: (r) => <span className="font-medium text-slate-900">{r.produkt}</span>,
    },
    { key: "hersteller", label: "Hersteller", sortable: true },
    {
      key: "preis",
      label: "Preis",
      sortable: true,
      align: "right",
      render: (r) => <span className="tabular-nums">{r.preis.toFixed(2)} €</span>,
    },
    {
      key: "konfidenz",
      label: "Konfidenz",
      sortable: true,
      align: "right",
      render: (r) => (
        <Badge variant={r.konfidenz >= 0.9 ? "success" : r.konfidenz >= 0.7 ? "info" : "warning"}>
          {(r.konfidenz * 100).toFixed(0)} %
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-10">
      <header className="flex items-center gap-3">
        <Beaker className="w-7 h-7 text-bauplan-600" />
        <div>
          <h1 className="text-3xl font-bold text-slate-900">UI-Komponenten-Showcase</h1>
          <p className="text-sm text-slate-600 mt-1">
            Dev-Seite fuer die UI-Library. Nicht im Menue, nur direkt aufrufbar unter{" "}
            <code className="px-1.5 py-0.5 bg-slate-100 rounded text-xs">
              /dashboard/dev/components
            </code>
            .{" "}
            <Link href="/dashboard" className="text-bauplan-600 hover:underline">
              → zurueck zur Uebersicht
            </Link>
          </p>
        </div>
      </header>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle>Table</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-sm text-slate-600">
            Klickbare Header fuer Sortierung. Klick auf Zeile zeigt Alert.
          </p>
          <Table<DemoRow>
            columns={columns}
            data={sortedRows}
            getRowKey={(r) => r.id}
            sortBy={sortBy}
            sortDirection={sortDir}
            onSort={(key, dir) => {
              setSortBy(key);
              setSortDir(dir);
            }}
            onRowClick={(r) => alert(`Klick: ${r.produkt}`)}
          />
          <div className="text-xs text-slate-500">
            Aktive Sortierung: <code>{sortBy}</code> · {sortDir}
          </div>
        </CardBody>
      </Card>

      {/* Dialog */}
      <Card>
        <CardHeader>
          <CardTitle>Dialog</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-sm text-slate-600">
            Modal mit Focus-Trap, Escape- und Backdrop-Close, Body-Scroll-Lock.
          </p>
          <Button onClick={() => setOpen(true)}>Dialog oeffnen</Button>
          <Dialog
            open={open}
            onClose={() => setOpen(false)}
            title="Preis-Eintrag bestaetigen"
            description="Diese Aktion kann rueckgaengig gemacht werden."
            size="md"
            actions={[
              { label: "Abbrechen", variant: "ghost" },
              {
                label: (
                  <span className="inline-flex items-center gap-1">
                    <Check className="w-4 h-4" /> Bestaetigen
                  </span>
                ),
                variant: "primary",
                onClick: () => alert("bestaetigt"),
              },
            ]}
          >
            <div className="space-y-3 text-sm text-slate-700">
              <p>Probe-Inhalt fuer den Dialog.</p>
              <Input placeholder="Tab-Focus-Test 1" />
              <Input placeholder="Tab-Focus-Test 2" />
              <Select
                options={[
                  { value: "a", label: "Option A" },
                  { value: "b", label: "Option B" },
                ]}
                placeholder="Select im Dialog"
              />
            </div>
          </Dialog>
        </CardBody>
      </Card>

      {/* Select */}
      <Card>
        <CardHeader>
          <CardTitle>Select</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-sm text-slate-600">
            Native-Select gestylt wie Input — mobil-freundlich, screenreader-tauglich.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Select
              value={select}
              onChange={setSelect}
              options={[
                { value: "alle", label: "Alle anzeigen" },
                { value: "review", label: "Nur needs_review" },
                { value: "ok", label: "Nur verifiziert" },
              ]}
            />
            <Select
              options={[
                { value: "1", label: "Knauf" },
                { value: "2", label: "Kemmler" },
                { value: "3", label: "Baumit (disabled)", disabled: true },
              ]}
              placeholder="Hersteller waehlen …"
            />
            <Select
              disabled
              options={[{ value: "x", label: "disabled" }]}
              placeholder="disabled"
            />
          </div>
          <div className="text-xs text-slate-500">
            Aktueller Wert: <code>{select}</code>
          </div>
        </CardBody>
      </Card>

      {/* Pagination */}
      <Card>
        <CardHeader>
          <CardTitle>Pagination</CardTitle>
        </CardHeader>
        <CardBody className="space-y-6">
          <p className="text-sm text-slate-600">
            Erste/Zurueck/Vor/Letzte + Seitenzahlen mit "…" Luecken. Mobile: nur
            Zurueck/Vor.
          </p>
          <Pagination
            currentPage={page}
            totalPages={12}
            onPageChange={setPage}
            totalItems={327}
            itemsPerPage={30}
          />
          <div className="text-xs text-slate-500">Aktuelle Seite: {page}</div>
          <div className="pt-4 border-t border-slate-200">
            <p className="text-xs text-slate-500 mb-2">Wenige Seiten (kein "…"):</p>
            <Pagination currentPage={2} totalPages={3} onPageChange={() => {}} />
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
