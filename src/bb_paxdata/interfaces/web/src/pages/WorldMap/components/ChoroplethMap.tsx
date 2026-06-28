// src/bb_paxdata/interfaces/web/src/pages/WorldMap/components/ChoroplethMap.tsx

import { geoCentroid, geoMercator, geoNaturalEarth1, geoOrthographic } from 'd3-geo';
import { interpolateRgb } from 'd3-interpolate';
import { scaleLinear } from 'd3-scale';
import { Zap } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ComposableMap,
  Geographies,
  Geography,
  Graticule,
  Marker,
  Sphere,
  ZoomableGroup,
} from 'react-simple-maps';
import { isoNumericToAlpha3 } from '../../../data/isoNumericToAlpha3';
import type {
  BilateralFlow,
  DominantEmotion,
  RelationshipType,
} from '../../../types/visualization';
import { RELATIONSHIP_COLORS, sentimentToColor } from '../../../utils/visualizationHelpers';
import { BilateralArcLayer } from './BilateralArcLayer';
import { MapLegend } from './MapLegend';
import { MapProjectionSwitcher } from './MapProjectionSwitcher';
import { RiskHotspotLayer } from './RiskHotspotLayer';

// Path to the downloaded local TopoJSON file in the public directory
const geoUrl = '/world-110m.json';

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

type ProjectionType = 'naturalEarth' | 'mercator' | 'orthographic';

