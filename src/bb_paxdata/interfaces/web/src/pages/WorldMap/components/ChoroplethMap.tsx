// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/ChoroplethMap.tsx

import { geoMercator, geoNaturalEarth1, geoOrthographic } from 'd3-geo';
import { interpolateRgb } from 'd3-interpolate';
import { scaleLinear } from 'd3-scale';
import type { Feature } from 'geojson';
import { Zap } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ComposableMap,
  Geographies,
  Geography,
  Graticule,
  Sphere,
  ZoomableGroup,
} from 'react-simple-maps';
import type {
  BilateralFlow,
  DominantEmotion,
  RelationshipType,
} from '../../../types/visualization';
import {
  getAlpha3FromNumeric,
  RELATIONSHIP_COLORS,
  sentimentToColor,
} from '../../../utils/visualizationHelpers';
import { BilateralArcLayer } from './BilateralArcLayer';
import { MapProjectionSwitcher } from './MapProjectionSwitcher';
import { RiskHotspotLayer } from './RiskHotspotLayer';

// Path to the downloaded local TopoJSON file in the public directory
const geoUrl = `${import.meta.env.BASE_URL}world-110m.json`;

interface CountryNode {
  country_code: string;
  country_name: string;
  latitude: number;
  longitude: number;
  total_mentions: number;
  avg_sentiment: number;
}

interface CountryConnection {
  from_country: string;
  to_country: string;
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
  avg_sentiment: number;
  interaction_count: number;
  relationship_type: string;
  affinity_score: number;
}

interface GeographyObject extends Feature {
  rsmKey?: string;
}

type ProjectionType = 'naturalEarth' | 'mercator' | 'orthographic';

interface ChoroplethMapProps {
  width?: number; // default: container width
  height?: number; // default: 520
  projection?: ProjectionType; // switcher
  nodes: CountryNode[];
  connections: CountryConnection[];
  setSelectedCountry: (country: string | null) => void;
  selectedCountry?: string | null;
  highlightedCountry: string | null;
  setHighlightedCountry: (country: string | null) => void;
  selectedConnection: CountryConnection | null;
  setSelectedConnection: (conn: CountryConnection | null) => void;
  flows?: BilateralFlow[];
  visibleTypes?: RelationshipType[];
  showAllFlows?: boolean;
  onArcHover?: (flow: BilateralFlow | null) => void;
  showRiskLayer?: boolean;
  mapContainerRef?: React.RefObject<HTMLDivElement>;
}

interface TooltipData {
  x: number;
  y: number;
  content: React.ReactNode;
}

