import { DataTable } from './DataTable';
import { formatDate } from '@/utils/helpers';
import type { Reviewer } from '@/types';
import { ToggleLeft, ToggleRight, Pencil } from 'lucide-react';

interface ReviewerTableProps {
  data: Reviewer[];
  loading?: boolean;
  onEdit?: (reviewer: Reviewer) => void;
  onToggleActive?: (reviewer: Reviewer) => void;
}

export const ReviewerTable = ({ data, loading, onEdit, onToggleActive }: ReviewerTableProps) => {
  return (
    <DataTable
      columns={[
        {
          key: 'reviewer_id',
          header: 'Reviewer ID',
          width: '200px',
          render: (r) => <span className="text-2xs text-carbon-200">{r.reviewer_id}</span>,
        },
        {
          key: 'scope_type',
          header: 'Scope',
          width: '100px',
          render: (r) => (
            <span className="text-micro font-mono text-carbon-300 uppercase">{r.scope_type}</span>
          ),
        },
        {
          key: 'scope_value',
          header: 'Değer',
          width: '120px',
          render: (r) => <span className="text-2xs text-carbon-400">{r.scope_value}</span>,
        },
        {
          key: 'permission_level',
          header: 'Yetki',
          width: '100px',
          render: (r) => (
            <span className="text-micro font-mono text-carbon-300 uppercase">
              {r.permission_level}
            </span>
          ),
        },
        {
          key: 'max_daily',
          header: 'Günlük Limit',
          width: '100px',
          render: (r) => <span className="font-mono text-carbon-200">{r.max_daily_reviews}</span>,
        },
        {
          key: 'current',
          header: 'Bugün',
          width: '80px',
          render: (r) => <span className="font-mono text-carbon-200">{r.current_daily_count}</span>,
        },
        {
          key: 'is_active',
          header: 'Durum',
          width: '80px',
          render: (r) => (
            <span
              className={r.is_active ? 'text-micro text-signal-pass' : 'text-micro text-carbon-500'}
            >
              {r.is_active ? 'AKTİF' : 'PASİF'}
            </span>
          ),
        },
        {
          key: 'created_at',
          header: 'Oluşturulma',
          width: '140px',
          render: (r) => (
            <span className="text-2xs text-carbon-400">{formatDate(r.created_at)}</span>
          ),
        },
        {
          key: 'actions',
          header: '',
          width: '100px',
          render: (r) => (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onEdit?.(r)}
                className="p-1 text-carbon-400 hover:text-carbon-50"
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => onToggleActive?.(r)}
                className="p-1 text-carbon-400 hover:text-carbon-50"
              >
                {r.is_active ? (
                  <ToggleRight className="w-4 h-4" />
                ) : (
                  <ToggleLeft className="w-4 h-4" />
                )}
              </button>
            </div>
          ),
        },
      ]}
      data={data}
      keyExtractor={(r) => r.reviewer_id}
      loading={loading}
    />
  );
};
