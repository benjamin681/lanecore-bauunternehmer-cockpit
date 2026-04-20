/**
 * Shared loading skeleton components.
 */

export function KpiCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 md:p-6 animate-pulse">
      <div className="h-3 bg-gray-200 rounded w-24 mb-3" />
      <div className="h-8 bg-gray-300 rounded w-16" />
    </div>
  );
}

export function KpiGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <KpiCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function TableRowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <tr className="animate-pulse border-t border-gray-100">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 bg-gray-200 rounded w-full max-w-24" />
        </td>
      ))}
    </tr>
  );
}

export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i} className="px-4 py-3 text-left">
                <div className="h-3 bg-gray-300 rounded w-20" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <TableRowSkeleton key={i} cols={cols} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse space-y-3">
      <div className="h-4 bg-gray-300 rounded w-32" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 bg-gray-200 rounded" style={{ width: `${70 + i * 5}%` }} />
      ))}
    </div>
  );
}

export function KanbanSkeleton({ columns = 4, cardsPerColumn = 2 }: { columns?: number; cardsPerColumn?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: columns }).map((_, c) => (
        <div key={c} className="space-y-3">
          <div className="flex items-center gap-2 animate-pulse">
            <div className="w-3 h-3 rounded-full bg-gray-300" />
            <div className="h-4 bg-gray-300 rounded w-24" />
          </div>
          {Array.from({ length: cardsPerColumn }).map((_, i) => (
            <CardSkeleton key={i} lines={2} />
          ))}
        </div>
      ))}
    </div>
  );
}
