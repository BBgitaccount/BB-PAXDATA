import type { ConfidenceLevel, HumanVerdict, QueueStatus } from '@/types';
import { cn } from '@/utils/helpers';

interface StatusBadgeProps {
  status: QueueStatus | HumanVerdict | ConfidenceLevel | string;
  className?: string;
}

export const StatusBadge = ({ status, className }: StatusBadgeProps) => {
  const statusStyles: Record<string, string> = {
    PENDING: 'text-carbon-400 border-carbon-550',
    ASSIGNED: 'text-carbon-300 border-carbon-500',
    IN_REVIEW: 'text-carbon-50 border-carbon-300',
    APPROVED: 'text-carbon-50 border-signal-pass',
    REJECTED: 'text-carbon-50 border-signal-fail',
    MODIFIED: 'text-carbon-50 border-signal-warn',
    ESCALATED: 'text-carbon-50 border-carbon-100',
    CONFIRMED_FAIL: 'text-carbon-50 border-signal-fail',
    CONFIRMED_PASS: 'text-carbon-50 border-signal-pass',
    CORRECTED: 'text-carbon-50 border-signal-warn',
    LOW: 'text-carbon-400 border-carbon-550',
    MEDIUM: 'text-carbon-200 border-carbon-400',
    HIGH: 'text-carbon-50 border-carbon-200',
  };

  const statusLabels: Record<string, string> = {
    PENDING: 'BEKLEMEDE',
    ASSIGNED: 'ATANDI',
    IN_REVIEW: 'İNCELENİYOR',
    APPROVED: 'ONAYLANDI',
    REJECTED: 'REDDEDİLDİ',
    MODIFIED: 'DEĞİŞTİRİLDİ',
    ESCALATED: 'ESKALE',
    CONFIRMED_FAIL: 'HATA ONAYLANDI',
    CONFIRMED_PASS: 'YANLIŞ ALARM',
    CORRECTED: 'DÜZELTİLDİ',
    LOW: 'DÜŞÜK',
    MEDIUM: 'ORTA',
    HIGH: 'YÜKSEK',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 border border-hair text-micro font-mono font-medium tracking-diplomatic',
        statusStyles[status] || 'text-carbon-400 border-carbon-550',
        className,
      )}
    >
      {statusLabels[status] || status}
    </span>
  );
};
