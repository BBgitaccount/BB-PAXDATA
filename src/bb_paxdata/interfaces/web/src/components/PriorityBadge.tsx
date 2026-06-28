import type { TriagePriority } from '@/types';
import { cn } from '@/utils/helpers';

interface PriorityBadgeProps {
  priority: TriagePriority;
  className?: string;
}

export const PriorityBadge = ({ priority, className }: PriorityBadgeProps) => {
  const styles: Record<TriagePriority, string> = {
    NORMAL: 'text-carbon-400 border-carbon-550',
    HIGH_PRIORITY: 'text-carbon-200 border-carbon-400',
    SOVEREIGN_PRIORITY: 'text-carbon-50 border-carbon-200',
    CRITICAL: 'text-carbon-50 border-carbon-50 bg-carbon-800',
  };

  const labels: Record<TriagePriority, string> = {
    NORMAL: 'NORMAL',
    HIGH_PRIORITY: 'HIGH',
    SOVEREIGN_PRIORITY: 'SOVEREIGN',
    CRITICAL: 'CRITICAL',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 border border-hair text-micro font-mono font-medium tracking-diplomatic',
        styles[priority],
        className,
      )}
    >
      {labels[priority]}
    </span>
  );
};