// Programmatic regional flag emoji generator
const getFlagEmoji = (countryCode: string): string => {
  const iso3ToIso2: Record<string, string> = {
    USA: 'US',
    TUR: 'TR',
    RUS: 'RU',
    CHN: 'CN',
    GBR: 'GB',
    FRA: 'FR',
    DEU: 'DE',
    ITA: 'IT',
    ESP: 'ES',
    POL: 'PL',
    UKR: 'UA',
    JPN: 'JP',
    KOR: 'KR',
    IND: 'IN',
    PAK: 'PK',
    IRN: 'IR',
    SAU: 'SA',
    EGY: 'EG',
    BRA: 'BR',
    ARG: 'AR',
    MEX: 'MX',
    CAN: 'CA',
    AUS: 'AU',
    IDN: 'ID',
    NGA: 'NG',
    ZAF: 'ZA',
    COL: 'CO',
    VEN: 'VE',
    CHL: 'CL',
    PER: 'PE',
    GRC: 'GR',
    PRT: 'PT',
    NLD: 'NL',
    BEL: 'BE',
    AUT: 'AT',
    CHE: 'CH',
    SWE: 'SE',
    NOR: 'NO',
    DNK: 'DK',
    FIN: 'FI',
    CZE: 'CZ',
    HUN: 'HU',
    ROU: 'RO',
    BGR: 'BG',
    SRB: 'RS',
    HRV: 'HR',
    BIH: 'BA',
    SVN: 'SI',
    SVK: 'SK',
    EST: 'EE',
    LVA: 'LV',
    LTU: 'LT',
    BLR: 'BY',
    MDA: 'MD',
    GEO: 'GE',
    ARM: 'AM',
    AZE: 'AZ',
    KAZ: 'KZ',
    UZB: 'UZ',
    TKM: 'TM',
    KGZ: 'KG',
    TJK: 'TJ',
    AFG: 'AF',
    IRQ: 'IQ',
    SYR: 'SY',
    JOR: 'JO',
    LBN: 'LB',
    ISR: 'IL',
    PSE: 'PS',
    KWT: 'KW',
    BHR: 'BH',
    QAT: 'QA',
    ARE: 'AE',
    OMN: 'OM',
    YEM: 'YE',
    MAR: 'MA',
    DZA: 'DZ',
    TUN: 'TN',
    LBY: 'LY',
    SDN: 'SD',
    ETH: 'ET',
    KEN: 'KE',
    TZA: 'TZ',
    UGA: 'UG',
    RWA: 'RW',
    COD: 'CD',
    ZWE: 'ZW',
    ZMB: 'ZM',
    MWI: 'MW',
    MOZ: 'MZ',
    AGO: 'AO',
    NAM: 'NA',
    BWA: 'BW',
    LSO: 'LS',
    SWZ: 'SZ',
    MDG: 'MG',
    MUS: 'MU',
    COM: 'KM',
    SYC: 'SC',
    DJI: 'DJ',
    SOM: 'SO',
    ERI: 'ER',
    SSD: 'SS',
    CMR: 'CM',
    BEN: 'BJ',
    TGO: 'TG',
    GHA: 'GH',
    CIV: 'CI',
    GIN: 'GN',
    SEN: 'SN',
    MLI: 'ML',
    BFA: 'BF',
    NER: 'NE',
    TCD: 'TD',
    CAF: 'CF',
    COG: 'CG',
    GAB: 'GA',
    GNQ: 'GQ',
    STP: 'ST',
    GMB: 'GM',
    GNB: 'GW',
    SLE: 'SL',
    LBR: 'LR',
    MRT: 'MR',
    CUB: 'CU',
    HTI: 'HT',
    DOM: 'DO',
    JAM: 'JM',
    TTO: 'TT',
    BRB: 'BB',
    GRD: 'GD',
    LCA: 'LC',
    VCT: 'VC',
    ATG: 'AG',
    DMA: 'DM',
    KNA: 'KN',
    BLZ: 'BZ',
    GTM: 'GT',
    SLV: 'SV',
    HND: 'HN',
    NIC: 'NI',
    CRI: 'CR',
    PAN: 'PA',
    ECU: 'EC',
    BOL: 'BO',
    PRY: 'PY',
    URY: 'UY',
    GUY: 'GY',
    SUR: 'SR',
    FLK: 'FK',
    MYS: 'MY',
    SGP: 'SG',
    THA: 'TH',
    VNM: 'VN',
    LAO: 'LA',
    KHM: 'KH',
    MMR: 'MM',
    BGD: 'BD',
    LKA: 'LK',
    NPL: 'NP',
    BTN: 'BT',
    MDV: 'MV',
    PHL: 'PH',
    TLS: 'TL',
    PNG: 'PG',
    NZL: 'NZ',
    FJI: 'FJ',
    SLB: 'SB',
    VUT: 'VU',
    NCL: 'NC',
    PYF: 'PF',
    ASM: 'AS',
    GUM: 'GU',
    MNP: 'MP',
    PRI: 'PR',
    VIR: 'VI',
  };
  const iso2 = iso3ToIso2[countryCode.toUpperCase()];
  if (!iso2) return '🌐';
  const codePoints = iso2
    .toUpperCase()
    .split('')
    .map((char) => 127397 + char.charCodeAt(0));
  try {
    return String.fromCodePoint(...codePoints);
  } catch (_e) {
    return '🌐';
  }
};

// Sleek indicator component representing sentiment range -1.0 to 1.0
const SentimentIndicator: React.FC<{ score: number; color: string }> = ({ score, color }) => {
  const pct = Math.min(100, Math.max(0, Math.abs(score) * 50)); // percentage from center (0 to 50%)
  const isPositive = score >= 0;

  return (
    <div
      className="w-[60px] h-2 bg-carbon-800 rounded-full relative overflow-hidden flex items-center border border-carbon-700"
      style={{
        backgroundColor: 'var(--bg-primary)',
        borderColor: 'var(--border-hair)',
      }}
    >
      {/* Center line representing neutral (0) */}
      <div
        className="absolute left-[50%] top-0 bottom-0 w-[1px] z-10"
        style={{ backgroundColor: 'var(--border-subtle)' }}
      />
      {/* Progress fill from center */}
      <div
        className="absolute h-full transition-all duration-300"
        style={{
          left: isPositive ? '50%' : 'auto',
          right: !isPositive ? '50%' : 'auto',
          width: `${pct}%`,
          backgroundColor: color,
        }}
      />
    </div>
  );
};

// Map sentiment level to custom dynamic dominant emotion
const getDominantEmotion = (sentiment: number): DominantEmotion => {
  if (sentiment > 0.3) return 'cooperative';
  if (sentiment > 0.1) return 'constructive';
  if (sentiment > -0.1) return 'neutral_cautious';
  return 'concerned';
};

