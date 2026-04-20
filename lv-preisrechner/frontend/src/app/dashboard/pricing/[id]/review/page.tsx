"use client";

/**
 * Review-Page fuer Eintraege einer Supplier-Preisliste (B+3.3).
 *
 * - Laedt alle Entries via GET /pricelists/{id}?include_entries=true
 *   (der Parser-Worker begrenzt auf ~500 pro PDF; fuer B+3 reicht das
 *    clientseitig).
 * - Filter: Status (alle / needs_review / unsicher <0.7), Hersteller,
 *   Volltext-Suche auf product_name.
 * - Sortierbare Table (Seite/Artikel/Conf); Klick auf Zeile oeffnet Edit-
 *   Dialog.
 * - Speichern im Dialog aktualisiert die lokale Liste inline, kein Full-
 *   Reload.
 */

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, Pencil } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { pricingApi } from "@/lib/pricingApi";
import type {
  SupplierPriceEntry,
  SupplierPriceListDetail,
} from "@/lib/types/pricing";

import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import {
  Table,
  type SortDirection,
  type TableColumn,
} from "@/components/ui/table";

import { ReviewEntryDialog } from "./ReviewEntryDialog";

const PAGE_SIZE = 30;
type StatusFilter = "ALL" | "NEEDS_REVIEW" | "UNCERTAIN";

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "ALL", label: "Alle Einträge" },
  { value: "NEEDS_REVIEW", label: "Nur needs_review" },
  { value: "UNCERTAIN", label: "Nur unsichere (< 70 %)" },
];

function confidenceBadge(conf: number) {
  if (conf >= 0.9)
    return <Badge variant="success">{(conf * 100).toFixed(0)} %</Badge>;
  if (conf >= 0.7)
    return <Badge variant="info">{(conf * 100).toFixed(0)} %</Badge>;
  return <Badge variant="warning">{(conf * 100).toFixed(0)} %</Badge>;
}

