import { useQuery } from '@tanstack/react-query';
import { Activity, Calendar, ChevronDown, Info, Palette, RefreshCw } from 'lucide-react';
import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getBilateralFlows, getSessionTimeline } from '../../../api/visualizationApi';
import type { RelationshipType } from '../../../types/visualization';
import { RELATIONSHIP_COLORS, sentimentToColor } from '../../../utils/visualizationHelpers';

interface ChordDiagramProps {
  width?: number;
  height?: number;
}

export const ChordDiagram: React.FC<ChordDiagramProps> = ({ height = 550 }) => {
  // Filters State
  const [selectedSessions, setSelectedSessions] = useState<string[]>([]);
  const [onlySignificant, setOnlySignificant] = useState<boolean>(false);
  const [colorMode, setColorMode] = useState<'relationship' | 'sentiment' | 'volume'>(
    'relationship',
  );
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState<boolean>(false);

  // Hover states
  const [activeGroupIndex, setActiveGroupIndex] = useState<number | null>(null);
  const [hoveredChordIndex, setHoveredChordIndex] = useState<number | null>(null);

  // Element refs
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: height });

  // Handle outside clicks to close session dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setSessionDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Resize Observer
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const rectWidth = entry.contentRect.width;
        setDimensions({
          width: Math.max(400, rectWidth),
          height: height,
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [height]);

  // Fetch sessions timeline
  const sessionsQuery = useQuery({
    queryKey: ['sessions-timeline'],
    queryFn: () => getSessionTimeline(),
  });

  // Fetch bilateral flows based on selected sessions
  const flowsQuery = useQuery({
    queryKey: ['chord-flows', selectedSessions],
    queryFn: () => getBilateralFlows({ sessionId: selectedSessions }),
  });

  // Filter flows for minimum interaction value if checked
  const filteredFlows = useMemo(() => {
    const data = flowsQuery.data || [];
    if (onlySignificant) {
      return data.filter((f) => f.interactionCount >= 5);
    }
    return data;
  }, [flowsQuery.data, onlySignificant]);

  // Compute Top 20 Countries, Matrix, and Dominant Relationship categories
  const { topCountries, matrix, countryDominantRel } = useMemo(() => {
    const countryInteractions: Record<string, number> = {};
    for (const f of filteredFlows) {
      countryInteractions[f.fromCountry] =
        (countryInteractions[f.fromCountry] || 0) + f.interactionCount;
      countryInteractions[f.toCountry] =
        (countryInteractions[f.toCountry] || 0) + f.interactionCount;
    }

    // Pick TOP 20 countries
    const sorted = Object.entries(countryInteractions)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([name]) => name);

    // Sort alphabetically for consistent circular placement
    sorted.sort();

    // Calculate dominant relationship category for each top country
    const dominantMap: Record<string, RelationshipType> = {};
    for (const country of sorted) {
      const countryFlows = filteredFlows.filter(
        (f) => f.fromCountry === country || f.toCountry === country,
      );
      const counts: Record<RelationshipType, number> = {
        ALLY: 0,
        PARTNER: 0,
        NEUTRAL: 0,
        CAUTIOUS: 0,
        ADVERSARY: 0,
      };
      for (const f of countryFlows) {
        counts[f.relationshipType] = (counts[f.relationshipType] || 0) + f.interactionCount;
      }
      let dominant: RelationshipType = 'NEUTRAL';
      let maxVal = -1;
      for (const type of Object.keys(counts) as RelationshipType[]) {
        if (counts[type] > maxVal) {
          maxVal = counts[type];
          dominant = type;
        }
      }
      dominantMap[country] = dominant;
    }

    // Build square matrix (N x N)
    const n = sorted.length;
    const mat = Array.from({ length: n }, () => Array(n).fill(0));

    // Populate matrix
    for (const flow of filteredFlows) {
      const i = sorted.indexOf(flow.fromCountry);
      const j = sorted.indexOf(flow.toCountry);
      if (i !== -1 && j !== -1) {
        mat[i][j] = flow.interactionCount;
      }
    }

    return {
      topCountries: sorted,
      matrix: mat,
      countryDominantRel: dominantMap,
    };
  }, [filteredFlows]);

  // Find the flow linking two country indices
  const findFlow = useCallback(
    (idxA: number, idxB: number) => {
      const cA = topCountries[idxA];
      const cB = topCountries[idxB];
      return filteredFlows.find(
        (f) =>
          (f.fromCountry === cA && f.toCountry === cB) ||
          (f.fromCountry === cB && f.toCountry === cA),
      );
    },
    [topCountries, filteredFlows],
  );

  // D3 Chord layout calculations
  const chordLayout = useMemo(() => {
    return d3.chord().padAngle(0.04).sortSubgroups(d3.descending);
  }, []);

  const chords = useMemo<d3.Chords>(() => {
    if (matrix.length === 0) return [] as unknown as d3.Chords;
    try {
      return chordLayout(matrix);
    } catch (e) {
      return [] as unknown as d3.Chords;
    }
  }, [matrix, chordLayout]);

  // Size constants
  const outerRadius = useMemo(() => {
    return Math.max(120, Math.min(dimensions.width, dimensions.height) / 2 - 80);
  }, [dimensions]);

  const innerRadius = outerRadius * 0.88;

  // D3 path generators
  const arcGenerator = useMemo(() => {
    return d3.arc<unknown, d3.ChordGroup>().innerRadius(innerRadius).outerRadius(outerRadius);
  }, [innerRadius, outerRadius]);

  const ribbonGenerator = useMemo(() => {
    return d3.ribbon<unknown, d3.Chord>().radius(innerRadius);
  }, [innerRadius]);

  // Color scale for volume density mode
  const maxInteractions = useMemo(() => {
    if (filteredFlows.length === 0) return 1;
    return Math.max(...filteredFlows.map((f) => f.interactionCount), 1);
  }, [filteredFlows]);

  const getVolumeColor = (count: number) => {
    const ratio = Math.min(1, count / maxInteractions);
    // Indigo to magenta/pink HSL glow
    const hue = 220 + ratio * 100;
    return `hsl(${hue}, 80%, 60%)`;
  };

  // Determine ribbon colors based on selected mode
  const getRibbonColor = (sourceIdx: number, targetIdx: number) => {
    const flow = findFlow(sourceIdx, targetIdx);
    if (!flow) return '#334155'; // Default fallback

    if (colorMode === 'sentiment') {
      return sentimentToColor(flow.avgSentiment);
    }
    if (colorMode === 'volume') {
      return getVolumeColor(flow.interactionCount);
    }
    return RELATIONSHIP_COLORS[flow.relationshipType] || '#6b7280';
  };

  // Check if a session is selected
  const handleSessionToggle = (id: string) => {
    if (selectedSessions.includes(id)) {
      setSelectedSessions(selectedSessions.filter((s) => s !== id));
    } else {
      setSelectedSessions([...selectedSessions, id]);
    }
  };

  // Text shortener (max 12 chars)
  const truncateCountry = (name: string) => {
    if (name.length > 12) {
      return `${name.substring(0, 10)}..`;
    }
    return name;
  };

  // Stats detail model for center info overlay
  const centerStats = useMemo(() => {
    // 1. Ribbon hovered details
    if (hoveredChordIndex !== null && chords[hoveredChordIndex]) {
      const chord = chords[hoveredChordIndex];
      const s = topCountries[chord.source.index];
      const t = topCountries[chord.target.index];
      const flow = findFlow(chord.source.index, chord.target.index);
      if (flow) {
        return {
          title: 'İLİŞKİ AKIŞI',
          lines: [
            `${truncateCountry(s)} ➔ ${truncateCountry(t)}`,
            `Hacim: ${flow.interactionCount} segment`,
            `Sentiment: ${flow.avgSentiment >= 0 ? '+' : ''}${flow.avgSentiment.toFixed(2)}`,
            `Kategori: ${flow.relationshipType}`,
          ],
        };
      }
    }

    // 2. Country slice hovered details
    if (activeGroupIndex !== null && topCountries[activeGroupIndex]) {
      const country = topCountries[activeGroupIndex];
      const countryFlows = filteredFlows.filter(
        (f) => f.fromCountry === country || f.toCountry === country,
      );

      // Aggregate targets
      const connectionsList = countryFlows
        .map((f) => {
          const target = f.fromCountry === country ? f.toCountry : f.fromCountry;
          return {
            target: truncateCountry(target),
            count: f.interactionCount,
            type: f.relationshipType,
          };
        })
        .sort((a, b) => b.count - a.count)
        .slice(0, 4);

      const lines = connectionsList.map(
        (c) => ` ${c.count.toString().padStart(2, ' ')} ➔ ${c.target} (${c.type.substring(0, 4)})`,
      );

      const totalVol = countryFlows.reduce((sum, f) => sum + f.interactionCount, 0);

      return {
        title: truncateCountry(country).toUpperCase(),
        lines: [
          `Toplam Hacim: ${totalVol}`,
          `Dominant: ${countryDominantRel[country]}`,
          'İlişkiler:',
          ...lines,
        ],
      };
    }

    // 3. Default state
    return {
      title: 'DİPLOMATİK AKIŞ',
      lines: [
        'Bir ülke dilimi veya',
        'bağlantı şeridinin',
        'üzerine gelerek',
        'akışları inceleyin.',
      ],
    };
  }, [
    activeGroupIndex,
    hoveredChordIndex,
    chords,
    topCountries,
    filteredFlows,
    countryDominantRel,
    findFlow,
  ]);

  return (
    <div
      ref={containerRef}
      className="w-full flex flex-col bg-carbon-950 border border-carbon-550 min-h-[550px] p-5 relative overflow-hidden font-mono select-none"
    >
      {/* Filters Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-carbon-800 z-30 select-text">
        <div className="flex flex-wrap items-center gap-4 text-[10px]">
          {/* Session Dropdown Selector */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
              className="flex items-center gap-2 bg-carbon-900 border border-carbon-700 px-3 py-1.5 text-carbon-200 hover:text-carbon-50 hover:bg-carbon-800 transition-colors"
            >
              <Calendar className="w-3.5 h-3.5 text-indigo-400" />
              <span>
                {selectedSessions.length === 0
                  ? 'Tüm Oturumlar'
                  : `Oturum (${selectedSessions.length})`}
              </span>
              <ChevronDown className="w-3 h-3 text-carbon-400" />
            </button>
            {sessionDropdownOpen && (
              <div className="absolute top-full left-0 mt-1.5 bg-carbon-900 border border-carbon-700 p-2.5 w-60 shadow-2xl z-50 flex flex-col gap-2">
                {sessionsQuery.isPending && (
                  <div className="text-carbon-400 py-1 text-2xs animate-pulse">Yükleniyor...</div>
                )}
                {sessionsQuery.data?.map((session) => (
                  <label
                    key={session.sessionId}
                    className="flex items-center gap-2 cursor-pointer text-carbon-300 hover:text-carbon-100 py-0.5"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSessions.includes(session.sessionId)}
                      onChange={() => handleSessionToggle(session.sessionId)}
                      className="w-3.5 h-3.5 bg-carbon-950 border border-carbon-700 text-indigo-500 rounded focus:ring-0 focus:ring-offset-0 cursor-pointer"
                    />
                    <span className="truncate">{session.sessionLabel}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Significance filter */}
          <label className="flex items-center gap-2 cursor-pointer text-carbon-300 hover:text-carbon-100 py-1">
            <input
              type="checkbox"
              checked={onlySignificant}
              onChange={(e) => setOnlySignificant(e.target.checked)}
              className="w-3.5 h-3.5 bg-carbon-900 border border-carbon-700 text-indigo-500 rounded focus:ring-0 focus:ring-offset-0 cursor-pointer"
            />
            <span>Sadece Anlamlı Bağlantılar (≥ 5 etkileşim)</span>
          </label>
        </div>

        {/* Color Mode toggles */}
        <div className="flex items-center gap-1.5 bg-carbon-900 border border-carbon-800 p-1 text-[9px] font-bold">
          <span className="text-carbon-400 px-1.5 flex items-center gap-1">
            <Palette className="w-3 h-3 text-indigo-400" /> RENK MODU:
          </span>
          <button
            onClick={() => setColorMode('relationship')}
            className={`px-2.5 py-1 transition-all ${
              colorMode === 'relationship'
                ? 'bg-indigo-950 text-indigo-400 border border-indigo-800/40'
                : 'text-carbon-400 hover:text-carbon-200'
            }`}
          >
            İlişki Tipi
          </button>
          <button
            onClick={() => setColorMode('sentiment')}
            className={`px-2.5 py-1 transition-all ${
              colorMode === 'sentiment'
                ? 'bg-indigo-950 text-indigo-400 border border-indigo-800/40'
                : 'text-carbon-400 hover:text-carbon-200'
            }`}
          >
            Sentiment
          </button>
          <button
            onClick={() => setColorMode('volume')}
            className={`px-2.5 py-1 transition-all ${
              colorMode === 'volume'
                ? 'bg-indigo-950 text-indigo-400 border border-indigo-800/40'
                : 'text-carbon-400 hover:text-carbon-200'
            }`}
          >
            Etkileşim Hacmi
          </button>
        </div>
      </div>

      {/* Main chord visual content wrapper */}
      <div className="flex-1 relative flex items-center justify-center min-h-[460px]">
        {flowsQuery.isPending && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-carbon-950/60 z-20">
            <RefreshCw className="w-6 h-6 text-indigo-400 animate-spin" />
            <span className="text-xs text-carbon-400">İlişki akış verileri yükleniyor...</span>
          </div>
        )}

        {!flowsQuery.isPending && topCountries.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-carbon-950 text-carbon-400 text-xs">
            <Info className="w-6 h-6 text-carbon-600" />
            <span>Seçili kriterlere uygun etkileşim verisi bulunamadı.</span>
          </div>
        )}

        {topCountries.length > 0 && (
          <>
            {/* SVG Chord Diagram render layout */}
            <svg width={dimensions.width} height={dimensions.height} className="overflow-visible">
              <g transform={`translate(${dimensions.width / 2}, ${dimensions.height / 2})`}>
                {/* 1. Ribbon connectors (Chords) */}
                <g className="chords-ribbons">
                  {chords.map((chord, idx) => {
                    const isSourceActive =
                      activeGroupIndex === null ||
                      chord.source.index === activeGroupIndex ||
                      chord.target.index === activeGroupIndex;

                    const isChordActive = hoveredChordIndex === null || idx === hoveredChordIndex;

                    // Opacity calculations: 0.65 -> 0.9 (hover) -> 0.1 (other)
                    let opacity = 0.65;
                    if (hoveredChordIndex !== null) {
                      opacity = isChordActive ? 0.95 : 0.08;
                    } else if (activeGroupIndex !== null) {
                      opacity = isSourceActive ? 0.85 : 0.08;
                    }

                    const ribbonColor = getRibbonColor(chord.source.index, chord.target.index);

                    return (
                      <path
                        key={`chord-${idx}`}
                        d={(ribbonGenerator(chord) as unknown as string) || undefined}
                        fill={ribbonColor}
                        fillOpacity={opacity}
                        stroke={d3.rgb(ribbonColor).darker(0.5).toString()}
                        strokeWidth={0.5}
                        strokeOpacity={opacity * 0.7}
                        className="transition-all duration-200 cursor-pointer"
                        onMouseEnter={() => setHoveredChordIndex(idx)}
                        onMouseLeave={() => setHoveredChordIndex(null)}
                      />
                    );
                  })}
                </g>

                {/* 2. Outer Circle Country Arcs */}
                <g className="country-arcs">
                  {chords.groups.map((group) => {
                    const country = topCountries[group.index];
                    const dominantType = countryDominantRel[country] || 'NEUTRAL';
                    const arcColor = RELATIONSHIP_COLORS[dominantType];

                    const isArcActive =
                      activeGroupIndex === null || group.index === activeGroupIndex;

                    const isConnected =
                      hoveredChordIndex !== null &&
                      chords[hoveredChordIndex] &&
                      (chords[hoveredChordIndex].source.index === group.index ||
                        chords[hoveredChordIndex].target.index === group.index);

                    // Hover opacity logic for arc segments
                    let opacity = 1.0;
                    if (hoveredChordIndex !== null) {
                      opacity = isConnected ? 1.0 : 0.25;
                    } else if (activeGroupIndex !== null) {
                      opacity = isArcActive ? 1.0 : 0.25;
                    }

                    // Calculate label rotation angle & offsets
                    const angle = (group.startAngle + group.endAngle) / 2;
                    const rotate = (angle * 180) / Math.PI - 90;
                    const isBottomHalf = angle > Math.PI;
                    const labelRotate = isBottomHalf ? rotate + 180 : rotate;

                    const translateDistance = outerRadius + 14;
                    const labelX = isBottomHalf ? -translateDistance : translateDistance;

                    return (
                      <g key={`group-${group.index}`}>
                        {/* Outer Arc Path */}
                        <path
                          d={arcGenerator(group) || undefined}
                          fill={arcColor}
                          fillOpacity={opacity}
                          stroke={d3.rgb(arcColor).darker(0.6).toString()}
                          strokeWidth={1}
                          className="transition-all duration-150 cursor-pointer"
                          onMouseEnter={() => setActiveGroupIndex(group.index)}
                          onMouseLeave={() => setActiveGroupIndex(null)}
                        />

                        {/* Radial Text Labels */}
                        <text
                          transform={`rotate(${labelRotate})`}
                          x={labelX}
                          dy=".35em"
                          textAnchor={isBottomHalf ? 'end' : 'start'}
                          fill={isArcActive && hoveredChordIndex === null ? '#f5f5f5' : '#8a8a8a'}
                          fontSize="8px"
                          fontWeight={group.index === activeGroupIndex ? 'bold' : 'normal'}
                          className="pointer-events-none select-none font-mono tracking-wider transition-colors duration-150"
                        >
                          {truncateCountry(country)}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </g>
            </svg>

            {/* Center Overlay Retro Information Stats Card */}
            <div
              className="absolute bg-carbon-950/95 border border-carbon-800 w-[185px] h-[185px] rounded-full flex flex-col items-center justify-center p-4 text-center pointer-events-none select-none z-10"
              style={{
                transform: 'translate(-50%, -50%)',
                top: '50%',
                left: '50%',
              }}
            >
              <div className="font-mono text-[8px] text-carbon-200 leading-tight w-full overflow-hidden">
                {/* Top Border */}
                <div className="text-carbon-500">╔═══════════════════╗</div>
                {/* Header */}
                <div className="text-carbon-50 font-bold uppercase tracking-wider truncate px-1">
                  ║ {centerStats.title.padEnd(17, ' ').substring(0, 17)} ║
                </div>
                <div className="text-carbon-500">╟───────────────────╢</div>
                {/* Body rows */}
                {centerStats.lines.map((line, idx) => (
                  <div key={idx} className="truncate text-left text-carbon-300 font-mono pl-2">
                    ║ {line.padEnd(17, ' ').substring(0, 17)} ║
                  </div>
                ))}
                {/* Fill empty spaces to maintain 6-line card dimensions */}
                {Array.from({ length: Math.max(0, 5 - centerStats.lines.length) }).map((_, idx) => (
                  <div key={`empty-${idx}`} className="text-left font-mono pl-2">
                    ║ {''.padEnd(17, ' ')} ║
                  </div>
                ))}
                {/* Bottom Border */}
                <div className="text-carbon-500">╚═══════════════════╝</div>
              </div>
            </div>
          </>
        )}
      </div>
      {/* Bottom description info */}
      <div className="border-t border-carbon-800 pt-3 flex items-center gap-2 text-carbon-400 text-[9px] mt-2">
        <Activity className="w-3.5 h-3.5 text-indigo-400" />
        <span>
          Chord diyagramı en çok etkileşime giren 20 ülkeyi listeler. Dış halka dilimleri ülkeleri,
          iç şeritler ise o ülkeler arasındaki diplomatik akış hacimlerini temsil eder.
        </span>
      </div>
    </div>
  );
};
