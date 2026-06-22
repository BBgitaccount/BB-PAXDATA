import { useState } from 'react';
import { cn } from '@/utils/helpers';

interface Column<T> {
  key: string;
  header: React.ReactNode;
  width?: string;
  render?: (row: T) => React.ReactNode;
  align?: 'left' | 'center' | 'right';
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  loading?: boolean;
  emptyText?: string;
  getRowClassName?: (row: T) => string;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  loading,
  emptyText = 'Veri bulunamadı',
  getRowClassName,
}: DataTableProps<T>) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const totalPages = Math.ceil(data.length / pageSize) || 1;
  const paginated = data.slice((page - 1) * pageSize, page * pageSize);

  if (loading) {
    return (
      <div className="border border-hair border-carbon-550">
        <div className="h-96 flex items-center justify-center">
          <div className="shimmer w-full h-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="border border-hair border-carbon-550">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-hair border-carbon-550">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    'px-4 py-3 text-left text-micro text-carbon-400 font-medium tracking-diplomatic uppercase bg-carbon-900',
                    col.width && col.width,
                  )}
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-sm text-carbon-400"
                >
                  {emptyText}
                </td>
              </tr>
            ) : (
              paginated.map((row) => {
                return (
                  <tr
                    key={keyExtractor(row)}
                    onClick={() => onRowClick?.(row)}
                    className={cn(
                      'border-b border-hair border-carbon-550/50 hover:bg-carbon-800/40 transition-colors',
                      onRowClick && 'cursor-pointer',
                      getRowClassName?.(row),
                    )}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={cn(
                          'px-4 py-3 text-sm text-carbon-200',
                          col.align === 'center' && 'text-center',
                          col.align === 'right' && 'text-right',
                        )}
                      >
                        {col.render
                          ? col.render(row)
                          : ((row as Record<string, unknown>)[col.key] as React.ReactNode)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {data.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 bg-carbon-900 border-t border-hair border-carbon-550">
          <div className="flex items-center gap-3">
            <span className="text-2xs text-carbon-400">Sayfa başına:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="bg-carbon-900 border border-hair border-carbon-550 text-2xs text-carbon-200 px-2 py-1"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="px-2 py-1 text-2xs text-carbon-300 border border-hair border-carbon-550 hover:text-carbon-50 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ◀
            </button>
            <span className="text-2xs text-carbon-400 font-mono">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="px-2 py-1 text-2xs text-carbon-300 border border-hair border-carbon-550 hover:text-carbon-50 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ▶
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
