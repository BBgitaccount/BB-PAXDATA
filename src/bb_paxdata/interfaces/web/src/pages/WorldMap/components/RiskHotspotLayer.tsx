// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/RiskHotspotLayer.tsx

import type { GeoProjection } from 'd3-geo';
import { geoCentroid } from 'd3-geo';
import { AlertTriangle, Shield } from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import type { BilateralFlow, CountryNode } from '../../../types/visualization';
import { getAlpha3FromNumeric } from '../../../utils/visualizationHelpers';

interface RiskHotspotLayerProps {
  nodes: CountryNode[];
  flows: BilateralFlow[];
  projection: GeoProjection;
  geographies?: unknown[];
  visible?: boolean;
  highlightedCountry?: string | null;
}

interface CountryRiskData {
  countryCode: string;
  riskScore: number;
  adversaryCount: number;
  cautiousCount: number;
  accusationRatio: number;
  sentimentPenalty: number;
  coordinates: [number, number] | null;
}

// Helper to get country coordinates
const getCountryCoordinates = (
  countryCode: string,
  geographies?: unknown[],
  nodes?: CountryNode[],
): [number, number] | null => {
  if (!countryCode) return null;
  const upperCode = countryCode.toUpperCase();

  // Try geographies first
  if (geographies) {
    const geo = geographies.find((g) => {
      if (typeof g !== 'object' || g === null) return false;
      const feature = g as { id?: string | number };
      const id = feature.id;
      if (id === undefined) return false;
      const alpha3 = getAlpha3FromNumeric(id);
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

  // Try nodes
  if (nodes) {
    nodes.find(
      (n) =>
        (n.country && n.country.toUpperCase() === upperCode) ||
        (n.isoAlpha3 && n.isoAlpha3.toUpperCase() === upperCode),
    );
    // For now, we don't have lat/lon in CountryNode, so skip
  }

  // Static centroids fallback
  const staticCentroids: Record<string, [number, number]> = {
    IRN: [53.688, 32.4279],
    LBY: [17.2283, 26.3351],
    RUS: [105.3188, 61.524],
    SYR: [38.9968, 34.8021],
    IRQ: [43.6793, 33.2232],
    ISR: [34.8516, 31.0461],
    USA: [-95.7129, 37.0902],
    CHN: [104.1954, 35.8617],
    TUR: [35.2433, 38.9637],
    SAU: [45.0792, 23.8859],
    EGY: [30.8025, 26.8206],
    UKR: [31.1656, 48.3794],
    YEM: [48.5164, 15.5527],
    AFN: [67.7099, 33.9391],
    PAK: [69.3451, 30.3753],
    IND: [78.9629, 20.5937],
    KOR: [127.7669, 35.9078],
    PRK: [127.5101, 40.3399],
    VEN: [-63.5889, 6.4238],
  };

  return staticCentroids[upperCode] || null;
};

const RiskProgressBar: React.FC<{ score: number; color: string }> = ({ score, color }) => {
  const blocks = 10;
  const filled = Math.round(score * blocks);
  return (
    <div className="flex gap-[2px] items-center">
      {Array.from({ length: blocks }).map((_, idx) => (
        <div
          key={idx}
          className="w-[5px] h-2.5 rounded-[1px] transition-colors duration-200"
          style={{
            backgroundColor: idx < filled ? color : '#374151',
          }}
        />
      ))}
    </div>
  );
};

// Risk Radar Panel Component
const RiskRadarPanel: React.FC<{
  riskData: CountryRiskData[];
  conflictCount: number;
  cautiousCount: number;
}> = ({ riskData, conflictCount, cautiousCount }) => {
  const topRisks = riskData.sort((a, b) => b.riskScore - a.riskScore).slice(0, 5);

  const getRiskColor = (score: number): string => {
    if (score > 0.5) return '#ef4444';
    if (score > 0.2) return '#f59e0b';
    return '#10b981';
  };

  return (
    <div
      className="flex flex-col border border-carbon-600 bg-[#0a0f1a] text-carbon-100 p-3 shadow-2xl"
      style={{
        fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
        fontSize: '11px',
        lineHeight: '1.4',
        minWidth: '220px',
      }}
    >
      <div className="flex items-center gap-2 font-bold text-xs text-carbon-50 border-b border-carbon-700 pb-2 mb-2">
        <Shield className="w-3.5 h-3.5 text-red-400" />
        <span>RİSK RADAR</span>
      </div>

      <div className="text-[10px] text-carbon-400 mb-2 font-semibold">EN YÜKSEK RİSKLİ ÜLKELER</div>

      <div className="space-y-2 mb-3">
        {topRisks.map((item, idx) => (
          <div key={item.countryCode} className="flex items-center gap-3">
            <span className="text-carbon-500 w-4 font-mono">{idx + 1}.</span>
            <div className="flex-1 min-w-[58px]">
              <RiskProgressBar score={item.riskScore} color={getRiskColor(item.riskScore)} />
            </div>
            <span className="w-12 truncate text-right font-mono text-carbon-300">
              {item.countryCode}
            </span>
            <span
              className="w-8 text-right font-semibold font-mono"
              style={{ color: getRiskColor(item.riskScore) }}
            >
              {item.riskScore.toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      <div className="border-t border-carbon-800 pt-2 space-y-1">
        <div className="flex justify-between">
          <span className="text-carbon-400">Çatışma Noktaları:</span>
          <span className="font-semibold text-red-400">{conflictCount}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-carbon-400">CAUTIOUS İlişkiler:</span>
          <span className="font-semibold text-amber-400">{cautiousCount}</span>
        </div>
      </div>
    </div>
  );
};

export const RiskHotspotLayer: React.FC<RiskHotspotLayerProps> = ({
  nodes,
  flows,
  projection,
  geographies,
  visible = true,
  highlightedCountry,
}) => {
  const [hoveredFlow, setHoveredFlow] = useState<BilateralFlow | null>(null);
  const [tooltipCoords, setTooltipCoords] = useState<{ x: number; y: number } | null>(null);

  // Calculate risk scores for all countries
  const riskData = useMemo(() => {
    const data: CountryRiskData[] = nodes.map((node) => {
      const adversaryCount = flows.filter(
        (f) =>
          ((f.fromIso3 || f.fromCountry) === node.country ||
            (f.toIso3 || f.toCountry) === node.country) &&
          f.relationshipType === 'ADVERSARY',
      ).length;

      const cautiousCount = flows.filter(
        (f) =>
          ((f.fromIso3 || f.fromCountry) === node.country ||
            (f.toIso3 || f.toCountry) === node.country) &&
          f.relationshipType === 'CAUTIOUS',
      ).length;

      const accusationRatio =
        node.accusationCount / (node.praiseCount + node.accusationCount + node.neutralCount + 1);

      const sentimentPenalty = node.avgSentiment < -0.3 ? 0.2 : 0;

      const riskScore = Math.min(
        1,
        adversaryCount * 0.4 + cautiousCount * 0.1 + accusationRatio * 0.35 + sentimentPenalty,
      );

      const coordinates = getCountryCoordinates(node.country, geographies, nodes);

      return {
        countryCode: node.country,
        riskScore,
        adversaryCount,
        cautiousCount,
        accusationRatio,
        sentimentPenalty,
        coordinates,
      };
    });

    return data;
  }, [nodes, flows, geographies]);

  // Get ADVERSARY flows for conflict edge markers
  const adversaryFlows = useMemo(() => {
    return flows.filter((f) => f.relationshipType === 'ADVERSARY');
  }, [flows]);

  // Calculate stats for Risk Radar
  const conflictCount = useMemo(() => {
    return new Set(
      adversaryFlows.flatMap((f) => [f.fromIso3 || f.fromCountry, f.toIso3 || f.toCountry]),
    ).size;
  }, [adversaryFlows]);

  const cautiousCount = useMemo(() => {
    return flows.filter((f) => f.relationshipType === 'CAUTIOUS').length;
  }, [flows]);

  // Get countries with ADVERSARY relationships for pulse halos
  const adversaryCountries = useMemo(() => {
    const countries = new Set<string>();
    adversaryFlows.forEach((f) => {
      countries.add(f.fromIso3 || f.fromCountry);
      countries.add(f.toIso3 || f.toCountry);
    });
    return Array.from(countries);
  }, [adversaryFlows]);

  // Get high risk countries for heatmap
  const highRiskCountries = useMemo(() => {
    return riskData.filter((d) => d.riskScore > 0.5 && d.coordinates);
  }, [riskData]);

  const handleFlowHover = (e: React.MouseEvent, flow: BilateralFlow) => {
    setHoveredFlow(flow);
    setTooltipCoords({ x: e.clientX, y: e.clientY });
  };

  const handleFlowLeave = () => {
    setHoveredFlow(null);
    setTooltipCoords(null);
  };

  if (!visible) return null;

  return (
    <>
      {/* Inline styles for animations */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        @keyframes pulse-halo {
          0% {
            r: 20;
            opacity: 0.8;
          }
          50% {
            r: 35;
            opacity: 0.4;
          }
          100% {
            r: 20;
            opacity: 0.8;
          }
        }
        .pulse-halo {
          animation: pulse-halo 2s ease-in-out infinite;
          pointer-events: none;
        }
        @keyframes warning-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        .warning-blink {
          animation: warning-blink 1.5s ease-in-out infinite;
        }
      `,
        }}
      />

      {/* SVG Filters for blur effects */}
      <defs>
        <filter id="risk-blur">
          <feGaussianBlur stdDeviation="15" />
        </filter>
        <radialGradient id="danger-gradient">
          <stop offset="0%" stopColor="#ef4444" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Layer 1: Pulse Halo for ADVERSARY countries */}
      {adversaryCountries.map((countryCode) => {
        const coords = getCountryCoordinates(countryCode, geographies, nodes);
        if (!coords) return null;

        const projected = projection(coords);
        if (!projected) return null;

        const [x, y] = projected;
        const isHighlighted = highlightedCountry === countryCode;

        return (
          <g key={`pulse-${countryCode}`}>
            <circle
              cx={x}
              cy={y}
              r={isHighlighted ? 25 : 20}
              fill="none"
              stroke="#ef4444"
              strokeWidth={2}
              className="pulse-halo"
              style={{ opacity: isHighlighted ? 1 : 0.7 }}
            />
            <circle
              cx={x}
              cy={y}
              r={isHighlighted ? 30 : 25}
              fill="none"
              stroke="#ef4444"
              strokeWidth={1}
              className="pulse-halo"
              style={{
                animationDelay: '0.5s',
                opacity: isHighlighted ? 0.6 : 0.4,
              }}
            />
          </g>
        );
      })}

      {/* Layer 2: Danger Zone Heatmap for high risk countries */}
      {highRiskCountries.map((data) => {
        if (!data.coordinates) return null;

        const projected = projection(data.coordinates);
        if (!projected) return null;

        const [x, y] = projected;

        return (
          <circle
            key={`heatmap-${data.countryCode}`}
            cx={x}
            cy={y}
            r={60}
            fill={`rgba(239, 68, 68, ${data.riskScore * 0.3})`}
            filter="url(#risk-blur)"
            className="pointer-events-none"
            style={{ opacity: 0.6 }}
          />
        );
      })}

      {/* Layer 3: Conflict Edge Markers for ADVERSARY flows */}
      {adversaryFlows.map((flow, idx) => {
        const from = flow.fromIso3 || flow.fromCountry;
        const to = flow.toIso3 || flow.toCountry;
        const fromCoords = getCountryCoordinates(from, geographies, nodes);
        const toCoords = getCountryCoordinates(to, geographies, nodes);

        if (!fromCoords || !toCoords) return null;

        const p0 = projection(fromCoords);
        const p2 = projection(toCoords);

        if (!p0 || !p2) return null;

        const [x0, y0] = p0;
        const [x2, y2] = p2;

        const midX = (x0 + x2) / 2;
        const midY = (y0 + y2) / 2;

        const isHighlighted = highlightedCountry === from || highlightedCountry === to;

        return (
          <g key={`conflict-edge-${idx}`}>
            {/* Invisible hit area for hover */}
            <line
              x1={x0}
              y1={y0}
              x2={x2}
              y2={y2}
              stroke="transparent"
              strokeWidth={12}
              className="cursor-pointer"
              onMouseEnter={(e) => handleFlowHover(e, flow)}
              onMouseMove={(e) => setTooltipCoords({ x: e.clientX, y: e.clientY })}
              onMouseLeave={handleFlowLeave}
            />

            {/* Dashed conflict line */}
            <line
              x1={x0}
              y1={y0}
              x2={x2}
              y2={y2}
              stroke="#ef4444"
              strokeWidth={2}
              strokeDasharray="8, 4"
              className="pointer-events-none"
              style={{
                opacity: isHighlighted ? 1 : 0.7,
              }}
            />

            {/* Warning icon at midpoint */}
            <g transform={`translate(${midX}, ${midY})`} className="pointer-events-none">
              <circle
                r={12}
                fill="#0a0f1a"
                stroke="#ef4444"
                strokeWidth={2}
                className={isHighlighted ? 'warning-blink' : ''}
              />
              <text
                x={0}
                y={4}
                textAnchor="middle"
                fontSize={14}
                fill="#ef4444"
                style={{ fontFamily: 'sans-serif' }}
              >
                ⚠️
              </text>
            </g>
          </g>
        );
      })}

      {/* Layer 4: Risk Donut Badges on bubble markers */}
      {riskData.map((data) => {
        if (!data.coordinates || data.riskScore < 0.2) return null;

        const projected = projection(data.coordinates);
        if (!projected) return null;

        const [x, y] = projected;

        const getRiskColor = (score: number): string => {
          if (score > 0.5) return '#ef4444';
          if (score > 0.2) return '#f59e0b';
          return '#10b981';
        };

        const riskColor = getRiskColor(data.riskScore);

        return (
          <g key={`badge-${data.countryCode}`} transform={`translate(${x + 15}, ${y - 15})`}>
            <circle r={6} fill="#0a0f1a" stroke={riskColor} strokeWidth={2} />
            <circle r={3} fill={riskColor} />
          </g>
        );
      })}

      {/* Tooltip for conflict edges */}
      {hoveredFlow &&
        tooltipCoords &&
        typeof window !== 'undefined' &&
        document.body &&
        createPortal(
          <div
            className="fixed z-50 pointer-events-none rounded-none border border-red-600 bg-[#0a0f1a]/95 p-3 shadow-2xl backdrop-blur-md transition-all duration-75 text-[11px]"
            style={{
              top: tooltipCoords.y,
              left: tooltipCoords.x,
              transform: 'translate(15px, 15px)',
              fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
              lineHeight: '1.4',
              color: '#cbd5e1',
            }}
          >
            <div className="font-bold text-red-400 text-xs mb-1 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3" />
              ADVERSARY
            </div>
            <div className="border-t border-carbon-800 my-1.5" />
            <div className="flex items-center gap-1.5">
              <span>{hoveredFlow.fromIso3 || hoveredFlow.fromCountry}</span>
              <span className="text-carbon-500">↔</span>
              <span>{hoveredFlow.toIso3 || hoveredFlow.toCountry}</span>
            </div>
            <div className="text-carbon-400 mt-0.5">
              Affinity:{' '}
              <span className="font-semibold text-red-400">
                {hoveredFlow.affinityScore.toFixed(2)}
              </span>
            </div>
          </div>,
          document.body,
        )}

      {/* Risk Radar Panel - positioned at top right */}
      {visible && (
        <div
          className="absolute top-4 right-4 z-20"
          style={{
            transform: 'translateX(0)',
          }}
        >
          <RiskRadarPanel
            riskData={riskData}
            conflictCount={conflictCount}
            cautiousCount={cautiousCount}
          />
        </div>
      )}
    </>
  );
};