export default function PricingReviewPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [detail, setDetail] = useState<SupplierPriceListDetail | null>(null);
  const [entries, setEntries] = useState<SupplierPriceEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("NEEDS_REVIEW");
  const [mfrFilter, setMfrFilter] = useState<string>("ALL");
  const [search, setSearch] = useState("");

  const [sortBy, setSortBy] = useState<string>("parser_confidence");
  const [sortDir, setSortDir] = useState<SortDirection>("asc");
  const [page, setPage] = useState(1);

  const [editing, setEditing] = useState<SupplierPriceEntry | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const data = await pricingApi.getPricelist(id, {
          includeEntries: true,
          limit: 500,
        });
        if (!active) return;
        setDetail(data);
        setEntries(data.entries ?? []);
      } catch (e) {
        const msg = e instanceof ApiError ? e.detail : "Laden fehlgeschlagen";
        toast.error(msg ?? "Laden fehlgeschlagen");
        router.replace(`/dashboard/pricing/${id}`);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [id, router]);

  const manufacturers = useMemo(() => {
    const set = new Set<string>();
    for (const e of entries) if (e.manufacturer) set.add(e.manufacturer);
    return Array.from(set).sort();
  }, [entries]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return entries.filter((e) => {
      if (statusFilter === "NEEDS_REVIEW" && !e.needs_review) return false;
      if (statusFilter === "UNCERTAIN" && e.parser_confidence >= 0.7) return false;
      if (mfrFilter !== "ALL" && (e.manufacturer ?? "") !== mfrFilter) return false;
      if (q && !e.product_name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [entries, statusFilter, mfrFilter, search]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const av = (a as unknown as Record<string, unknown>)[sortBy];
      const bv = (b as unknown as Record<string, unknown>)[sortBy];
      if (av === bv) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = (av as number | string) > (bv as number | string) ? 1 : -1;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sortBy, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const paged = sorted.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  // Reset zur Seite 1 bei Filter-Wechsel
  useEffect(() => {
    setPage(1);
  }, [statusFilter, mfrFilter, search]);

  function handleSaved(updated: SupplierPriceEntry) {
    setEntries((list) =>
      list.map((e) => (e.id === updated.id ? updated : e)),
    );
  }

  const columns: TableColumn<SupplierPriceEntry>[] = [
    {
      key: "source_page",
      label: "S.",
      sortable: true,
      align: "right",
      className: "tabular-nums text-slate-500",
      render: (r) => r.source_page ?? "—",
    },
    {
      key: "product_name",
      label: "Produkt",
      sortable: true,
      render: (r) => (
        <div className="min-w-0">
          <div className="font-medium text-slate-900 truncate max-w-sm">
            {r.product_name}
          </div>
          {r.manufacturer && (
            <div className="text-xs text-slate-500 truncate">
              {r.manufacturer}
              {r.category ? ` · ${r.category}` : ""}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "article_number",
      label: "Artikel",
      render: (r) =>
        r.article_number ? (
          <code className="text-xs text-slate-700">{r.article_number}</code>
        ) : (
          <span className="text-slate-300 text-xs">—</span>
        ),
    },
    {
      key: "unit",
      label: "Einheit",
      render: (r) => (
        <span className="text-slate-700 text-xs">
          {r.unit}
          {r.effective_unit && r.effective_unit !== r.unit && (
            <span className="text-slate-400"> → {r.effective_unit}</span>
          )}
        </span>
      ),
    },
    {
      key: "price_net",
      label: "Preis",
      align: "right",
      render: (r) => (
        <div className="text-xs tabular-nums">
          <div className="text-slate-900">{r.price_net.toFixed(2)} €</div>
          {r.price_per_effective_unit !== r.price_net && (
            <div className="text-slate-500">
              {r.price_per_effective_unit.toFixed(4)} €/{r.effective_unit}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "parser_confidence",
      label: "Conf.",
      sortable: true,
      align: "center",
      render: (r) => confidenceBadge(r.parser_confidence),
    },
    {
      key: "status",
      label: "Status",
      align: "center",
      render: (r) =>
        r.correction_applied ? (
          <Badge variant="success">
            <CheckCircle2 className="w-3 h-3 mr-1" /> reviewed
          </Badge>
        ) : r.needs_review ? (
          <Badge variant="warning">
            <AlertTriangle className="w-3 h-3 mr-1" /> offen
          </Badge>
        ) : (
          <span className="text-slate-300 text-xs">—</span>
        ),
    },
    {
      key: "actions",
      label: "",
      align: "right",
      render: () => <Pencil className="w-4 h-4 text-slate-400" />,
    },
  ];

  if (loading || !detail) {
    return <div className="py-20 text-center text-slate-500">Lade …</div>;
  }

  const openEntries = entries.filter((e) => e.needs_review).length;
  const reviewedEntries = entries.filter((e) => e.correction_applied).length;

  return (
    <div className="space-y-6">
      <Link
        href={`/dashboard/pricing/${id}`}
        className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" /> Zurueck zur Detail-Seite
      </Link>

      <header>
        <h1 className="text-3xl font-bold text-slate-900">Review</h1>
        <p className="text-slate-600 mt-1">
          <span className="font-medium">{detail.supplier_name}</span>
          {detail.supplier_location && ` — ${detail.supplier_location}`} ·{" "}
          {detail.list_name}
        </p>
        <div className="flex items-center gap-3 mt-2 flex-wrap text-sm">
          <span className="text-slate-600">
            {entries.length} Einträge geladen
          </span>
          <span className="text-amber-600">{openEntries} offen</span>
          <span className="text-emerald-600">{reviewedEntries} reviewed</span>
          <span className="text-slate-500">Aktuell gefiltert: {sorted.length}</span>
        </div>
      </header>

      {/* Filter-Leiste */}
      <Card>
        <CardBody>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Select
              value={statusFilter}
              onChange={(v) => setStatusFilter(v as StatusFilter)}
              options={STATUS_OPTIONS}
            />
            <Select
              value={mfrFilter}
              onChange={setMfrFilter}
              options={[
                { value: "ALL", label: "Alle Hersteller" },
                ...manufacturers.map((m) => ({ value: m, label: m })),
              ]}
            />
            <Input
              placeholder="Produktname suchen …"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </CardBody>
      </Card>

      {/* Confidence-Legende */}
      <div className="text-xs text-slate-500 flex items-center gap-3 flex-wrap">
        <span>Confidence:</span>
        <Badge variant="success">≥ 90 %</Badge>
        <span className="text-slate-400">sicher</span>
        <Badge variant="info">70–89 %</Badge>
        <span className="text-slate-400">ok</span>
        <Badge variant="warning">&lt; 70 %</Badge>
        <span className="text-slate-400">Review empfohlen</span>
      </div>

      <Table<SupplierPriceEntry>
        columns={columns}
        data={paged}
        getRowKey={(r) => r.id}
        sortBy={sortBy}
        sortDirection={sortDir}
        onSort={(k, d) => {
          setSortBy(k);
          setSortDir(d);
        }}
        onRowClick={(r) => setEditing(r)}
        empty="Keine Einträge im aktuellen Filter."
      />

      {totalPages > 1 && (
        <Pagination
          currentPage={pageSafe}
          totalPages={totalPages}
          onPageChange={setPage}
          totalItems={sorted.length}
          itemsPerPage={PAGE_SIZE}
        />
      )}

      <ReviewEntryDialog
        open={editing !== null}
        entry={editing}
        pricelistId={id}
        pdfSourceUrl={null}
        onClose={() => setEditing(null)}
        onSaved={handleSaved}
      />
    </div>
  );
}
