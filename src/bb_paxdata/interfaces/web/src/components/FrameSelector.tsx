import { useState } from 'react';
import type { FrameType } from '@/types';
import { cn } from '@/utils/helpers';

const frames: FrameType[] = [
  'problem_definition',
  'cause_interpretation',
  'moral_evaluation',
  'remedy_suggestion',
  'episodic',
  'thematic',
  'conflict_frame',
  'security_frame',
  'humanitarian_frame',
  'legal_frame',
  'negotiation_frame',
  'occupation_frame',
  'two_state_frame',
  'effectiveness_frame',
  'sovereignty_frame',
  'multilateral_frame',
  'threat_frame',
  'deterrence_frame',
  'peace_frame',
  'neutral',
];

interface FrameSelectorProps {
  value: FrameType | null;
  onChange: (val: FrameType) => void;
  disabled?: boolean;
}

export const FrameSelector = ({ value, onChange, disabled }: FrameSelectorProps) => {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={cn(
          'w-full px-3 py-2.5 text-sm bg-carbon-900 border border-hair border-carbon-550 text-left flex items-center justify-between transition-colors',
          !disabled && 'hover:border-carbon-400',
          disabled && 'opacity-40 cursor-not-allowed',
        )}
      >
        <span className={value ? 'text-carbon-50' : 'text-carbon-400'}>
          {value || 'Frame seçin...'}
        </span>
        <span className="text-carbon-500 text-xs">▼</span>
      </button>

      {open && !disabled && (
        <div className="absolute z-50 w-full mt-1 bg-carbon-900 border border-hair border-carbon-550 max-h-60 overflow-auto shadow-elevated">
          {frames.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => {
                onChange(f);
                setOpen(false);
              }}
              className={cn(
                'w-full px-3 py-2 text-left text-xs hover:bg-carbon-800 transition-colors',
                value === f ? 'text-carbon-50 bg-carbon-800' : 'text-carbon-300',
              )}
            >
              {f}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