// BubbleMarker component removed

export const ChoroplethMap: React.FC<ChoroplethMapProps> = ({
  width,
  height,
  projection = 'naturalEarth',
  nodes,
  connections,
  setSelectedCountry,
  selectedCountry,
  highlightedCountry,
  setHighlightedCountry,
  selectedConnection: _selectedConnection,
  setSelectedConnection,
  flows,
  visibleTypes,
  showAllFlows,
  onArcHover,
  showRiskLayer = false,
  mapContainerRef: externalMapContainerRef,
}) => {
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [localProjection, setLocalProjection] = useState<ProjectionType>(projection);
  const internalContainerRef = useRef<HTMLDivElement>(null);
  const containerRef = externalMapContainerRef || internalContainerRef;

  // Sync prop changes to local projection state
  useEffect(() => {
    if (projection) {
      setLocalProjection(projection);
    }
  }, [projection]);

  // Coordinate and Zoom states controlled by buttons and d3-zoom internally
  const [position, setPosition] = useState({
    coordinates: [0, 10] as [number, number],
    zoom: 1,
  });
  const [rotation, setRotation] = useState<[number, number, number]>([0, 0, 0]);

  // Handle Drag-to-rotate globe physics for orthographic projection
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Sync viewport settings on projection switcher activation
  useEffect(() => {
    if (localProjection === 'orthographic') {
      // Transition from flat to globe: rotate to face current flat center coordinates
      const targetLon = -position.coordinates[0];
      const targetLat = -position.coordinates[1];
      setRotation([targetLon, targetLat, 0]);
    } else {
      // Transition from globe to flat: set flat center to current globe rotation center
      const currentLon = -rotation[0];
      const currentLat = -rotation[1];

      // Clean bounds checking for flat map center
      const boundedLon = Math.max(-180, Math.min(180, currentLon));
      const boundedLat = Math.max(-90, Math.min(90, currentLat));

      // Set appropriate zoom for mercator vs naturalEarth
      const targetZoom = localProjection === 'mercator' ? 1.2 : 1;

      setPosition({
        coordinates: [boundedLon, boundedLat],
        zoom: targetZoom,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localProjection]);

  // ResizeObserver state logic to compute responsive container dimensions
  const [dimensions, setDimensions] = useState({
    width: width || 800,
    height: height || 600,
  });

  useEffect(() => {
    if (width && height) {
      setDimensions({ width, height });
      return;
    }
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const rectWidth = entry.contentRect.width;
        const rectHeight = entry.contentRect.height;
        setDimensions({
          width: width || rectWidth || 800,
          height: height || rectHeight || 600,
        });
      }
    });
    observer.observe(containerRef.current);
    // Initial measurement
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setDimensions({
        width: width || rect.width || 800,
        height: height || rect.height || 600,
      });
    }
    return () => observer.disconnect();
  }, [width, height, containerRef]);

  // Setup D3 Linear Sentiment Color scale:
  const choroplethScale = useMemo(() => {
    return scaleLinear<string>()
      .domain([-1.0, 0.0, 1.0])
      .range(['#7f1d1d', '#1e293b', '#064e3b'])
      .interpolate(interpolateRgb);
  }, []);

  // Synchronized props or local defaults for bilateral flow layer
  const [localVisibleTypes, setLocalVisibleTypes] = useState<RelationshipType[]>(
    visibleTypes || ['ALLY', 'PARTNER', 'NEUTRAL', 'CAUTIOUS', 'ADVERSARY'],
  );
  const [localShowAllFlows, setLocalShowAllFlows] = useState<boolean>(
    showAllFlows !== undefined ? showAllFlows : true,
  );
  const [localShowRiskLayer, setLocalShowRiskLayer] = useState<boolean>(
    showRiskLayer !== undefined ? showRiskLayer : false,
  );

  useEffect(() => {
    if (visibleTypes) setLocalVisibleTypes(visibleTypes);
  }, [visibleTypes]);

  useEffect(() => {
    if (showAllFlows !== undefined) setLocalShowAllFlows(showAllFlows);
  }, [showAllFlows]);

  useEffect(() => {
    if (showRiskLayer !== undefined) setLocalShowRiskLayer(showRiskLayer);
  }, [showRiskLayer]);

  // Convert connections to flows if flows prop is not provided
  const mappedFlows = useMemo(() => {
    if (flows) return flows;
    return connections.map((conn) => ({
      fromCountry: conn.from_country,
      toCountry: conn.to_country,
      fromIso3: conn.from_country,
      toIso3: conn.to_country,
      interactionCount: conn.interaction_count,
      avgSentiment: conn.avg_sentiment,
      affinityScore: conn.affinity_score,
      powerWeightedScore: 0,
      relationshipType: (conn.relationship_type as RelationshipType) || 'NEUTRAL',
      praiseRatio: 0,
      accusationRatio: 0,
      sessions: [],
    }));
  }, [flows, connections]);

  // Stable flat projection instances that do not change during zoom/pan
  const flatProjectionInstance = useMemo(() => {
    let proj;
    // Calculate responsive scale based on container dimensions
    const minDimension = Math.min(dimensions.width, dimensions.height);
    const baseScale = localProjection === 'mercator' ? minDimension * 0.4 : minDimension * 0.18;

    if (localProjection === 'mercator') {
      proj = geoMercator().scale(baseScale);
    } else {
      proj = geoNaturalEarth1().scale(baseScale);
    }
    return proj.translate([dimensions.width / 2, dimensions.height / 2]);
  }, [localProjection, dimensions.width, dimensions.height]);

  // Orthographic projection instance that updates on rotation and zoom
  const orthographicProjectionInstance = useMemo(() => {
    if (localProjection !== 'orthographic') return null;
    // Calculate responsive scale based on container dimensions
    const minDimension = Math.min(dimensions.width, dimensions.height);
    const baseScale = minDimension * 0.25;

    return geoOrthographic()
      .scale(baseScale * position.zoom)
      .rotate(rotation as [number, number, number])
      .translate([dimensions.width / 2, dimensions.height / 2]);
  }, [localProjection, rotation, position.zoom, dimensions.width, dimensions.height]);

  // Combined projection instance passed to child layers
  const projectionInstance =
    localProjection === 'orthographic' ? orthographicProjectionInstance! : flatProjectionInstance;

  const handleArcHover = (flow: BilateralFlow | null) => {
    if (onArcHover) {
      onArcHover(flow);
    }
    if (flow) {
      // Find matching connection in parent to highlight selectedConnection panel
      const conn = connections.find(
        (c) => c.from_country === flow.fromCountry && c.to_country === flow.toCountry,
      );
      if (conn) {
        setSelectedConnection(conn);
      }
    } else {
      setSelectedConnection(null);
    }
  };

  // Helper to determine the dominant relationship type for a country from its connections
  const getDominantRelType = (
    countryCode: string,
    conns: CountryConnection[],
  ): RelationshipType => {
    const countryConns = conns.filter(
      (c) => c.from_country === countryCode || c.to_country === countryCode,
    );
    if (countryConns.length === 0) return 'NEUTRAL';

    const counts: Record<string, number> = {};
    countryConns.forEach((c) => {
      const type = c.relationship_type as RelationshipType;
      counts[type] = (counts[type] || 0) + c.interaction_count;
    });

    let dominant: RelationshipType = 'NEUTRAL';
    let maxVal = -1;
    (Object.keys(counts) as RelationshipType[]).forEach((type) => {
      if (counts[type] > maxVal) {
        maxVal = counts[type];
        dominant = type;
      }
    });

    return dominant;
  };

  // bubbleData calculation removed

  // Drag handlers for the Orthographic Globe rotation
  const handleMouseDown = (e: React.MouseEvent) => {
    if (localProjection === 'orthographic') {
      setIsDragging(true);
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseMoveRotate = (e: React.MouseEvent) => {
    if (isDragging && localProjection === 'orthographic') {
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      setRotation((prev) => [prev[0] + dx * 0.35, prev[1] - dy * 0.35, prev[2]]);
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    if (localProjection === 'orthographic') {
      // Keep position.coordinates synced with rotation center
      setPosition((prev) => ({
        ...prev,
        coordinates: [-rotation[0], -rotation[1]],
      }));
    }
  };

  const showTooltip = (e: React.MouseEvent, content: React.ReactNode) => {
    setTooltip({
      x: e.clientX,
      y: e.clientY,
      content,
    });
  };

  const moveTooltip = (e: React.MouseEvent) => {
    setTooltip((prev) => (prev ? { ...prev, x: e.clientX, y: e.clientY } : null));
  };

  const hideTooltip = () => {
    setTooltip(null);
  };

  // Custom styling-matched tooltip renderer
  const renderCountryTooltip = (countryCode: string) => {
    const node = nodes.find((n) => n.country_code === countryCode);
    const dominantRel = getDominantRelType(countryCode, connections);

    if (!node) {
      return (
        <div
          className="flex flex-col border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-[var(--text-primary)] p-3 min-w-[200px]"
          style={{
            fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
            fontSize: '11px',
            lineHeight: '1.4',
          }}
        >
          <div className="flex items-center gap-1.5 font-bold text-sm text-[var(--text-primary)] border-b border-[var(--border-subtle)] pb-1.5 mb-1.5">
            <span>{getFlagEmoji(countryCode)}</span>
            <span>{countryCode}</span>
          </div>
          <span className="text-[var(--text-tertiary)] italic text-[10px]">
            Etkileşim verisi yok
          </span>
        </div>
      );
    }

    const sentimentColor = sentimentToColor(node.avg_sentiment);
    const relColor = RELATIONSHIP_COLORS[dominantRel] || '#9ca3af';
    const dominantEmotion = getDominantEmotion(node.avg_sentiment);
    const sessionCount = Math.max(1, Math.min(8, Math.round(node.total_mentions / 12)));

    return (
      <div
        className="flex flex-col border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-[var(--text-primary)] p-3.5 min-w-[230px] shadow-2xl"
        style={{
          fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
          fontSize: '11px',
          lineHeight: '1.4',
        }}
      >
        <div className="flex items-center gap-2 font-bold text-xs text-[var(--text-primary)] border-b border-[var(--border-subtle)] pb-1.5 mb-2">
          <span className="text-sm leading-none">{getFlagEmoji(node.country_code)}</span>
          <span className="truncate">{node.country_name}</span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-carbon-400">Sentiment:</span>
          <span className="font-semibold flex items-center gap-2.5">
            <span style={{ color: sentimentColor }}>
              {node.avg_sentiment > 0 ? '+' : ''}
              {node.avg_sentiment.toFixed(2)}
            </span>
            <SentimentIndicator score={node.avg_sentiment} color={sentimentColor} />
          </span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-carbon-400">Etkileşim:</span>
          <span className="font-semibold text-carbon-100">{node.total_mentions}</span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-carbon-400">Baskın İlişki:</span>
          <span className="font-semibold" style={{ color: relColor }}>
            {dominantRel}
          </span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-carbon-400">Dominant Duygu:</span>
          <span className="font-semibold text-carbon-200">{dominantEmotion}</span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-carbon-400">Oturumlar:</span>
          <span className="font-semibold text-carbon-100">{sessionCount} oturum</span>
        </div>
        <div className="text-[10px] text-indigo-400 font-semibold mt-2.5 pt-1.5 border-t border-[var(--border-subtle)] text-center select-none cursor-pointer">
          [Detay Göster →]
        </div>
      </div>
    );
  };

  // Zoom Button Controls
  const zoomIn = () => {
    setPosition((prev) => ({ ...prev, zoom: Math.min(8, prev.zoom * 1.4) }));
  };

  const zoomOut = () => {
    setPosition((prev) => ({ ...prev, zoom: Math.max(1, prev.zoom / 1.4) }));
  };

  const resetZoom = () => {
    if (localProjection === 'mercator') {
      setPosition({ coordinates: [20, 48], zoom: 1.2 });
    } else if (localProjection === 'orthographic') {
      setPosition({ coordinates: [0, 0], zoom: 1 });
      setRotation([0, 0, 0]);
    } else {
      setPosition({ coordinates: [0, 10], zoom: 1 });
    }
  };

  // Computed projection styles
  const isGlobe = localProjection === 'orthographic';
  const currentProjectionType =
    localProjection === 'orthographic'
      ? 'geoOrthographic'
      : localProjection === 'mercator'
        ? 'geoMercator'
        : 'geoNaturalEarth1';

  const projectionConfig = useMemo(() => {
    const minDimension = Math.min(dimensions.width, dimensions.height);

    if (localProjection === 'orthographic') {
      return {
        scale: minDimension * 0.4 * position.zoom,
        rotate: rotation,
      };
    } else if (localProjection === 'mercator') {
      // Focused regional view of Europe/Middle-East (center removed)
      return {
        scale: minDimension * 0.7,
      };
    } else {
      // NaturalEarth global projection (center removed)
      return {
        scale: minDimension * 0.3,
      };
    }
  }, [localProjection, rotation, position.zoom, dimensions.width, dimensions.height]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none bg-[var(--bg-secondary)]"
      onMouseLeave={() => {
        handleMouseUp();
        hideTooltip();
      }}
    >
      {/* Import JetBrains Mono via CDN, inject hardware acceleration/performance classes */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');
        @keyframes pulse-ring {
          0% {
            transform: scale(0.6);
            opacity: 0.8;
          }
          100% {
            transform: scale(2.2);
            opacity: 0;
          }
        }
        .animate-pulse-ring {
          animation: pulse-ring 2.5s cubic-bezier(0.215, 0.610, 0.355, 1) infinite;
          transform-origin: center;
          transform-box: fill-box;
          pointer-events: none;
          will-change: transform;
        }
        .rsm-geography {
          will-change: transform;
        }
      `,
        }}
      />

      {/* Projection switcher inside map component (Top Right) */}
      <MapProjectionSwitcher
        currentProjection={localProjection}
        onChangeProjection={setLocalProjection}
      />

      {/* Floating Bilateral Flow Control Panel (Top Left) */}
      <div
        className="absolute top-2 left-2 z-10 flex flex-col gap-1.5 pointer-events-auto bg-carbon-900/90 border border-carbon-700/80 shadow-2xl backdrop-blur-md"
        style={{
          padding: 'clamp(6px, 0.8vw, 12px)',
          fontSize: 'clamp(9px, 0.8vw, 11px)',
          maxWidth: 'min(220px, 20vw)',
          fontFamily: "'JetBrains Mono', monospace",
          color: '#cbd5e1',
        }}
      >
        <div className="font-bold text-white flex items-center gap-1 mb-0.5">
          <Zap className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
          Bilateral Akış Filtreleri
        </div>
        <div className="border-t border-carbon-800 my-1" />
        <label className="flex items-center gap-2 cursor-pointer text-[10px] text-carbon-300 hover:text-white transition-colors duration-150">
          <input
            type="checkbox"
            checked={localShowAllFlows}
            onChange={(e) => setLocalShowAllFlows(e.target.checked)}
            className="accent-indigo-500 rounded border-carbon-700 bg-carbon-950"
          />
          Tüm Akışları Göster (&lt;5 etkileşim)
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-[10px] text-red-300 hover:text-red-200 transition-colors duration-150">
          <input
            type="checkbox"
            checked={localShowRiskLayer}
            onChange={(e) => setLocalShowRiskLayer(e.target.checked)}
            className="accent-red-500 rounded border-carbon-700 bg-carbon-950"
          />
          Risk Katmanını Göster
        </label>
        <div className="flex flex-wrap gap-1 mt-1.5">
          {(['ALLY', 'PARTNER', 'NEUTRAL', 'CAUTIOUS', 'ADVERSARY'] as RelationshipType[]).map(
            (type) => {
              const isActive = localVisibleTypes.includes(type);
              const color = RELATIONSHIP_COLORS[type] || '#94a3b8';
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => {
                    setLocalVisibleTypes((prev) =>
                      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type],
                    );
                  }}
                  className={`px-1.5 py-0.5 text-[9px] border transition-all duration-150 ${
                    isActive
                      ? 'bg-carbon-800 text-white font-semibold'
                      : 'bg-transparent text-carbon-500 border-carbon-800 hover:border-carbon-700 hover:text-carbon-400'
                  }`}
                  style={{
                    borderColor: isActive ? color : undefined,
                    borderWidth: '1px',
                  }}
                >
                  <span
                    className="w-1.5 h-1.5 inline-block mr-1 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  {type}
                </button>
              );
            },
          )}
        </div>
      </div>

      {/* Zoom controls inside map component (Bottom Right) */}
      <div className="absolute bottom-2 right-2 flex flex-col gap-1 bg-carbon-900/90 border border-carbon-700/80 p-1 shadow-2xl backdrop-blur-md z-10 pointer-events-auto">
        <button
          onClick={zoomIn}
          type="button"
          className="flex items-center justify-center border border-carbon-700 text-carbon-300 hover:text-white hover:bg-carbon-800 font-bold select-none transition-all duration-150 rounded-none bg-carbon-950/70"
          style={{
            width: 'clamp(24px, 2.5vw, 32px)',
            height: 'clamp(24px, 2.5vw, 32px)',
            fontSize: 'clamp(12px, 1.2vw, 16px)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          +
        </button>
        <button
          onClick={zoomOut}
          type="button"
          className="flex items-center justify-center border border-carbon-700 text-carbon-300 hover:text-white hover:bg-carbon-800 font-bold select-none transition-all duration-150 rounded-none bg-carbon-950/70"
          style={{
            width: 'clamp(24px, 2.5vw, 32px)',
            height: 'clamp(24px, 2.5vw, 32px)',
            fontSize: 'clamp(12px, 1.2vw, 16px)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          -
        </button>
        <button
          onClick={resetZoom}
          type="button"
          className="flex items-center justify-center border border-carbon-700 text-carbon-300 hover:text-white hover:bg-carbon-800 font-bold select-none transition-all duration-150 rounded-none bg-carbon-950/70"
          style={{
            width: 'clamp(24px, 2.5vw, 32px)',
            height: 'clamp(24px, 2.5vw, 32px)',
            fontSize: 'clamp(12px, 1.2vw, 16px)',
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          ↺
        </button>
      </div>

      {/* Map Rendering Panel */}
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        onMouseDown={handleMouseDown}
        onMouseMove={(e) => {
          handleMouseMoveRotate(e);
          moveTooltip(e);
        }}
        onMouseUp={handleMouseUp}
        className={isGlobe ? 'cursor-grab active:cursor-grabbing' : ''}
      >
        <ComposableMap
          projection={currentProjectionType}
          projectionConfig={projectionConfig}
          width={dimensions.width}
          height={dimensions.height}
          style={{ width: '100%', height: '100%', outline: 'none' }}
        >
          {isGlobe ? (
            // Globe okyanus backplate
            <Sphere
              id="rsm-sphere"
              fill="var(--bg-primary)"
              stroke="var(--border-hair)"
              strokeWidth={0.5}
            />
          ) : (
            // Flat okyanus backplate
            <rect width={dimensions.width} height={dimensions.height} fill="var(--bg-primary)" />
          )}

          {/* Dynamic map geometries layout */}
          {isGlobe ? (
            // Globe orthographic rendering (we do not use ZoomableGroup to support standard rotation)
            <>
              <Graticule stroke="var(--border-hair)" strokeOpacity={0.2} strokeWidth={0.5} />
              <Geographies geography={geoUrl}>
                {({ geographies }: { geographies: GeographyObject[] }) => (
                  <>
                    {/* Country Geographies */}
                    {geographies.map((geo) => {
                      const countryCode = geo.id ? getAlpha3FromNumeric(geo.id) : undefined;
                      if (!countryCode) return null;

                      const node = nodes.find((n) => n.country_code === countryCode);
                      const isHighlighted = highlightedCountry === countryCode;
                      const hasHighlight = highlightedCountry !== null;

                      const opacity = hasHighlight ? (isHighlighted ? 1.0 : 0.3) : 1.0;
                      const fillColor = node
                        ? choroplethScale(node.avg_sentiment)
                        : 'var(--bg-quaternary)';

                      const isActive = node !== undefined;
                      const strokeColor = isActive ? 'var(--text-primary)' : 'var(--border-hair)';
                      const strokeWidth = isActive ? 1.0 : 0.5;

                      return (
                        <Geography
                          key={geo.id}
                          geography={geo}
                          onMouseEnter={(e: React.MouseEvent) => {
                            setHighlightedCountry(countryCode);
                            showTooltip(e, renderCountryTooltip(countryCode));
                          }}
                          onMouseMove={moveTooltip}
                          onMouseLeave={() => {
                            setHighlightedCountry(null);
                            hideTooltip();
                          }}
                          onClick={() => setSelectedCountry(countryCode)}
                          style={{
                            default: {
                              fill: fillColor,
                              fillOpacity: opacity,
                              stroke: strokeColor,
                              strokeWidth: strokeWidth,
                              strokeOpacity: opacity,
                              outline: 'none',
                            },
                            hover: {
                              fill: fillColor,
                              fillOpacity: 1.0,
                              stroke: '#ffffff',
                              strokeWidth: 1.2,
                              outline: 'none',
                              cursor: 'pointer',
                            },
                            pressed: {
                              fill: fillColor,
                              outline: 'none',
                            },
                          }}
                        />
                      );
                    })}

                    {/* Bilateral Arcs Connection Layer — only show when a country is selected */}
                    {selectedCountry && (
                      <BilateralArcLayer
                        flows={mappedFlows}
                        projection={projectionInstance}
                        highlightedCountry={selectedCountry}
                        visibleTypes={localVisibleTypes}
                        showAllFlows={localShowAllFlows}
                        onArcHover={handleArcHover}
                        geographies={geographies}
                        nodes={nodes}
                      />
                    )}

                    {/* Risk Hotspot Layer - ADVERSARY relationships, heatmaps, conflict edges */}
                    {localShowRiskLayer && mappedFlows.length > 0 && (
                      <RiskHotspotLayer
                        nodes={nodes.map((n) => ({
                          country: n.country_code,
                          isoAlpha3: n.country_code,
                          totalInteractions: n.total_mentions,
                          avgSentiment: n.avg_sentiment,
                          dominantEmotion: null,
                          relationshipCategories: {
                            ALLY: 0,
                            PARTNER: 0,
                            NEUTRAL: 0,
                            CAUTIOUS: 0,
                            ADVERSARY: 0,
                          },
                          praiseCount: 0,
                          accusationCount: 0,
                          neutralCount: 0,
                          powerLevel: 0,
                          sessions: [],
                        }))}
                        flows={mappedFlows}
                        projection={projectionInstance}
                        geographies={geographies}
                        visible={localShowRiskLayer}
                        highlightedCountry={highlightedCountry}
                      />
                    )}

                    {/* Bubble Markers removed */}
                  </>
                )}
              </Geographies>
            </>
          ) : (
            // Flat projections rendering with ZoomableGroup
            <ZoomableGroup
              zoom={position.zoom}
              center={position.coordinates}
              maxZoom={8}
              onMoveEnd={(newPos) =>
                setPosition({
                  coordinates: newPos.coordinates,
                  zoom: newPos.zoom,
                })
              }
            >
              <Graticule stroke="var(--border-hair)" strokeOpacity={0.2} strokeWidth={0.5} />
              <Geographies geography={geoUrl}>
                {({ geographies }: { geographies: GeographyObject[] }) => (
                  <>
                    {/* Country Geographies */}
                    {geographies.map((geo) => {
                      const countryCode = geo.id ? getAlpha3FromNumeric(geo.id) : undefined;
                      if (!countryCode) return null;

                      const node = nodes.find((n) => n.country_code === countryCode);
                      const isHighlighted = highlightedCountry === countryCode;
                      const hasHighlight = highlightedCountry !== null;

                      const opacity = hasHighlight ? (isHighlighted ? 1.0 : 0.3) : 1.0;
                      const fillColor = node
                        ? choroplethScale(node.avg_sentiment)
                        : 'var(--bg-quaternary)';

                      const isActive = node !== undefined;
                      const strokeColor = isActive ? 'var(--text-primary)' : 'var(--border-hair)';
                      const strokeWidth = isActive ? 1.0 : 0.5;

                      return (
                        <Geography
                          key={geo.id}
                          geography={geo}
                          onMouseEnter={(e: React.MouseEvent) => {
                            setHighlightedCountry(countryCode);
                            showTooltip(e, renderCountryTooltip(countryCode));
                          }}
                          onMouseMove={moveTooltip}
                          onMouseLeave={() => {
                            setHighlightedCountry(null);
                            hideTooltip();
                          }}
                          onClick={() => setSelectedCountry(countryCode)}
                          style={{
                            default: {
                              fill: fillColor,
                              fillOpacity: opacity,
                              stroke: strokeColor,
                              strokeWidth: strokeWidth,
                              strokeOpacity: opacity,
                              outline: 'none',
                            },
                            hover: {
                              fill: fillColor,
                              fillOpacity: 1.0,
                              stroke: '#ffffff',
                              strokeWidth: 1.2,
                              outline: 'none',
                              cursor: 'pointer',
                            },
                            pressed: {
                              fill: fillColor,
                              outline: 'none',
                            },
                          }}
                        />
                      );
                    })}

                    {/* Bilateral Arcs Connection Layer — only show when a country is selected */}
                    {selectedCountry && (
                      <BilateralArcLayer
                        flows={mappedFlows}
                        projection={projectionInstance}
                        highlightedCountry={selectedCountry}
                        visibleTypes={localVisibleTypes}
                        showAllFlows={localShowAllFlows}
                        onArcHover={handleArcHover}
                        geographies={geographies}
                        nodes={nodes}
                      />
                    )}

                    {/* Risk Hotspot Layer - ADVERSARY relationships, heatmaps, conflict edges */}
                    {localShowRiskLayer && mappedFlows.length > 0 && (
                      <RiskHotspotLayer
                        nodes={nodes.map((n) => ({
                          country: n.country_code,
                          isoAlpha3: n.country_code,
                          totalInteractions: n.total_mentions,
                          avgSentiment: n.avg_sentiment,
                          dominantEmotion: null,
                          relationshipCategories: {
                            ALLY: 0,
                            PARTNER: 0,
                            NEUTRAL: 0,
                            CAUTIOUS: 0,
                            ADVERSARY: 0,
                          },
                          praiseCount: 0,
                          accusationCount: 0,
                          neutralCount: 0,
                          powerLevel: 0,
                          sessions: [],
                        }))}
                        flows={mappedFlows}
                        projection={projectionInstance}
                        geographies={geographies}
                        visible={localShowRiskLayer}
                        highlightedCountry={highlightedCountry}
                      />
                    )}

                    {/* Bubble Markers removed */}
                  </>
                )}
              </Geographies>
            </ZoomableGroup>
          )}
        </ComposableMap>
      </svg>

      {/* Hover-based tooltip rendering portal */}
      {tooltip &&
        typeof window !== 'undefined' &&
        document.body &&
        createPortal(
          <div
            className="fixed z-50 pointer-events-none rounded-none shadow-2xl backdrop-blur-md"
            style={{
              top: tooltip.y,
              left: tooltip.x,
              transform: 'translate(15px, 15px)',
            }}
          >
            {tooltip.content}
          </div>,
          document.body,
        )}
    </div>
  );
};
