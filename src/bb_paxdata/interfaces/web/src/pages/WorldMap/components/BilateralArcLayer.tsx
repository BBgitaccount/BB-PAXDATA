// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/BilateralArcLayer.tsx

import { geoCentroid } from 'd3-geo';
import type { GeoProjection } from 'd3-geo';
import React, { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { isoNumericToAlpha3 } from '../../../data/isoNumericToAlpha3';
import type { BilateralFlow, RelationshipType } from '../../../types/visualization';

// Extended interface to support alternative snake_case fields that might be passed from some endpoints
export interface ExtendedBilateralFlow extends BilateralFlow {
  from_country?: string;
  to_country?: string;
  from_iso3?: string | null;
  to_iso3?: string | null;
  interaction_count?: number;
  avg_sentiment?: number;
  affinity_score?: number;
  relationship_type?: string;
}

export interface MapNode {
  country_code?: string;
  country_name?: string;
  isoAlpha3?: string;
  country?: string;
  longitude?: number;
  latitude?: number;
}

interface BilateralArcLayerProps {
  flows: ExtendedBilateralFlow[];
  projection: GeoProjection;
  highlightedCountry: string | null;
  visibleTypes: RelationshipType[];
  showAllFlows: boolean;
  onArcHover: (flow: BilateralFlow | null) => void;
  geographies?: unknown[];
  nodes?: MapNode[];
}

// Arc Width mapping based on interaction count
const arcWidth = (count: number): number => {
  if (count >= 30) return 3.5;
  if (count >= 15) return 2.5;
  if (count >= 7) return 1.8;
  return 1.2;
};

// Colors mapping
const RELATIONSHIP_STYLES: Record<
  RelationshipType,
  { color: string; baseWidth: number; opacity: number; dashArray?: string }
> = {
  ALLY: { color: '#10b981', baseWidth: 2.5, opacity: 0.8 },
  PARTNER: { color: '#3b82f6', baseWidth: 1.5, opacity: 0.7 },
  NEUTRAL: { color: '#475569', baseWidth: 1.0, opacity: 0.4 },
  CAUTIOUS: { color: '#f59e0b', baseWidth: 2.0, opacity: 0.85 },
  ADVERSARY: {
    color: '#ef4444',
    baseWidth: 3.0,
    opacity: 0.9,
    dashArray: '6,3',
  },
};

// Resolver helper to get country center (coordinates: [lon, lat])
const getCountryCoordinates = (
  countryCode: string | null,
  geographies?: unknown[],
  nodes?: MapNode[],
): [number, number] | null => {
  if (!countryCode) return null;
  const upperCode = countryCode.toUpperCase();

  // 1. Try to find in geographies using d3.geoCentroid
  if (geographies) {
    const geo = geographies.find((g) => {
      if (typeof g !== 'object' || g === null) return false;
      const feature = g as { id?: string | number };
      const id = feature.id;
      if (id === undefined) return false;
      const alpha3 =
        typeof id === 'number' || !Number.isNaN(Number(id)) ? isoNumericToAlpha3[Number(id)] : id;
      return alpha3 && alpha3.toUpperCase() === upperCode;
    });
    if (geo) {
      try {
        const c = geoCentroid(geo as Parameters<typeof geoCentroid>[0]);
        if (c && !Number.isNaN(c[0]) && !Number.isNaN(c[1])) {
          return c;
        }
      } catch {
        // ignore
      }
    }
  }

  // 2. Try to find in nodes list
  if (nodes) {
    const node = nodes.find(
      (n) =>
        (n.country_code && n.country_code.toUpperCase() === upperCode) ||
        (n.isoAlpha3 && n.isoAlpha3.toUpperCase() === upperCode) ||
        (n.country && n.country.toUpperCase() === upperCode),
    );
    if (node && node.longitude !== undefined && node.latitude !== undefined) {
      return [node.longitude, node.latitude];
    }
  }

  // 3. Static centroids fallback for major/popular countries
  const staticCentroids: Record<string, [number, number]> = {
    USA: [-95.7129, 37.0902],
    TUR: [35.2433, 38.9637],
    RUS: [105.3188, 61.524],
    CHN: [104.1954, 35.8617],
    GBR: [-1.1743, 54.2379],
    FRA: [2.2137, 46.2276],
    DEU: [10.4515, 51.1657],
    JPN: [138.2529, 36.2048],
    BRA: [-51.9253, -14.235],
    IND: [78.9629, 20.5937],
    AUS: [133.7751, -25.2744],
    CAN: [-106.3468, 56.1304],
    ZAF: [25.0479, -30.5595],
    IRN: [53.688, 32.4279],
    SAU: [45.0792, 23.8859],
    EGY: [30.8025, 26.8206],
    UKR: [31.1656, 48.3794],
    POL: [19.1451, 51.9192],
    GRC: [21.8243, 39.0742],
    ITA: [12.5674, 41.8719],
    ESP: [-3.7492, 40.4637],
    SWE: [18.6435, 60.1282],
    NOR: [8.4689, 60.472],
    FIN: [25.7482, 61.9241],
    KOR: [127.7669, 35.9078],
    PAK: [69.3451, 30.3753],
    ISR: [34.8516, 31.0461],
    SYR: [38.9968, 34.8021],
    IRQ: [43.6793, 33.2232],
    AFG: [67.7099, 33.9391],
    AZE: [47.5769, 40.1431],
    ARM: [45.0382, 40.0691],
    GEO: [43.3569, 42.3154],
  };

  return staticCentroids[upperCode] || null;
};

// Memoized Single Arc Component for high FPS performance
interface BilateralArcProps {
  flow: ExtendedBilateralFlow;
  fromCoords: [number, number];
  toCoords: [number, number];
  projection: GeoProjection;
  highlightedCountry: string | null;
  isSelectedCountryRelated: boolean;
  styleConfig: (typeof RELATIONSHIP_STYLES)[RelationshipType];
  onMouseEnter: (e: React.MouseEvent, flow: ExtendedBilateralFlow) => void;
  onMouseMove: (e: React.MouseEvent) => void;
  onMouseLeave: () => void;
}

const BilateralArc: React.FC<BilateralArcProps> = React.memo(
  ({
    flow,
    fromCoords,
    toCoords,
    projection,
    highlightedCountry,
    isSelectedCountryRelated,
    styleConfig,
    onMouseEnter,
    onMouseMove,
    onMouseLeave,
  }) => {
    // Interaction states
    const [isHovered, setIsHovered] = useState(false);

    // Project geographic coordinates into SVG space coordinates
    const p0 = projection(fromCoords);
    const p2 = projection(toCoords);

    // If coordinates are clipped by projection (e.g., backside of 3D orthographic globe), return null
    if (!p0 || !p2) return null;

    const [x0, y0] = p0;
    const [x2, y2] = p2;

    const dx = x2 - x0;
    const dy = y2 - y0;
    const distance = Math.sqrt(dx * dx + dy * dy);

    // Filter out extremely close countries to prevent messy SVG rendering
    if (distance < 4) return null;

    const midX = (x0 + x2) / 2;
    const midY = (y0 + y2) / 2;

    // Curved SVG Arc Geometry with 30% height control point.
    // Clockwise perpendicular offset handles USA -> TUR and TUR -> USA separation cleanly.
    const offsetRatio = 0.3;
    const ctrlX = midX - (dy / distance) * (distance * offsetRatio);
    const ctrlY = midY + (dx / distance) * (distance * offsetRatio);

    const d = `M ${x0} ${y0} Q ${ctrlX} ${ctrlY} ${x2} ${y2}`;

    // Get stroke width based on interaction count
    const count =
      flow.interactionCount !== undefined ? flow.interactionCount : flow.interaction_count || 1;
    const baseStrokeWidth = arcWidth(count);

    // Set opacity based on highlightedCountry logic:
    // If a country is highlighted, keep related arcs visible (opacity 1.0 / base) and fade other arcs (opacity 0.1)
    let opacity = isHovered ? 1.0 : styleConfig.opacity;
    if (highlightedCountry) {
      opacity = isSelectedCountryRelated ? (isHovered ? 1.0 : 0.9) : 0.1;
    }

    const strokeWidth = isHovered ? baseStrokeWidth * 2 : baseStrokeWidth;

    // Determine animation parameters
    const relType = (flow.relationshipType ||
      flow.relationship_type ||
      'NEUTRAL') as RelationshipType;
    const hasAnimation = relType !== 'NEUTRAL';
    const animationClass =
      relType === 'ALLY' || relType === 'PARTNER' ? 'arc-flow-slow' : 'arc-flow-fast';

    // Slightly lighter/brighter color for flowing animated dots
    const glowColor =
      relType === 'ALLY'
        ? '#34d399'
        : relType === 'PARTNER'
          ? '#60a5fa'
          : relType === 'CAUTIOUS'
            ? '#fbbf24'
            : '#f87171';

    return (
      <g>
        {/* Invisible thicker path for easier mouse hover interaction */}
        {/* biome-ignore lint/a11y/useSemanticElements: SVG path cannot be replaced with semantic HTML <button> */}
        <path
          d={d}
          fill="none"
          stroke="transparent"
          strokeWidth={Math.max(12, strokeWidth * 3)}
          className="cursor-pointer"
          role="button"
          tabIndex={-1}
          aria-label="Arc relationship flow"
          onMouseEnter={(e) => {
            setIsHovered(true);
            onMouseEnter(e, flow);
          }}
          onMouseMove={onMouseMove}
          onMouseLeave={() => {
            setIsHovered(false);
            onMouseLeave();
          }}
        />

        {/* Base Static/Relationship Path */}
        <path
          d={d}
          fill="none"
          stroke={styleConfig.color}
          strokeWidth={strokeWidth}
          strokeOpacity={opacity}
          strokeDasharray={styleConfig.dashArray || 'none'}
          className="pointer-events-none transition-all duration-200"
        />

        {/* Directional Animated Dash Path Overlay */}
        {hasAnimation && (
          <path
            d={d}
            fill="none"
            stroke={glowColor}
            strokeWidth={strokeWidth}
            strokeOpacity={opacity * 0.9}
            strokeLinecap="round"
            className={`${animationClass} pointer-events-none`}
          />
        )}
      </g>
    );
  },
);

BilateralArc.displayName = 'BilateralArc';

export const BilateralArcLayer: React.FC<BilateralArcLayerProps> = ({
  flows,
  projection,
  highlightedCountry,
  visibleTypes,
  showAllFlows,
  onArcHover,
  geographies,
  nodes,
}) => {
  const [hoveredFlow, setHoveredFlow] = useState<ExtendedBilateralFlow | null>(null);
  const [tooltipCoords, setTooltipCoords] = useState<{
    x: number;
    y: number;
  } | null>(null);

  // Dynamically resolve SVG Viewport dimensions from projection translation to support clean clipping
  const [width, height] = useMemo(() => {
    const translate = projection.translate ? projection.translate() : [400, 300];
    return [translate[0] * 2, translate[1] * 2];
  }, [projection]);

  // Filters significant and type-visible flows
  const processedFlows = useMemo(() => {
    return flows.filter((flow) => {
      const from = flow.fromCountry || flow.from_country;
      const to = flow.toCountry || flow.to_country;
      if (!from || !to) return false;

      // Filter by RelationshipType
      const relType = (flow.relationshipType ||
        flow.relationship_type ||
        'NEUTRAL') as RelationshipType;
      if (!visibleTypes.includes(relType)) return false;

      // Filter by interaction count (significant flows >= 5 by default)
      const count =
        flow.interactionCount !== undefined ? flow.interactionCount : flow.interaction_count || 0;
      if (!showAllFlows && count < 5) return false;

      return true;
    });
  }, [flows, visibleTypes, showAllFlows]);

  // Hide neutral flows if total flow counts exceed 50 for top-tier render performance
  const shouldHideNeutralByDefault = processedFlows.length > 50;

  // Separate non-neutral and neutral flows into distinct groups
  const { neutralFlows, activeFlows } = useMemo(() => {
    const neutral: ExtendedBilateralFlow[] = [];
    const active: ExtendedBilateralFlow[] = [];

    processedFlows.forEach((flow) => {
      const relType = (flow.relationshipType ||
        flow.relationship_type ||
        'NEUTRAL') as RelationshipType;
      if (relType === 'NEUTRAL') {
        neutral.push(flow);
      } else {
        active.push(flow);
      }
    });

    return { neutralFlows: neutral, activeFlows: active };
  }, [processedFlows]);

  const handleMouseEnter = (e: React.MouseEvent, flow: ExtendedBilateralFlow) => {
    setHoveredFlow(flow);
    setTooltipCoords({ x: e.clientX, y: e.clientY });
    onArcHover(flow);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    setTooltipCoords({ x: e.clientX, y: e.clientY });
  };

  const handleMouseLeave = () => {
    setHoveredFlow(null);
    setTooltipCoords(null);
    onArcHover(null);
  };

  // Helper to map country ISO3 keys to actual human-readable country names
  const getCountryName = (codeOrName: string | undefined) => {
    if (!codeOrName) return '';
    if (nodes) {
      const found = nodes.find(
        (n) =>
          (n.country_code && n.country_code.toLowerCase() === codeOrName.toLowerCase()) ||
          (n.isoAlpha3 && n.isoAlpha3.toLowerCase() === codeOrName.toLowerCase()) ||
          (n.country && n.country.toLowerCase() === codeOrName.toLowerCase()),
      );
      if (found) return found.country_name || found.country;
    }
    return codeOrName;
  };

  return (
    <>
      {/* Inline styles for custom GPU-accelerated moving dot animations */}
      <style
        // biome-ignore lint/security/noDangerouslySetInnerHtml: Inline style injection is safe here as contents are static CSS rules
        dangerouslySetInnerHTML={{
          __html: `
        @keyframes dashFlow {
          from {
            stroke-dashoffset: 80;
          }
          to {
            stroke-dashoffset: 0;
          }
        }
        .arc-flow-slow {
          stroke-dasharray: 6, 45;
          animation: dashFlow 3s linear infinite;
        }
        .arc-flow-fast {
          stroke-dasharray: 6, 25;
          animation: dashFlow 1.2s linear infinite;
        }
      `,
        }}
      />

      {/* SVG clipPath setup for clean viewport boundary virtualization */}
      <defs>
        <clipPath id="map-viewport-clip">
          <rect x={0} y={0} width={width} height={height} />
        </clipPath>
      </defs>

      <g clipPath="url(#map-viewport-clip)">
        {/* NEUTRAL Arc Layer with static separate rendering and global toggle opacity */}
        {!shouldHideNeutralByDefault && neutralFlows.length > 0 && (
          <g
            style={{
              opacity: 0.45,
              transition: 'opacity 0.25s ease-in-out',
            }}
          >
            {neutralFlows.map((flow) => {
              const from = flow.fromCountry || flow.from_country || null;
              const to = flow.toCountry || flow.to_country || null;
              const fromCoords = getCountryCoordinates(from, geographies, nodes);
              const toCoords = getCountryCoordinates(to, geographies, nodes);

              if (!fromCoords || !toCoords) return null;

              const isSelectedCountryRelated =
                highlightedCountry !== null &&
                (from === highlightedCountry || to === highlightedCountry);

              return (
                <BilateralArc
                  key={`neutral-arc-${from}-${to}`}
                  flow={flow}
                  fromCoords={fromCoords}
                  toCoords={toCoords}
                  projection={projection}
                  highlightedCountry={highlightedCountry}
                  isSelectedCountryRelated={isSelectedCountryRelated}
                  styleConfig={RELATIONSHIP_STYLES.NEUTRAL}
                  onMouseEnter={handleMouseEnter}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={handleMouseLeave}
                />
              );
            })}
          </g>
        )}

        {/* ALLY, PARTNER, CAUTIOUS, ADVERSARY Active Arc Layer */}
        {activeFlows.map((flow) => {
          const from = flow.fromCountry || flow.from_country || null;
          const to = flow.toCountry || flow.to_country || null;
          const fromCoords = getCountryCoordinates(from, geographies, nodes);
          const toCoords = getCountryCoordinates(to, geographies, nodes);

          if (!fromCoords || !toCoords) return null;

          const relType = (flow.relationshipType ||
            flow.relationship_type ||
            'NEUTRAL') as RelationshipType;
          const styleConfig = RELATIONSHIP_STYLES[relType] || RELATIONSHIP_STYLES.NEUTRAL;

          const isSelectedCountryRelated =
            highlightedCountry !== null &&
            (from === highlightedCountry || to === highlightedCountry);

          return (
            <BilateralArc
              key={`active-arc-${from}-${to}`}
              flow={flow}
              fromCoords={fromCoords}
              toCoords={toCoords}
              projection={projection}
              highlightedCountry={highlightedCountry}
              isSelectedCountryRelated={isSelectedCountryRelated}
              styleConfig={styleConfig}
              onMouseEnter={handleMouseEnter}
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
            />
          );
        })}
      </g>

      {/* Render absolute positioned micro tooltip portal */}
      {hoveredFlow &&
        tooltipCoords &&
        createPortal(
          <div
            className="fixed z-50 pointer-events-none rounded-none border border-carbon-600 bg-carbon-950/95 p-3.5 shadow-2xl backdrop-blur-md transition-all duration-75 text-[11px]"
            style={{
              top: tooltipCoords.y,
              left: tooltipCoords.x,
              transform: 'translate(15px, 15px)',
              fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
              lineHeight: '1.4',
              color: '#cbd5e1',
            }}
          >
            <div className="font-bold text-white text-xs mb-1 flex items-center gap-1.5">
              <span>{getCountryName(hoveredFlow.fromCountry || hoveredFlow.from_country)}</span>
              <span className="text-carbon-500">→</span>
              <span>{getCountryName(hoveredFlow.toCountry || hoveredFlow.to_country)}</span>
            </div>
            <div className="border-t border-carbon-800 my-1.5" />
            <div className="flex items-center gap-1.5">
              <span>
                {hoveredFlow.interactionCount !== undefined
                  ? hoveredFlow.interactionCount
                  : hoveredFlow.interaction_count || 0}{' '}
                etkileşim
              </span>
              <span className="text-carbon-700">|</span>
              <span
                style={{
                  color:
                    RELATIONSHIP_STYLES[
                      (hoveredFlow.relationshipType ||
                        hoveredFlow.relationship_type ||
                        'NEUTRAL') as RelationshipType
                    ]?.color || '#94a3b8',
                  fontWeight: 'bold',
                }}
              >
                {hoveredFlow.relationshipType || hoveredFlow.relationship_type || 'NEUTRAL'}
              </span>
            </div>
            <div className="text-carbon-400 mt-0.5">
              Sentiment:{' '}
              <span
                className={
                  (hoveredFlow.avgSentiment !== undefined
                    ? hoveredFlow.avgSentiment
                    : hoveredFlow.avg_sentiment || 0) >= 0
                    ? 'text-emerald-400 font-semibold'
                    : 'text-red-400 font-semibold'
                }
              >
                {(hoveredFlow.avgSentiment !== undefined
                  ? hoveredFlow.avgSentiment
                  : hoveredFlow.avg_sentiment || 0) >= 0
                  ? '+'
                  : ''}
                {(hoveredFlow.avgSentiment !== undefined
                  ? hoveredFlow.avgSentiment
                  : hoveredFlow.avg_sentiment || 0
                ).toFixed(2)}
              </span>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
};