interface ChoroplethMapProps {
  width?: number; // default: container width
  height?: number; // default: 520
  projection?: ProjectionType; // switcher
  nodes: CountryNode[];
  connections: CountryConnection[];
  setSelectedCountry: (country: string | null) => void;
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

// Generates textual visual blocks for sentiment level (range -1.0 to 1.0 represented by 6 blocks)
const getSentimentBar = (score: number): string => {
  const pct = (score + 1) / 2; // Normalize to [0, 1]
  const totalBlocks = 6;
  const filledCount = pct * totalBlocks;
  let bar = '';
  for (let i = 0; i < totalBlocks; i++) {
    if (i < Math.floor(filledCount)) {
      bar += '█';
    } else if (i === Math.floor(filledCount)) {
      const rem = filledCount - Math.floor(filledCount);
      if (rem > 0.66) bar += '█';
      else if (rem > 0.33) bar += '▓';
      else if (rem > 0) bar += '▒';
      else bar += '░';
    } else {
      bar += '░';
    }
  }
  return bar;
};

// Map sentiment level to custom dynamic dominant emotion
const getDominantEmotion = (sentiment: number): DominantEmotion => {
  if (sentiment > 0.3) return 'cooperative';
  if (sentiment > 0.1) return 'constructive';
  if (sentiment > -0.1) return 'neutral_cautious';
  return 'concerned';
};

// Memoized bubble marker component to prevent unnecessary re-renders
const BubbleMarker = React.memo(
  ({
    node,
    coords,
    radius,
    bubbleColor,
    borderColor,
    opacity,
    setHighlightedCountry,
    showTooltip,
    moveTooltip,
    hideTooltip,
    setSelectedCountry,
    renderCountryTooltip,
  }: {
    node: CountryNode;
    coords: [number, number];
    radius: number;
    bubbleColor: string;
    borderColor: string;
    opacity: number;
    setHighlightedCountry: (country: string | null) => void;
    showTooltip: (e: React.MouseEvent, content: React.ReactNode) => void;
    moveTooltip: (e: React.MouseEvent) => void;
    hideTooltip: () => void;
    setSelectedCountry: (country: string) => void;
    renderCountryTooltip: (countryCode: string) => React.ReactNode;
  }) => {
    return (
      <Marker key={`bubble-${node.country_code}`} coordinates={coords}>
        <circle
          r={radius}
          fill={bubbleColor}
          fillOpacity={opacity}
          stroke={borderColor}
          strokeWidth={2}
          strokeOpacity={opacity}
          className="bubble-marker"
          onMouseEnter={(e) => {
            setHighlightedCountry(node.country_code);
            showTooltip(e, renderCountryTooltip(node.country_code));
          }}
          onMouseMove={moveTooltip}
          onMouseLeave={() => {
            setHighlightedCountry(null);
            hideTooltip();
          }}
          onClick={() => setSelectedCountry(node.country_code)}
        />
      </Marker>
    );
  },
);

BubbleMarker.displayName = 'BubbleMarker';

export const ChoroplethMap: React.FC<ChoroplethMapProps> = ({
  width,
  height = 520,
  projection = 'naturalEarth',
  nodes,
  connections,
  setSelectedCountry,
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

  // Reset viewport settings on projection switcher activation
  useEffect(() => {
    if (localProjection === 'mercator') {
      setPosition({ coordinates: [20, 48], zoom: 1.2 });
    } else if (localProjection === 'orthographic') {
      setPosition({ coordinates: [0, 0], zoom: 1 });
      setRotation([0, 0, 0]);
    } else {
      setPosition({ coordinates: [0, 10], zoom: 1 });
    }
  }, [localProjection]);

  // ResizeObserver state logic to compute width responsive container width
  const [dimensions, setDimensions] = useState({
    width: width || 800,
    height: height,
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
        setDimensions({
          width: width || rectWidth || 800,
          height: height,
        });
      }
    });
    observer.observe(containerRef.current);
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
    showAllFlows !== undefined ? showAllFlows : false,
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

  // Custom D3 Projection instance matching position & rotation
  const projectionInstance = useMemo(() => {
    let proj;
    if (localProjection === 'orthographic') {
      proj = geoOrthographic()
        .scale(230 * position.zoom)
        .rotate(rotation as [number, number, number]);
    } else if (localProjection === 'mercator') {
      proj = geoMercator()
        .scale(450)
        .center([20, 48] as [number, number]);
    } else {
      proj = geoNaturalEarth1()
        .scale(145)
        .center([0, 10] as [number, number]);
    }
    return proj.translate([dimensions.width / 2, dimensions.height / 2]);
  }, [localProjection, rotation, position.zoom, dimensions.width, dimensions.height]);

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

  // Compute maximum interactions among all nodes for bubble scaling
  const maxInteractions = useMemo(() => {
    if (nodes.length === 0) return 1;
    return Math.max(...nodes.map((n) => n.total_mentions), 1);
  }, [nodes]);

  // Memoize bubble data to avoid recalculating on every render
  const bubbleData = useMemo(() => {
    // Bubble radius calculation (6px to 28px) with square root scaling
    const getBubbleRadius = (mentions: number) => {
      const minRadius = 6;
      const maxRadius = 28;
      const ratio = Math.sqrt(mentions / maxInteractions);
      return minRadius + (maxRadius - minRadius) * ratio;
    };

    return nodes.map((node) => ({
      node,
      radius: getBubbleRadius(node.total_mentions),
      bubbleColor: sentimentToColor(node.avg_sentiment),
      dominantRel: getDominantRelType(node.country_code, connections),
    }));
  }, [nodes, connections, maxInteractions]);

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
          className="flex flex-col border border-carbon-600 bg-[#0a0f1a] text-carbon-100 p-3 min-w-[200px]"
          style={{
            fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
            fontSize: '11px',
            lineHeight: '1.4',
          }}
        >
          <div className="flex items-center gap-1.5 font-bold text-sm text-carbon-50 border-b border-carbon-700 pb-1.5 mb-1.5">
            <span>{getFlagEmoji(countryCode)}</span>
            <span>{countryCode}</span>
          </div>
          <span className="text-carbon-500 italic text-[10px]">Etkileşim verisi yok</span>
        </div>
      );
    }

    const sentimentColor = sentimentToColor(node.avg_sentiment);
    const relColor = RELATIONSHIP_COLORS[dominantRel] || '#9ca3af';
    const dominantEmotion = getDominantEmotion(node.avg_sentiment);
    const sessionCount = Math.max(1, Math.min(8, Math.round(node.total_mentions / 12)));

    return (
      <div
        className="flex flex-col border border-carbon-600 bg-[#0a0f1a] text-carbon-100 p-3.5 min-w-[230px] shadow-2xl"
        style={{
          fontFamily: "'JetBrains Mono', 'Space Mono', monospace",
          fontSize: '11px',
          lineHeight: '1.4',
        }}
      >
        <div className="flex items-center gap-2 font-bold text-xs text-carbon-50 border-b border-carbon-700 pb-1.5 mb-2">
          <span className="text-sm leading-none">{getFlagEmoji(node.country_code)}</span>
          <span className="truncate">{node.country_name}</span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-carbon-400">Sentiment:</span>
          <span className="font-semibold flex items-center gap-2">
            <span style={{ color: sentimentColor }}>
              {node.avg_sentiment > 0 ? '+' : ''}
              {node.avg_sentiment.toFixed(2)}
            </span>
            <span className="text-carbon-500 tracking-tighter">
              {getSentimentBar(node.avg_sentiment)}
            </span>
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
        <div className="text-[10px] text-indigo-400 font-semibold mt-2.5 pt-1.5 border-t border-carbon-800 text-center select-none cursor-pointer">
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
    if (localProjection === 'orthographic') {
      return {
        scale: 230 * position.zoom,
        rotate: rotation,
      };
    } else if (localProjection === 'mercator') {
      // Focused regional view of Europe/Middle-East
      return {
        scale: 450,
        center: [20, 48] as [number, number],
      };
    } else {
      // NaturalEarth global projection
      return {
        scale: 145,
        center: [0, 10] as [number, number],
      };
    }
  }, [localProjection, rotation, position.zoom]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden select-none bg-[#0a0f1a]"
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
        .bubble-marker {
          transform-origin: center;
          transform-box: fill-box;
          cursor: pointer;
          transition: transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275), fill-opacity 0.2s ease-in-out;
          will-change: transform;
        }
        .bubble-marker:hover {
          transform: scale(1.3);
          fill-opacity: 1.0 !important;
        }
        .rsm-geography {
          will-change: transform;
        }
        @media (prefers-reduced-motion: reduce) {
          .animate-pulse-ring {
            animation: none !important;
          }
          .bubble-marker {
            transition: none !important;
            transform: none !important;
          }
          .bubble-marker:hover {
            transform: none !important;
          }
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
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2 pointer-events-auto bg-carbon-900/90 border border-carbon-700/80 p-3 shadow-2xl backdrop-blur-md max-w-xs text-xs font-mono text-carbon-200">
        <div className="font-bold text-white flex items-center gap-1.5 mb-1">
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

      {/* Legend inside map component (Bottom Left) */}
      <MapLegend />

      {/* Zoom controls inside map component (Bottom Right) */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-1 bg-carbon-900/90 border border-carbon-700/80 p-1.5 shadow-2xl backdrop-blur-md z-10 pointer-events-auto">
        <button
          onClick={zoomIn}
          type="button"
          className="w-8 h-8 flex items-center justify-center border border-carbon-700 text-carbon-300 hover:text-white hover:bg-carbon-800 font-bold text-sm select-none transition-all duration-150 rounded-none bg-carbon-950/70"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          +
        </button>
        <button
          onClick={zoomOut}
          type="button"
          className="w-8 h-8 flex items-center justify-center border border-carbon-700 text-carbon-300 hover:text-white hover:bg-carbon-800 font-bold text-sm select-none transition-all duration-150 rounded-none bg-carbon-950/70"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          -
        </button>
        <button
          onClick={resetZoom}
          type="button"
          className="w-8 h-8 flex items-center justify-center border border-carbon-700 text-carbon-300 hover:text-white hover:bg-carbon-800 font-bold text-sm select-none transition-all duration-150 rounded-none bg-carbon-950/70"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
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
        className={`${isGlobe ? 'cursor-grab active:cursor-grabbing' : 'outline-none'}`}
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
            <Sphere id="rsm-sphere" fill="#0d1b2a" stroke="#2a3a4f" strokeWidth={0.5} />
          ) : (
            // Flat okyanus backplate
            <rect width={dimensions.width} height={dimensions.height} fill="#0d1b2a" />
          )}

          {/* Dynamic map geometries layout */}
          {isGlobe ? (
            // Globe orthographic rendering (we do not use ZoomableGroup to support standard rotation)
            <>
              <Graticule stroke="#1a2332" strokeOpacity={0.2} strokeWidth={0.5} />
              <Geographies geography={geoUrl}>
                {({ geographies }: { geographies: GeoJSON.Feature[] }) => (
                  <>
                    {/* Country Geographies */}
                    {geographies.map((geo) => {
                      const countryCode = geo.id ? isoNumericToAlpha3[geo.id] : undefined;
                      if (!countryCode) return null;

                      const node = nodes.find((n) => n.country_code === countryCode);
                      const isHighlighted = highlightedCountry === countryCode;
                      const hasHighlight = highlightedCountry !== null;

                      const opacity = hasHighlight ? (isHighlighted ? 1.0 : 0.3) : 1.0;
                      const fillColor = node ? choroplethScale(node.avg_sentiment) : '#1a2332';

                      const isActive = node !== undefined;
                      const strokeColor = isActive ? '#ffffff' : '#2a3a4f';
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

                    {/* Bilateral Arcs Connection Layer */}
                    <BilateralArcLayer
                      flows={mappedFlows}
                      projection={projectionInstance}
                      highlightedCountry={highlightedCountry}
                      visibleTypes={localVisibleTypes}
                      showAllFlows={localShowAllFlows}
                      onArcHover={handleArcHover}
                      geographies={geographies}
                      nodes={nodes}
                    />

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

                    {/* Bubble Markers */}
                    {bubbleData.map(({ node, radius, bubbleColor, dominantRel }) => {
                      const geo = geographies.find(
                        (g) => g.id && isoNumericToAlpha3[g.id] === node.country_code,
                      );
                      let coords: [number, number] = [node.longitude, node.latitude];
                      if (geo) {
                        try {
                          const c = geoCentroid(geo);
                          if (c && !isNaN(c[0]) && !isNaN(c[1])) coords = c;
                        } catch (_err) {
                          // geoCentroid failed; keep default coords
                        }
                      }

                      const borderColor = RELATIONSHIP_COLORS[dominantRel] || '#6b7280';

                      const isHighlighted = highlightedCountry === node.country_code;
                      const hasHighlight = highlightedCountry !== null;
                      const opacity = hasHighlight ? (isHighlighted ? 0.95 : 0.2) : 0.75;

                      return (
                        <BubbleMarker
                          key={`bubble-${node.country_code}`}
                          node={node}
                          coords={coords}
                          radius={radius}
                          bubbleColor={bubbleColor}
                          borderColor={borderColor}
                          opacity={opacity}
                          setHighlightedCountry={setHighlightedCountry}
                          showTooltip={showTooltip}
                          moveTooltip={moveTooltip}
                          hideTooltip={hideTooltip}
                          setSelectedCountry={setSelectedCountry}
                          renderCountryTooltip={renderCountryTooltip}
                        />
                      );
                    })}
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
              <Graticule stroke="#1a2332" strokeOpacity={0.2} strokeWidth={0.5} />
              <Geographies geography={geoUrl}>
                {({ geographies }: { geographies: GeoJSON.Feature[] }) => (
                  <>
                    {/* Country Geographies */}
                    {geographies.map((geo) => {
                      const countryCode = geo.id ? isoNumericToAlpha3[geo.id] : undefined;
                      if (!countryCode) return null;

                      const node = nodes.find((n) => n.country_code === countryCode);
                      const isHighlighted = highlightedCountry === countryCode;
                      const hasHighlight = highlightedCountry !== null;

                      const opacity = hasHighlight ? (isHighlighted ? 1.0 : 0.3) : 1.0;
                      const fillColor = node ? choroplethScale(node.avg_sentiment) : '#1a2332';

                      const isActive = node !== undefined;
                      const strokeColor = isActive ? '#ffffff' : '#2a3a4f';
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

                    {/* Bilateral Arcs Connection Layer */}
                    <BilateralArcLayer
                      flows={mappedFlows}
                      projection={projectionInstance}
                      highlightedCountry={highlightedCountry}
                      visibleTypes={localVisibleTypes}
                      showAllFlows={localShowAllFlows}
                      onArcHover={handleArcHover}
                      geographies={geographies}
                      nodes={nodes}
                    />

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

                    {/* Bubble Markers */}
                    {bubbleData.map(({ node, radius, bubbleColor, dominantRel }) => {
                      const geo = geographies.find(
                        (g) => g.id && isoNumericToAlpha3[g.id] === node.country_code,
                      );
                      let coords: [number, number] = [node.longitude, node.latitude];
                      if (geo) {
                        try {
                          const c = geoCentroid(geo);
                          if (c && !isNaN(c[0]) && !isNaN(c[1])) coords = c;
                        } catch (_err) {
                          // geoCentroid failed; keep default coords
                        }
                      }

                      const borderColor = RELATIONSHIP_COLORS[dominantRel] || '#6b7280';

                      const isHighlighted = highlightedCountry === node.country_code;
                      const hasHighlight = highlightedCountry !== null;
                      const opacity = hasHighlight ? (isHighlighted ? 0.95 : 0.2) : 0.75;

                      return (
                        <BubbleMarker
                          key={`bubble-${node.country_code}`}
                          node={node}
                          coords={coords}
                          radius={radius}
                          bubbleColor={bubbleColor}
                          borderColor={borderColor}
                          opacity={opacity}
                          setHighlightedCountry={setHighlightedCountry}
                          showTooltip={showTooltip}
                          moveTooltip={moveTooltip}
                          hideTooltip={hideTooltip}
                          setSelectedCountry={setSelectedCountry}
                          renderCountryTooltip={renderCountryTooltip}
                        />
                      );
                    })}
                  </>
                )}
              </Geographies>
            </ZoomableGroup>
          )}
        </ComposableMap>
      </svg>

      {/* Hover-based tooltip rendering portal */}
      {tooltip &&
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
