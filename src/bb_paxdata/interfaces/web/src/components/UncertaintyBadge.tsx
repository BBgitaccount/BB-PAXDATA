/**
 * UncertaintyBadge.tsx
 *
 * Displays a colour-coded confidence badge for AI analysis outputs.
 *
 * Usage:
 *   <UncertaintyBadge score={0.73} />
 *   <UncertaintyBadge status="HIGH" />
 *   <UncertaintyBadge score={0.45} status="LOW" />
 *
 * Colour semantics (mirrors Python UncertaintyScorer thresholds):
 *   HIGH   ≥ 0.80  → green  (signal-pass)
 *   MEDIUM ≥ 0.60  → amber  (signal-warn)
 *   LOW    < 0.60  → red    (signal-fail)
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export type UncertaintyStatus = 'HIGH' | 'MEDIUM' | 'LOW';

export interface UncertaintyBadgeProps {
  /** Raw confidence score from AISentenceAnalysis.coherence_score (0.0 – 1.0) */
  score?: number | null;
  /** Pre-computed label from API (preferred when available) */
  status?: UncertaintyStatus | string | null;
  /** Show numeric percentage next to the label */
  showScore?: boolean;
}

// ─── Config ───────────────────────────────────────────────────────────────────

interface BadgeConfig {
  label: string;
  className: string;
  dotClass: string;
}

const CONFIG: Record<UncertaintyStatus, BadgeConfig> = {
  HIGH: {
    label: 'YÜKSEK GÜVEN',
    className: 'text-signal-pass bg-signal-pass/10 border-signal-pass/30',
    dotClass: 'bg-signal-pass',
  },
  MEDIUM: {
    label: 'ORTA GÜVEN',
    className: 'text-signal-warn bg-signal-warn/10 border-signal-warn/30',
    dotClass: 'bg-signal-warn',
  },
  LOW: {
    label: 'DÜŞÜK GÜVEN',
    className: 'text-signal-fail bg-signal-fail/10 border-signal-fail/30',
    dotClass: 'bg-signal-fail',
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function deriveStatus(score?: number | null, status?: string | null): UncertaintyStatus | null {
  // Prefer explicit status from API
  if (status === 'HIGH' || status === 'MEDIUM' || status === 'LOW') return status;

  // Fall back to computing from raw score
  if (score == null) return null;
  if (score >= 0.8) return 'HIGH';
  if (score >= 0.6) return 'MEDIUM';
  return 'LOW';
}

// ─── Component ────────────────────────────────────────────────────────────────

export const UncertaintyBadge = ({ score, status, showScore = true }: UncertaintyBadgeProps) => {
  const resolved = deriveStatus(score, status);
  if (!resolved) return null;

  const { label, className, dotClass } = CONFIG[resolved];
  const pctStr = showScore && score != null ? ` (${(score * 100).toFixed(0)}%)` : '';

  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 px-2 py-0.5',
        'rounded-full border',
        'text-3xs font-mono font-medium',
        'select-none whitespace-nowrap',
        className,
      ].join(' ')}
      title={`AI confidence: ${score != null ? (score * 100).toFixed(1) + '%' : resolved}`}
    >
      {/* Status dot */}
      <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${dotClass}`} />
      {label}
      {pctStr}
    </span>
  );
};

// ─── Row-level wrapper (for table cells) ─────────────────────────────────────

/**
 * UncertaintyCell — renders badge with a subtle row background tint.
 * Use inside <td> or <div> in review queue tables.
 */
export const UncertaintyCell = (props: UncertaintyBadgeProps) => (
  <div className="flex items-center">
    <UncertaintyBadge {...props} />
  </div>
);
