import { DataTable } from './DataTable';
import { StatusBadge } from './StatusBadge';
import { formatDate } from '@/utils/helpers';
import type { AuditEntry } from '@/types';
import { Link } from 'lucide-react';

interface AuditTrailTableProps {
  data: AuditEntry[];
  loading?: boolean;
}

export const AuditTrailTable = ({ data, loading }: AuditTrailTableProps) => {
  return (
    <DataTable
      columns={[
        {
          key: 'audit_id',
          header: 'Audit ID',
          width: '100px',
          render: (r) => <span className="font-mono text-carbon-300">{r.audit_id}</span>,
        },
        {
          key: 'log_id',
          header: 'Log ID',
          width: '80px',
          render: (r) => (
            <span className="font-mono text-carbon-300 flex items-center gap-1">
              <Link className="w-3 h-3" /> {r.log_id}
            </span>
          ),
        },
        {
          key: 'action_type',
          header: 'Aksiyon',
          width: '120px',
          render: (r) => <StatusBadge status={r.action_type} />,
        },
        {
          key: 'previous_verdict',
          header: 'Önceki',
          width: '100px',
          render: (r) =>
            r.previous_verdict ? (
              <StatusBadge status={r.previous_verdict} />
            ) : (
              <span className="text-carbon-500">—</span>
            ),
        },
        {
          key: 'new_verdict',
          header: 'Yeni',
          width: '100px',
          render: (r) =>
            r.new_verdict ? (
              <StatusBadge status={r.new_verdict} />
            ) : (
              <span className="text-carbon-500">—</span>
            ),
        },
        {
          key: 'previous_value',
          header: 'Önceki Değer',
          width: '100px',
          render: (r) =>
            r.previous_value !== null ? (
              <span className="font-mono text-carbon-300">{r.previous_value}</span>
            ) : (
              <span className="text-carbon-500">—</span>
            ),
        },
        {
          key: 'new_value',
          header: 'Yeni Değer',
          width: '100px',
          render: (r) =>
            r.new_value !== null ? (
              <span className="font-mono text-carbon-300">{r.new_value}</span>
            ) : (
              <span className="text-carbon-500">—</span>
            ),
        },
        {
          key: 'performed_by',
          header: 'Kim',
          width: '160px',
          render: (r) => <span className="text-2xs text-carbon-300">{r.performed_by}</span>,
        },
        {
          key: 'performed_at',
          header: 'Ne Zaman',
          width: '140px',
          render: (r) => (
            <span className="text-2xs text-carbon-400">{formatDate(r.performed_at)}</span>
          ),
        },
        {
          key: 'justification',
          header: 'Gerekçe',
          render: (r) => (
            <span className="text-2xs text-carbon-400 max-w-xs truncate">{r.justification}</span>
          ),
        },
        {
          key: 'review_status',
          header: 'Durum',
          width: '100px',
          render: (r) => <StatusBadge status={r.review_status} />,
        },
      ]}
      data={data}
      keyExtractor={(r) => r.audit_id}
      loading={loading}
    />
  );
};
