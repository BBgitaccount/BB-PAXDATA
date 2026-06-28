import React, { useEffect, useState } from 'react';

interface SentimentBarProps {
  score: number; // -1 to 1
  className?: string;
  showLabel?: boolean;
}

export const SentimentBar: React.FC<SentimentBarProps> = ({
  score,
  className = '',
  showLabel = true,
}) => {
  const [animatedWidth, setAnimatedWidth] = useState(0);

  // Clamp score between -1 and 1
  const clampedScore = Math.max(-1, Math.min(1, score));

  // Convert score to percentage (0 to 100)
  const percentage = ((clampedScore + 1) / 2) * 100;

  // Determine color based on score
  const getColor = () => {
    if (clampedScore >= 0.5) return 'var(--sentiment-ally)';
    if (clampedScore >= 0.2) return 'var(--sentiment-partner)';
    if (clampedScore >= -0.2) return 'var(--sentiment-neutral)';
    if (clampedScore >= -0.5) return 'var(--sentiment-cautious)';
    return 'var(--sentiment-adversary)';
  };

  // Animate width on mount and score change
  useEffect(() => {
    setAnimatedWidth(percentage);
  }, [percentage]);

  const getSentimentLabel = () => {
    if (clampedScore >= 0.5) return 'ALLY';
    if (clampedScore >= 0.2) return 'PARTNER';
    if (clampedScore >= -0.2) return 'NEUTRAL';
    if (clampedScore >= -0.5) return 'CAUTIOUS';
    return 'ADVERSARY';
  };

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {showLabel && (
        <div className="flex justify-between items-center">
          <span className="geoint-data-label">Sentiment</span>
          <span className="text-[10px] font-mono font-semibold" style={{ color: getColor() }}>
            {getSentimentLabel()}
          </span>
        </div>
      )}
      <div
        className="relative h-2 w-full rounded-sm overflow-hidden"
        style={{ backgroundColor: 'var(--geoint-elevated)' }}
      >
        {/* Background track */}
        <div className="absolute inset-0 flex">
          {/* Red zone */}
          <div
            className="h-full"
            style={{
              width: '20%',
              backgroundColor: 'var(--sentiment-adversary)',
              opacity: 0.2,
            }}
          />
          {/* Yellow zone */}
          <div
            className="h-full"
            style={{
              width: '30%',
              backgroundColor: 'var(--sentiment-cautious)',
              opacity: 0.2,
            }}
          />
          {/* Gray zone */}
          <div
            className="h-full"
            style={{
              width: '30%',
              backgroundColor: 'var(--sentiment-neutral)',
              opacity: 0.2,
            }}
          />
          {/* Blue zone */}
          <div
            className="h-full"
            style={{
              width: '10%',
              backgroundColor: 'var(--sentiment-partner)',
              opacity: 0.2,
            }}
          />
          {/* Green zone */}
          <div
            className="h-full"
            style={{
              width: '10%',
              backgroundColor: 'var(--sentiment-ally)',
              opacity: 0.2,
            }}
          />
        </div>

        {/* Fill bar */}
        <div
          className="absolute top-0 bottom-0 left-0 rounded-sm transition-all duration-500 ease-out"
          style={{
            width: `${animatedWidth}%`,
            backgroundColor: getColor(),
            boxShadow:
              clampedScore >= 0.5
                ? 'var(--glow-ally)'
                : clampedScore <= -0.5
                  ? 'var(--glow-adversary)'
                  : 'none',
          }}
        />

        {/* Center marker */}
        <div className="absolute top-0 bottom-0 w-0.5 bg-white/30" style={{ left: '50%' }} />
      </div>

      {/* Score display */}
      {showLabel && (
        <div className="flex justify-between items-center">
          <span className="text-[9px] font-mono text-[var(--text-tertiary)]">-1.0</span>
          <span className="text-[11px] font-mono font-bold" style={{ color: getColor() }}>
            {clampedScore.toFixed(2)}
          </span>
          <span className="text-[9px] font-mono text-[var(--text-tertiary)]">+1.0</span>
        </div>
      )}
    </div>
  );
};
