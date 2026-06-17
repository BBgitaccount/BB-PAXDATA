import { CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import type { ToastMessage } from '@/types';
import { cn } from '@/utils/helpers';

interface ToastProps {
  toasts: ToastMessage[];
}

export const Toast = ({ toasts }: ToastProps) => {
  if (toasts.length === 0) return null;

  const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
  };

  const colors = {
    success: 'border-signal-pass text-carbon-50',
    error: 'border-signal-fail text-carbon-50',
    warning: 'border-signal-warn text-carbon-50',
    info: 'border-signal-info text-carbon-50',
  };

  return (
    <div className="fixed bottom-8 right-8 z-[100] flex flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = icons[toast.type];
        return (
          <div
            key={toast.id}
            className={cn(
              'bg-carbon-900 border border-hair px-4 py-3 flex items-center gap-3 min-w-[320px] shadow-elevated animate-[toast-lifecycle_4000ms_ease-in-out_forwards]',
              colors[toast.type],
            )}
          >
            <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
            <span className="text-xs font-medium tracking-tight flex-1">{toast.message}</span>
          </div>
        );
      })}
    </div>
  );
};
