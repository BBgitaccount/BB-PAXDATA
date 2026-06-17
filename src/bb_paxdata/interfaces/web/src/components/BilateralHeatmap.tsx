/**
 * BilateralHeatmap – Faz 1.1
 *
 * Diplomatik ikili ilişkileri affinity_score üzerinden ısı haritasında gösterir.
 * Time Slider ile panel bazında zaman içindeki değişimi animasyonlu görselleştirir.
 *
 * Referans: Trager (2010) Costly Signaling, Fischer DNA network edge semantics.
 */
import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  Cell,
} from 'recharts';
import type { TooltipProps } from 'recharts';
import { Play, Pause, SkipBack, SkipForward, Globe } from 'lucide-react';
import type { BilateralSentimentData, PanelTimelineEntry } from '@/types';
import { useUIStore } from '@/store/uiStore';

// ─── Tooltip ───────────────────────────────────────────────────────────────

const HeatmapTooltip = ({ active, payload }: TooltipProps<number, string>) => {
  const theme = useUIStore((s) => s.theme);
  const isDark = theme === 'dark';
  if (active && payload && payload.length) {
    const d = payload[0].payload as BilateralSentimentData & {
      x: number;
      y: number;
    };
    const scoreColor =
      d.affinity_score > 0.3 ? '#4ade80' : d.affinity_score < -0.3 ? '#f87171' : '#a1a1aa';
    return (
      <div
        style={{
          background: isDark ? 'rgba(15, 15, 20, 0.97)' : 'rgba(255, 255, 255, 0.97)',
          border: isDark ? '1px solid #2a2a3a' : '1px solid #ced4da',
          borderRadius: 6,
          padding: '10px 14px',
          boxShadow: isDark ? '0 8px 32px rgba(0,0,0,0.6)' : '0 8px 32px rgba(0,0,0,0.1)',
          minWidth: 200,
        }}
      >
        <p
          style={{
            fontWeight: 700,
            color: isDark ? '#f0f0f0' : '#1a1a1a',
            marginBottom: 8,
            fontSize: 13,
          }}
        >
          {d.from_country} → {d.to_country}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
            }}
          >
            <span style={{ color: isDark ? '#8a8a9a' : '#495057' }}>İlişki tipi</span>
            <span style={{ color: isDark ? '#d4d4e0' : '#212529', fontWeight: 600 }}>
              {d.relationship_type}
            </span>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
            }}
          >
            <span style={{ color: isDark ? '#8a8a9a' : '#495057' }}>Affinity</span>
            <span
              style={{
                color: scoreColor,
                fontWeight: 700,
                fontFamily: 'monospace',
              }}
            >
              {d.affinity_score.toFixed(3)}
            </span>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
            }}
          >
            <span style={{ color: isDark ? '#8a8a9a' : '#495057' }}>Avg. Sentiment</span>
            <span
              style={{
                color: isDark ? '#d4d4e0' : '#212529',
                fontFamily: 'monospace',
              }}
            >
              {d.avg_sentiment.toFixed(3)}
            </span>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
            }}
          >
            <span style={{ color: isDark ? '#8a8a9a' : '#495057' }}>Etkileşim</span>
            <span style={{ color: isDark ? '#d4d4e0' : '#212529' }}>{d.interaction_count}</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

// ─── Color scale ───────────────────────────────────────────────────────────

function affinityToColor(score: number, isDark: boolean): string {
  // Diverging: deep red → neutral gray → deep green
  if (score >= 0.7) return '#166534'; // very positive
  if (score >= 0.4) return '#15803d';
  if (score >= 0.15) return '#4ade80';
  if (score >= -0.15) return isDark ? '#3f3f50' : '#e2e2e9'; // neutral
  if (score >= -0.4) return '#f87171';
  if (score >= -0.7) return '#dc2626';
  return '#7f1d1d'; // very negative
}

// ─── Legend ────────────────────────────────────────────────────────────────

const ColorLegend = () => {
  const theme = useUIStore((s) => s.theme);
  const isDark = theme === 'dark';
  const stops = [
    { color: '#7f1d1d', label: '< -0.7' },
    { color: '#dc2626', label: '-0.7' },
    { color: '#f87171', label: '-0.4' },
    { color: isDark ? '#3f3f50' : '#e2e2e9', label: '0' },
    { color: '#4ade80', label: '+0.4' },
    { color: '#15803d', label: '+0.7' },
    { color: '#166534', label: '> +0.7' },
  ];
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        flexWrap: 'wrap',
        marginTop: 6,
      }}
    >
      <span
        style={{
          fontSize: 11,
          color: isDark ? '#6b7280' : '#888899',
          marginRight: 4,
        }}
      >
        Affinity:
      </span>
      {stops.map(({ color, label }) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <div
            style={{
              width: 14,
              height: 14,
              background: color,
              borderRadius: 2,
              border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
            }}
          />
          <span style={{ fontSize: 10, color: isDark ? '#9ca3af' : '#495057' }}>{label}</span>
        </div>
      ))}
    </div>
  );
};

