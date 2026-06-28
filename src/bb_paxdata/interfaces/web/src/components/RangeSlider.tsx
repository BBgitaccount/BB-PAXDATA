import type React from 'react';

interface RangeSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  displayValue?: string | number;
}

export const RangeSlider = ({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  displayValue,
}: RangeSliderProps) => {
  const percentage = ((value - min) / (max - min)) * 100;
  const progressStyle = {
    '--range-progress': `${percentage}%`,
  } as React.CSSProperties;

  return (
    <div className="py-3 border-b border-hair border-carbon-550/50">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm text-carbon-200">{label}</span>
        <span className="text-xs font-mono font-semibold text-carbon-100">
          {displayValue !== undefined ? displayValue : value}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={progressStyle}
        className="w-full bg-transparent accent-transparent focus:outline-none"
      />
    </div>
  );
};
