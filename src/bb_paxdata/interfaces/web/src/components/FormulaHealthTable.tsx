import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ChevronDown, ChevronUp, TableProperties } from 'lucide-react';
import { useState } from 'react';
import { DataTable } from '@/components/DataTable';
import { apiClient } from '@/services/apiClient';
import type { FormulaHealth } from '@/types';
import { cn } from '@/utils/helpers';

interface FormulaHealthTableProps {
  data?: FormulaHealth[];
}

export const FormulaHealthTable = ({ data: propData }: FormulaHealthTableProps) => {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [sortBy, setSortBy] = useState<keyof FormulaHealth | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const healthQuery = useQuery({
    queryKey: ['formulas-health-table'],
    queryFn: () => apiClient.get<FormulaHealth[]>('/api/v1/dashboard/formulas/health'),
    enabled: !propData,
  });

  const healthData = propData ?? healthQuery.data ?? [];

  // Filter formulas with False Positive rate > 30% (0.30)
  const highFpFormulas = healthData.filter((item) => item.false_positive_rate > 0.3);

  // Sorting logic
  const sortedData = [...healthData].sort((a, b) => {
    if (!sortBy) return 0;
    const valA = a[sortBy];
    const valB = b[sortBy];

    if (typeof valA === 'string' && typeof valB === 'string') {
      return sortDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }

    const numA = (valA as number) || 0;
    const numB = (valB as number) || 0;
    return sortDir === 'asc' ? numA - numB : numB - numA;
  });

  const renderSortableHeader = (
    label: string,
    key: keyof FormulaHealth,
    align: 'left' | 'right' = 'left',
  ) => {
    const isActive = sortBy === key;
    return (
      <button
        onClick={() => {
          if (sortBy === key) {
            setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
          } else {
            setSortBy(key);
            setSortDir('desc');
          }
        }}
        className={cn(
          'flex items-center gap-1 hover:text-carbon-100 transition-colors w-full font-mono text-micro font-medium uppercase tracking-diplomatic outline-none',
          isActive ? 'text-carbon-100' : 'text-carbon-400',
          align === 'right' ? 'justify-end' : 'justify-start',
        )}
      >
        <span>{label}</span>
        {isActive ? (
          sortDir === 'asc' ? (
            <ChevronUp className="w-3.5 h-3.5 text-brand" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-brand" />
          )
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-carbon-600 opacity-0 hover:opacity-100 transition-opacity" />
        )}
      </button>
    );
  };

  const columns = [
    {
      key: 'formula_name',
      header: renderSortableHeader('Formül', 'formula_name', 'left'),
      render: (r: FormulaHealth) => (
        <span className="font-mono text-2xs text-carbon-200">{r.formula_name}</span>
      ),
    },
    {
      key: 'total_fail',
      header: renderSortableHeader('Toplam FAIL', 'total_fail', 'right'),
      align: 'right' as const,
      render: (r: FormulaHealth) => (
        <span className="font-mono text-2xs text-carbon-200">{r.total_fail.toLocaleString()}</span>
      ),
    },
    {
      key: 'false_positive_rate',
      header: renderSortableHeader('False Positive %', 'false_positive_rate', 'right'),
      align: 'right' as const,
      render: (r: FormulaHealth) => {
        const pct = (r.false_positive_rate * 100).toFixed(1);
        const isHigh = r.false_positive_rate > 0.3;
        return (
          <span
            className={`font-mono text-2xs ${isHigh ? 'text-signal-fail font-semibold' : 'text-carbon-200'}`}
          >
            %{pct}
          </span>
        );
      },
    },
    {
      key: 'correction_rate',
      header: renderSortableHeader('Düzeltme %', 'correction_rate', 'right'),
      align: 'right' as const,
      render: (r: FormulaHealth) => {
        const pct = (r.correction_rate * 100).toFixed(1);
        return <span className="font-mono text-2xs text-carbon-200">%{pct}</span>;
      },
    },
    {
      key: 'confirmed_fail_count',
      header: renderSortableHeader('Onaylanan FAIL', 'confirmed_fail_count', 'right'),
      align: 'right' as const,
      render: (r: FormulaHealth) => (
        <span className="font-mono text-2xs text-carbon-300">
          {r.confirmed_fail_count.toLocaleString()}
        </span>
      ),
    },
    {
      key: 'false_positive_count',
      header: renderSortableHeader('False Positive', 'false_positive_count', 'right'),
      align: 'right' as const,
      render: (r: FormulaHealth) => (
        <span className="font-mono text-2xs text-carbon-300">
          {r.false_positive_count.toLocaleString()}
        </span>
      ),
    },
    {
      key: 'correction_count',
      header: renderSortableHeader('Düzeltme', 'correction_count', 'right'),
      align: 'right' as const,
      render: (r: FormulaHealth) => (
        <span className="font-mono text-2xs text-carbon-300">
          {r.correction_count.toLocaleString()}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {highFpFormulas.length > 0 && (
        <div className="space-y-2">
          {highFpFormulas.map((item) => {
            const pct = (item.false_positive_rate * 100).toFixed(1);
            return (
              <div
                key={`warning-${item.formula_name}`}
                className="flex items-start gap-3 p-4 bg-signal-fail/10 border border-hair border-signal-fail text-signal-fail text-xs animate-[fade-in-up_200ms_ease-out]"
              >
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <span className="font-semibold block mb-0.5">Yüksek False Positive Oranı</span>
                  <span>
                    <strong>{item.formula_name}</strong> formülü %{pct} oranında false positive
                    üretiyor! Eşik ayarı gerekebilir.
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="bg-carbon-900 border border-hair border-carbon-550 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TableProperties className="w-4 h-4 text-carbon-400" />
            <h3 className="text-sm font-semibold text-carbon-50 tracking-tight">
              Formül Sağlık Tablosu
            </h3>
          </div>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-carbon-800 hover:bg-carbon-700 border border-hair border-carbon-550 text-2xs font-mono text-carbon-300 hover:text-carbon-50 transition-colors"
          >
            {isCollapsed ? 'Tabloyu Göster' : 'Tabloyu Gizle'}
            {isCollapsed ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5" />
            )}
          </button>
        </div>

        {!isCollapsed && (
          <DataTable
            columns={columns}
            data={sortedData}
            keyExtractor={(r) => r.formula_name}
            loading={!propData && healthQuery.isPending}
            getRowClassName={(r) =>
              r.false_positive_rate > 0.3 ? 'bg-signal-fail/5 border-l-2 border-signal-fail' : ''
            }
          />
        )}
      </div>
    </div>
  );
};
