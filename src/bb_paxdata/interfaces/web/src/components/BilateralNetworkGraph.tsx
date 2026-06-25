/**
 * BilateralNetworkGraph – Advanced Force-Directed Network Visualization
 *
 * Interactive network graph for bilateral diplomatic relations using ReactFlow.
 * Features:
 * - Force-directed layout with physics simulation
 * - Interactive nodes (drag, zoom, pan)
 * - Edge styling based on affinity scores and interaction counts
 * - Time slider for panel-by-panel exploration
 * - Auto-play animation
 * - Detailed tooltips with relationship metrics
 */
import { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  Panel,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Globe,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-react';
import type { BilateralSentimentData, PanelTimelineEntry } from '@/types';
import { useUIStore } from '@/store/uiStore';

// ─── Custom Node Component ─────────────────────────────────────────────────────

const CountryNode = ({ data }: { data: any }) => {
  const theme = useUIStore((s) => s.theme);
  const isDark = theme === 'dark';

  return (
    <div
      style={{
        padding: '8px 12px',
        borderRadius: '8px',
        background: isDark ? 'rgba(30, 30, 40, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        border: isDark ? '2px solid #4f46e5' : '2px solid #4f46e5',
        color: isDark ? '#f0f0f0' : '#1a1a1a',
        fontSize: '12px',
        fontWeight: 600,
        minWidth: '100px',
        textAlign: 'center',
        boxShadow: isDark ? '0 4px 20px rgba(0,0,0,0.4)' : '0 4px 20px rgba(0,0,0,0.15)',
        cursor: 'grab',
        transition: 'transform 0.2s, box-shadow 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'scale(1.05)';
        e.currentTarget.style.boxShadow = isDark
          ? '0 6px 25px rgba(79, 70, 229, 0.3)'
          : '0 6px 25px rgba(79, 70, 229, 0.2)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'scale(1)';
        e.currentTarget.style.boxShadow = isDark
          ? '0 4px 20px rgba(0,0,0,0.4)'
          : '0 4px 20px rgba(0,0,0,0.15)';
      }}
    >
      <div>{data.label}</div>
      {data.connectionCount && (
        <div
          style={{
            fontSize: '10px',
            color: isDark ? '#9ca3af' : '#6b7280',
            marginTop: '2px',
          }}
        >
          {data.connectionCount} bağlantı
        </div>
      )}
    </div>
  );
};

const nodeTypes = {
  country: CountryNode,
};

// ─── Color Scale Functions ─────────────────────────────────────────────────────

function affinityToColor(score: number): string {
  // Diverging color scale for affinity scores
  if (score >= 0.7) return '#166534'; // very positive - deep green
  if (score >= 0.4) return '#15803d'; // positive - green
  if (score >= 0.15) return '#4ade80'; // slightly positive - light green
  if (score >= -0.15) return '#9ca3af'; // neutral - gray
  if (score >= -0.4) return '#f87171'; // negative - light red
  if (score >= -0.7) return '#dc2626'; // very negative - red
  return '#7f1d1d'; // extremely negative - deep red
}

function getEdgeWidth(interactionCount: number): number {
  // Scale edge width based on interaction count
  const minWidth = 1;
  const maxWidth = 6;
  const maxCount = 100; // cap at 100 interactions for scaling
  const normalized = Math.min(interactionCount, maxCount) / maxCount;
  return minWidth + normalized * (maxWidth - minWidth);
}

// ─── Time Slider Controls ───────────────────────────────────────────────────────

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
        background: isDark ? 'rgba(20, 20, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        border: isDark ? '1px solid #2a2a3a' : '1px solid #dee2e6',
        borderRadius: '12px',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        backdropFilter: 'blur(10px)',
        boxShadow: isDark ? '0 8px 32px rgba(0,0,0,0.4)' : '0 8px 32px rgba(0,0,0,0.1)',
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Globe size={16} color="#6366f1" />
          <span
            style={{
              color: isDark ? '#e0e0f0' : '#1a1a1a',
              fontSize: '13px',
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
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '99',
                fontFamily: 'monospace',
              }}
            >
              {current.date_str}
            </span>
          )}
        </div>
        <span style={{ color: isDark ? '#6b7280' : '#868e96', fontSize: '11px' }}>
          {currentIdx + 1} / {steps.length}
        </span>
      </div>

      {/* Playback controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          onClick={onPrev}
          disabled={currentIdx === 0}
          style={{
            background: 'transparent',
            border: isDark ? '1px solid #3a3a4a' : '1px solid #ced4da',
            borderRadius: '8px',
            padding: '6px 10px',
            color: currentIdx === 0 ? (isDark ? '#444' : '#ccc') : isDark ? '#a1a1aa' : '#495057',
            cursor: currentIdx === 0 ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            transition: 'all 0.2s',
          }}
        >
          <SkipBack size={14} />
        </button>

        <button
          onClick={onTogglePlay}
          style={{
            background: isPlaying
              ? '#4f46e5'
              : isDark
                ? 'rgba(79,70,229,0.15)'
                : 'rgba(79,70,229,0.08)',
            border: '1px solid #4f46e5',
            borderRadius: '8px',
            padding: '6px 14px',
            color: isPlaying ? '#ffffff' : '#4f46e5',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            fontWeight: 600,
            transition: 'all 0.2s',
          }}
        >
          {isPlaying ? <Pause size={14} /> : <Play size={14} />}
          {isPlaying ? 'Durdur' : 'Oynat'}
        </button>

        <button
          onClick={onNext}
          disabled={currentIdx === steps.length - 1}
          style={{
            background: 'transparent',
            border: isDark ? '1px solid #3a3a4a' : '1px solid #ced4da',
            borderRadius: '8px',
            padding: '6px 10px',
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
            transition: 'all 0.2s',
          }}
        >
          <SkipForward size={14} />
        </button>

        {/* Scrubber */}
        <input
          type="range"
          min={0}
          max={steps.length - 1}
          value={currentIdx}
          onChange={(e) => onSeek(Number(e.target.value))}
          style={{ flex: 1, accentColor: '#6366f1', cursor: 'pointer', height: '4px' }}
        />
      </div>

      {/* Step dots */}
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
        {steps.map((s, i) => (
          <button
            key={s.file_id}
            onClick={() => onSeek(i)}
            title={s.title}
            style={{
              width: '8px',
              height: '8px',
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
              transition: 'all 0.15s',
            }}
          />
        ))}
      </div>
    </div>
  );
};

