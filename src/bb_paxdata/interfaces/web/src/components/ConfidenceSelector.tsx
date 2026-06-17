import { cn } from '@/utils/helpers';
import type { ConfidenceLevel } from '@/types';

interface ConfidenceSelectorProps {
  value: ConfidenceLevel | null;
  onChange: (val: ConfidenceLevel) => void;
  disabled?: boolean;
}

export const ConfidenceSelector = ({ value, onChange, disabled }: ConfidenceSelectorProps) => {
  const options: ConfidenceLevel[] = ['LOW', 'MEDIUM', 'HIGH'];

  return (
    <div className="flex gap-2">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          disabled={disabled}
          onClick={() => onChange(opt)}
          className={cn(
            'flex-1 py-2 text-xs font-medium tracking-diplomatic border transition-all duration-swift',
            value === opt
              ? 'bg-carbon-50 text-carbon-950 border-carbon-50'
              : 'bg-transparent text-carbon-400 border-carbon-550 hover:border-carbon-400 hover:text-carbon-200',
            disabled && 'opacity-40 cursor-not-allowed',
          )}
        >
          {opt === 'LOW' && 'DÜŞÜK'}
          {opt === 'MEDIUM' && 'ORTA'}
          {opt === 'HIGH' && 'YÜKSEK'}
        </button>
      ))}
    </div>
  );
};