// ─── Time Slider Controls ───────────────────────────────────────────────────

interface SliderControlsProps {
  steps: PanelTimelineEntry[];
  currentIdx: number;
  isPlaying: boolean;
  onPrev: () => void;
  onNext: () => void;
  onTogglePlay: () => void;
  onSeek: (idx: number) => void;
}

const SliderControls = ({
  steps,
  currentIdx,
  isPlaying,
  onPrev,
  onNext,
  onTogglePlay,
  onSeek,
}: SliderControlsProps) => {
  const current = steps[currentIdx];
  const theme = useUIStore((s) => s.theme);
  const isDark = theme === 'dark';

  return (
    <div
      style={{
        background: isDark ? 'rgba(20, 20, 30, 0.8)' : 'rgba(255, 255, 255, 0.8)',
        border: isDark ? '1px solid #2a2a3a' : '1px solid #dee2e6',
        borderRadius: 8,
        padding: '10px 14px',
        marginBottom: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      {/* Label row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Globe size={14} color="#6366f1" />
          <span
            style={{
              color: isDark ? '#e0e0f0' : '#1a1a1a',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {current?.title ?? 'Tüm Paneller'}
          </span>
          {current?.date_str && (
            <span
              style={{
                background: isDark ? '#1e1b4b' : '#e0e7ff',
                color: isDark ? '#a5b4fc' : '#4f46e5',
                fontSize: 11,
                padding: '1px 8px',
                borderRadius: 99,
                fontFamily: 'monospace',
              }}
            >
              {current.date_str}
            </span>
          )}
        </div>
        <span style={{ color: isDark ? '#6b7280' : '#868e96', fontSize: 11 }}>
          {currentIdx + 1} / {steps.length}
        </span>
      </div>

      {/* Playback controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          id="bilateral-slider-prev"
          onClick={onPrev}
          disabled={currentIdx === 0}
          style={{
            background: 'transparent',
            border: isDark ? '1px solid #3a3a4a' : '1px solid #ced4da',
            borderRadius: 6,
            padding: '4px 8px',
            color: currentIdx === 0 ? (isDark ? '#444' : '#ccc') : isDark ? '#a1a1aa' : '#495057',
            cursor: currentIdx === 0 ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <SkipBack size={14} />
        </button>

        <button
          id="bilateral-slider-play"
          onClick={onTogglePlay}
          style={{
            background: isPlaying
              ? '#4f46e5'
              : isDark
                ? 'rgba(79,70,229,0.15)'
                : 'rgba(79,70,229,0.08)',
            border: '1px solid #4f46e5',
            borderRadius: 6,
            padding: '4px 12px',
            color: isPlaying ? '#ffffff' : '#4f46e5',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 12,
            fontWeight: 600,
            transition: 'background 0.2s',
          }}
        >
          {isPlaying ? <Pause size={13} /> : <Play size={13} />}
          {isPlaying ? 'Durdur' : 'Oynat'}
        </button>

        <button
          id="bilateral-slider-next"
          onClick={onNext}
          disabled={currentIdx === steps.length - 1}
          style={{
            background: 'transparent',
            border: isDark ? '1px solid #3a3a4a' : '1px solid #ced4da',
            borderRadius: 6,
            padding: '4px 8px',
            color:
              currentIdx === steps.length - 1
                ? isDark
                  ? '#444'
                  : '#ccc'
                : isDark
                  ? '#a1a1aa'
                  : '#495057',
            cursor: currentIdx === steps.length - 1 ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <SkipForward size={14} />
        </button>

        {/* Scrubber */}
        <input
          id="bilateral-timeline-scrubber"
          type="range"
          min={0}
          max={steps.length - 1}
          value={currentIdx}
          onChange={(e) => onSeek(Number(e.target.value))}
          style={{ flex: 1, accentColor: '#6366f1', cursor: 'pointer' }}
        />
      </div>

      {/* Step dots */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {steps.map((s, i) => (
          <button
            key={s.file_id}
            onClick={() => onSeek(i)}
            title={s.title}
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: i === currentIdx ? '#6366f1' : isDark ? '#2a2a3a' : '#e2e2e9',
              border:
                i === currentIdx
                  ? isDark
                    ? '2px solid #a5b4fc'
                    : '2px solid #4f46e5'
                  : isDark
                    ? '1px solid #3a3a4a'
                    : '1px solid #ced4da',
              cursor: 'pointer',
              padding: 0,
              transition: 'background 0.15s, border 0.15s',
            }}
          />
        ))}
      </div>
    </div>
  );
};

// ─── Main component ─────────────────────────────────────────────────────────

interface BilateralHeatmapProps {
  /** Aggregated data for all-panels view (no file_id filter). */
  data: BilateralSentimentData[];
  /** Optional ordered list of panels to drive the time slider. */
  timeline?: PanelTimelineEntry[];
  /** Callback when slider moves to a new step — parent fetches panel-specific data. */
  onTimelineStep?: (entry: PanelTimelineEntry | null) => void;
  /** Auto-play interval in ms (default 2 500). */
  playIntervalMs?: number;
}

export const BilateralHeatmap = ({
  data,
  timeline,
  onTimelineStep,
  playIntervalMs = 2500,
}: BilateralHeatmapProps) => {
  const theme = useUIStore((s) => s.theme);
  const isDark = theme === 'dark';
  const hasTimeline = timeline && timeline.length > 1;
  const [sliderIdx, setSliderIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Playback engine ──────────────────────────────────────────────────────
  const stopPlay = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  const handleSeek = useCallback(
    (idx: number) => {
      stopPlay();
      setSliderIdx(idx);
      if (hasTimeline && onTimelineStep) {
        onTimelineStep(timeline![idx] ?? null);
      }
    },
    [stopPlay, hasTimeline, timeline, onTimelineStep],
  );

  const handleTogglePlay = useCallback(() => {
    if (isPlaying) {
      stopPlay();
      return;
    }
    if (!hasTimeline) return;
    setIsPlaying(true);
    intervalRef.current = setInterval(() => {
      setSliderIdx((prev) => {
        const next = prev + 1;
        if (next >= timeline!.length) {
          stopPlay();
          return prev;
        }
        if (onTimelineStep) onTimelineStep(timeline![next]);
        return next;
      });
    }, playIntervalMs);
  }, [isPlaying, stopPlay, hasTimeline, timeline, onTimelineStep, playIntervalMs]);

  // cleanup on unmount
  useEffect(() => () => stopPlay(), [stopPlay]);

  // ── Chart data processing ────────────────────────────────────────────────
  const uniqueCountries = useMemo(
    () => Array.from(new Set(data.flatMap((d) => [d.from_country, d.to_country]))).sort(),
    [data],
  );

  const processedData = useMemo(
    () =>
      data.map((d) => ({
        ...d,
        x: uniqueCountries.indexOf(d.to_country),
        y: uniqueCountries.indexOf(d.from_country),
        z: Math.abs(d.affinity_score) * 200 + 40,
      })),
    [data, uniqueCountries],
  );

  if (!data || data.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: 200,
          border: isDark ? '1px dashed #2a2a3a' : '1px dashed #ced4da',
          borderRadius: 8,
          color: isDark ? '#4b5563' : '#868e96',
          fontSize: 13,
        }}
      >
        Henüz analiz edilmiş ikili ilişki bulunamadı.
      </div>
    );
  }

  return (
    <div style={{ width: '100%' }}>
      {/* Time Slider */}
      {hasTimeline && (
        <SliderControls
          steps={timeline!}
          currentIdx={sliderIdx}
          isPlaying={isPlaying}
          onPrev={() => handleSeek(Math.max(0, sliderIdx - 1))}
          onNext={() => handleSeek(Math.min(timeline!.length - 1, sliderIdx + 1))}
          onTogglePlay={handleTogglePlay}
          onSeek={handleSeek}
        />
      )}

      {/* Heatmap Chart */}
      <div
        style={{
          height: 380,
          transition: 'opacity 0.3s ease',
          opacity: isPlaying ? 0.85 : 1,
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 70, left: 90 }}>
            <XAxis
              type="number"
              dataKey="x"
              name="Hedef (To)"
              domain={[-0.5, uniqueCountries.length - 0.5]}
              tickFormatter={(val) => uniqueCountries[val] || ''}
              tick={{
                fill: isDark ? '#6b7280' : '#495057',
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace',
              }}
              tickLine={false}
              axisLine={{ stroke: isDark ? '#2a2a3a' : '#dee2e6' }}
              interval={0}
              angle={-45}
              textAnchor="end"
            />
            <YAxis
              type="number"
              dataKey="y"
              name="Kaynak (From)"
              domain={[-0.5, uniqueCountries.length - 0.5]}
              tickFormatter={(val) => uniqueCountries[val] || ''}
              tick={{
                fill: isDark ? '#6b7280' : '#495057',
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace',
              }}
              tickLine={false}
              axisLine={{ stroke: isDark ? '#2a2a3a' : '#dee2e6' }}
              interval={0}
            />
            <ZAxis type="number" dataKey="z" range={[60, 500]} />
            <Tooltip
              content={<HeatmapTooltip />}
              cursor={{ strokeDasharray: '3 3', stroke: '#4f46e5' }}
            />
            <Scatter data={processedData} shape="square">
              {processedData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={affinityToColor(entry.affinity_score, isDark)}
                  stroke={isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'}
                  strokeWidth={1}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Color legend */}
      <ColorLegend />
    </div>
  );
};