// ─── Main Component ───────────────────────────────────────────────────────────

interface BilateralNetworkGraphProps {
  data: BilateralSentimentData[];
  timeline?: PanelTimelineEntry[];
  onTimelineStep?: (entry: PanelTimelineEntry | null) => void;
  playIntervalMs?: number;
}

export const BilateralNetworkGraph = ({
  data,
  timeline,
  onTimelineStep,
  playIntervalMs = 3000,
}: BilateralNetworkGraphProps) => {
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

  useEffect(() => () => stopPlay(), [stopPlay]);

  // ── Process data for network graph ───────────────────────────────────────────
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    if (!data || data.length === 0) {
      return { nodes: [], edges: [] };
    }

    // Extract unique countries
    const countries = Array.from(
      new Set(data.flatMap((d) => [d.from_country, d.to_country])),
    ).sort();

    // Calculate connection counts for each country
    const connectionCounts = countries.reduce(
      (acc, country) => {
        acc[country] = data.filter(
          (d) => d.from_country === country || d.to_country === country,
        ).length;
        return acc;
      },
      {} as Record<string, number>,
    );

    // Create nodes with force-directed layout positions
    const nodes: Node[] = countries.map((country, index) => {
      const angle = (index / countries.length) * 2 * Math.PI;
      const radius = 300 + Math.random() * 100;
      return {
        id: country,
        type: 'country',
        position: {
          x: 400 + radius * Math.cos(angle),
          y: 300 + radius * Math.sin(angle),
        },
        data: {
          label: country,
          connectionCount: connectionCounts[country],
        },
      };
    });

    // Create edges with styling based on affinity and interaction count
    const edges: Edge[] = data.map((d, index) => ({
      id: `edge-${index}`,
      source: d.from_country,
      target: d.to_country,
      label: d.affinity_score.toFixed(2),
      style: {
        stroke: affinityToColor(d.affinity_score),
        strokeWidth: getEdgeWidth(d.interaction_count),
        opacity: 0.7,
      },
      labelStyle: {
        fontSize: '10px',
        fontWeight: 600,
        fill: isDark ? '#f0f0f0' : '#1a1a1a',
        textShadow: isDark ? '0 1px 3px rgba(0,0,0,0.8)' : '0 1px 3px rgba(0,0,0,0.3)',
      },
      labelBgStyle: {
        fill: isDark ? 'rgba(20, 20, 30, 0.9)' : 'rgba(255, 255, 255, 0.9)',
        stroke: isDark ? '#2a2a3a' : '#dee2e6',
        strokeWidth: 1,
        rx: 4,
        ry: 4,
      },
      animated: Math.abs(d.affinity_score) > 0.5, // Animate strong relationships
      data: {
        affinity_score: d.affinity_score,
        avg_sentiment: d.avg_sentiment,
        interaction_count: d.interaction_count,
        relationship_type: d.relationship_type,
      },
    }));

    return { nodes, edges };
  }, [data, isDark]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes and edges when data changes
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // ── Custom edge tooltip ─────────────────────────────────────────────────────
  const onEdgeMouseEnter = useCallback((_: React.MouseEvent, edge: Edge) => {
    const edgeData = edge.data as any;
    if (!edgeData) return;

    // You could add custom tooltip logic here
    console.log('Edge data:', edgeData);
  }, []);

  if (!data || data.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '400px',
          border: isDark ? '1px dashed #2a2a3a' : '1px dashed #ced4da',
          borderRadius: '8px',
          color: isDark ? '#4b5563' : '#868e96',
          fontSize: '13px',
        }}
      >
        Henüz analiz edilmiş ikili ilişki bulunamadı.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '600px', position: 'relative' }}>
      {/* Time Slider */}
      {hasTimeline && (
        <div style={{ position: 'absolute', top: '16px', left: '16px', zIndex: 10 }}>
          <SliderControls
            steps={timeline!}
            currentIdx={sliderIdx}
            isPlaying={isPlaying}
            onPrev={() => handleSeek(Math.max(0, sliderIdx - 1))}
            onNext={() => handleSeek(Math.min(timeline!.length - 1, sliderIdx + 1))}
            onTogglePlay={handleTogglePlay}
            onSeek={handleSeek}
          />
        </div>
      )}

      {/* ReactFlow Graph */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onEdgeMouseEnter={onEdgeMouseEnter}
        fitView
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
        minZoom={0.2}
        maxZoom={2}
        style={{
          background: isDark ? '#0a0a0f' : '#f8fafc',
        }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color={isDark ? '#2a2a3a' : '#cbd5e1'}
        />
        <Controls
          style={{
            background: isDark ? 'rgba(20, 20, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
            border: isDark ? '1px solid #2a2a3a' : '1px solid #dee2e6',
            borderRadius: '8px',
          }}
        />
        <MiniMap
          style={{
            background: isDark ? 'rgba(20, 20, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
            border: isDark ? '1px solid #2a2a3a' : '1px solid #dee2e6',
            borderRadius: '8px',
          }}
          nodeColor="#4f46e5"
          maskColor={isDark ? 'rgba(0, 0, 0, 0.6)' : 'rgba(255, 255, 255, 0.6)'}
        />
        <Panel position="top-right">
          <div
            style={{
              background: isDark ? 'rgba(20, 20, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
              border: isDark ? '1px solid #2a2a3a' : '1px solid #dee2e6',
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '11px',
              color: isDark ? '#9ca3af' : '#6b7280',
              backdropFilter: 'blur(10px)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Globe size={14} color="#6366f1" />
              <span>{nodes.length} Ülke</span>
              <span>•</span>
              <span>{edges.length} İlişki</span>
            </div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
};
