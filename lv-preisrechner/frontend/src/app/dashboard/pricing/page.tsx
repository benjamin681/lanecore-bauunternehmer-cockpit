"use client";

/**
 * Uebersichtsseite aller SupplierPriceLists des Tenants (B+3.2).
 *
 * Laeuft gegen die neue /pricing/pricelists-API (parallel zur Legacy-UI
 * unter /dashboard/preislisten).
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle, Plus } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { pricingApi } from "@/lib/pricingApi";
import { fmtDate } from "@/lib/format";
import {
  PRICING_STATUS_META,
  PRICING_STATUS_VALUES,
  type PricingStatus,
  type SupplierPriceList,
} from "@/lib/types/pricing";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { Table, TableColumn } from "@/components/ui/table";

const PAGE_SIZE = 20;

type StatusFilter = "ALL" | PricingStatus;

const STATUS_FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "ALL", label: "Alle Status" },
  ...PRICING_STATUS_VALUES.map((s) => ({
    value: s as StatusFilter,
    label: PRICING_STATUS_META[s].label,
  })),
];

export default function PricingListPage() {
  const router = useRouter();
  const [rows, setRows] = useState<SupplierPriceList[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await pricingApi.listPricelists({
        status: status === "ALL" ? null : status,
        offset: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setRows(data);
      // Heuristik: wenn voller Batch, gibt's evtl. noch mehr Seiten.
      setHasMore(data.length === PAGE_SIZE);
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : "Unbekannter Fehler";
      toast.error(msg || "Laden fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  }, [status, page]);

  useEffect(() => {
    load();
  }, [load]);

  // Beim Filter-Wechsel zurueck auf Seite 1
  function onStatusChange(value: string) {
    setStatus(value as StatusFilter);
    setPage(1);
  }

  const columns: TableColumn<SupplierPriceList>[] = [
    {
      key: "supplier",
      label: "Lieferant",
      render: (r) => (
        <div className="min-w-0">
          <div className="font-medium text-slate-900 truncate">{r.supplier_name}</div>
          {r.supplier_location && (
            <div className="text-xs text-slate-500 truncate">{r.supplier_location}</div>
          )}
        </div>
      ),
    },
    {
      key: "list_name",
      label: "Liste",
      render: (r) => <span className="text-slate-700">{r.list_name}</span>,
    },
    {
      key: "status",
      label: "Status",
      render: (r) => {
        const meta = PRICING_STATUS_META[r.status];
        return <Badge variant={meta.badge}>{meta.label}</Badge>;
      },
    },
    {
      key: "valid",
      label: "Gültig",
      render: (r) => (
        <span className="text-slate-700 text-xs tabular-nums whitespace-nowrap">
          {fmtDate(r.valid_from)}
          {r.valid_until ? ` – ${fmtDate(r.valid_until)}` : " – offen"}
        </span>
      ),
    },
    {
      key: "entries",
      label: "Einträge",
      align: "right",
      render: (r) => {
        const total = r.entries_total ?? 0;
        const reviewed = r.entries_reviewed ?? 0;
        if (total === 0) return <span className="text-slate-400 text-xs">—</span>;
        return (
          <span className="text-slate-700 tabular-nums">
            {reviewed}<span className="text-slate-400">/{total}</span>
          </span>
        );
      },
    },
    {
      key: "is_active",
      label: "Aktiv",
      align: "center",
      render: (r) =>
        r.is_active ? (
          <Badge variant="success">
            <CheckCircle className="w-3 h-3 mr-1" /> aktiv
          </Badge>
        ) : (
          <span className="text-slate-300 text-xs">—</span>
        ),
    },
    {
      key: "uploaded_at",
      label: "Hochgeladen",
      align: "right",
      render: (r) => (
        <span className="text-xs text-slate-500 tabular-nums whitespace-nowrap">
          {fmtDate(r.uploaded_at)}
        </span>
      ),
    },
  ];

  // Fuer die Pagination-Komponente brauchen wir eine "totalPages"-Zahl; da das
  // Backend (noch) kein total liefert, schaetzen wir: aktuelle Seite + 1 falls
  // hasMore. Damit sind mindestens 2 Seiten navigierbar; sobald hasMore=false,
  // ist die letzte bekannte Seite totalPages.
  const totalPages = hasMore ? page + 1 : page;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Lieferanten-Preise</h1>
          <p className="text-slate-600 mt-1">
            Preislisten deiner Lieferanten — hochladen, parsen, reviewen, freigeben.
          </p>
        </div>
        <Link href="/dashboard/pricing/upload">
          <Button>
            <Plus className="w-4 h-4" /> Neue Preisliste hochladen
          </Button>
        </Link>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="w-56">
          <Select
            value={status}
            onChange={onStatusChange}
            options={STATUS_FILTER_OPTIONS}
          />
        </div>
        {loading && <span className="text-sm text-slate-500">Lade …</span>}
      </div>

      <Table<SupplierPriceList>
        columns={columns}
        data={rows}
        getRowKey={(r) => r.id}
        onRowClick={(r) => router.push(`/dashboard/pricing/${r.id}`)}
        empty={
          status === "ALL"
            ? "Noch keine Preislisten hochgeladen."
            : `Keine Preislisten mit Status „${PRICING_STATUS_META[status as PricingStatus]?.label}"`
        }
      />

      {(totalPages > 1 || hasMore) && (
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          itemsPerPage={PAGE_SIZE}
        />
      )}
    </div>
  );
}
