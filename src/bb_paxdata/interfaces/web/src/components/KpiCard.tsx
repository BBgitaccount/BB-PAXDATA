import { cn } from '@/utils/helpers';
import type { ReactNode } from 'react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  accent?: 'white' | 'muted' | 'fail' | 'pass' | 'warn';
  trend?: number;
  monospace?: boolean;
}

export const KpiCard = ({
  title,
  value,
  subtitle,
  icon,
  accent = 'muted',
  trend,
  monospace = true,
}: KpiCardProps) => {
  const accentMap = {
    white: 'text-carbon-50',
    muted: 'text-carbon-200',
    fail: 'text-carbon-50',
    pass: 'text-carbon-50',
    warn: 'text-carbon-50',
  };

  const borderMap = {
    white: 'border-carbon-500',
    muted: 'border-carbon-550',
    fail: 'border-signal-fail',
    pass: 'border-signal-pass',
    warn: 'border-signal-warn',
  };

  return (
    <div
      className={cn(
        'bg-carbon-900 border border-hair p-5 relative group hover:translate-y-[-1px] transition-transform duration-150',
        borderMap[accent],
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <span className="label-micro">{title}</span>
        {icon && <div className="text-carbon-400">{icon}</div>}
      </div>
      <div
        className={cn(
          'text-2xl font-semibold tracking-tight',
          accentMap[accent],
          monospace && 'font-mono',
        )}
      >
        {value}
      </div>
      {subtitle && <div className="mt-2 text-2xs text-carbon-400 tracking-tight">{subtitle}</div>}
      {trend !== undefined && (
        <div
          className={cn(
            'mt-2 text-2xs font-mono',
            trend >= 0 ? 'text-carbon-300' : 'text-carbon-400',
          )}
        >
          {trend >= 0 ? '+' : ''}
          {trend}% vs önceki dönem
        </div>
      )}
      <div
        className={cn(
          'absolute bottom-0 left-0 h-px bg-carbon-50 transition-all duration-500',
          accent === 'white'
            ? 'w-full opacity-10'
            : 'w-0 group-hover:w-full opacity-0 group-hover:opacity-10',
        )}
      />
    </div>
  );
};
