import * as d3 from 'd3';
import { ChevronLeft, ChevronRight, Filter, HelpCircle, Pause, Play } from 'lucide-react';
import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { RelationshipType } from '../../../types/visualization';
import { RELATIONSHIP_COLORS, sentimentToColor } from '../../../utils/visualizationHelpers';

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

interface NetworkGraphProps {
  nodes: CountryNode[];
  connections: CountryConnection[];
  selectedCountry: string | null;
  setSelectedCountry: (country: string | null) => void;
}

interface SimulationNode extends d3.SimulationNodeDatum {
  country_code: string;
  country_name: string;
  total_mentions: number;
  avg_sentiment: number;
  r: number;
}

interface SimulationLink extends d3.SimulationLinkDatum<SimulationNode> {
  source: string | SimulationNode;
  target: string | SimulationNode;
  interaction_count: number;
  avg_sentiment: number;
  relationship_type: string;
  affinity_score: number;
  from_country: string;
  to_country: string;
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
}

interface ResolvedSimulationLink extends Omit<SimulationLink, 'source' | 'target'> {
  source: SimulationNode;
  target: SimulationNode;
}

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

const getIso2Label = (countryCode: string) => {
  const code = countryCode.toUpperCase();
  return (iso3ToIso2[code] || countryCode.substring(0, 2)).toLowerCase();
};

const getDominantEmotion = (sentiment: number): string => {
  if (sentiment > 0.3) return 'cooperative';
  if (sentiment > 0.1) return 'constructive';
  if (sentiment > -0.1) return 'neutral_cautious';
  return 'concerned';
};

// Dominant relationship type for a country from its connections
const getDominantRelType = (countryCode: string, conns: CountryConnection[]): RelationshipType => {
  const countryConns = conns.filter(
    (c) => c.from_country === countryCode || c.to_country === countryCode,
  );
  if (countryConns.length === 0) return 'NEUTRAL';

  const counts: Record<string, number> = {};
  for (const c of countryConns) {
    const type = c.relationship_type as RelationshipType;
    counts[type] = (counts[type] || 0) + c.interaction_count;
  }

  let dominant: RelationshipType = 'NEUTRAL';
  let maxVal = -1;
  for (const type of Object.keys(counts) as RelationshipType[]) {
    if (counts[type] > maxVal) {
      maxVal = counts[type];
      dominant = type;
    }
  }
  return dominant;
};

export const NetworkGraph: React.FC<NetworkGraphProps> = ({
  nodes,
  connections,
  selectedCountry,
  setSelectedCountry,
}) => {
  // Container size
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Filter states
  const [selectedRelTypes, setSelectedRelTypes] = useState<RelationshipType[]>([
    'ALLY',
    'PARTNER',
    'NEUTRAL',
    'CAUTIOUS',
    'ADVERSARY',
  ]);
  const [localMinInteractions, setLocalMinInteractions] = useState<number>(2);
  const [clusteringMode, setClusteringMode] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);

  // Collapsible Legend Sidebar
  const [legendOpen, setLegendOpen] = useState<boolean>(true);

  // Interactivity States
  const [hoveredCountryCode, setHoveredCountryCode] = useState<string | null>(null);

  // SVG ref and simulation ref
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<SimulationNode, SimulationLink> | null>(null);

  // Resize Observer
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const rectWidth = entry.contentRect.width;
        const legendWidth = legendOpen ? 280 : 0;
        const width = Math.max(400, rectWidth - legendWidth);
        setDimensions({
          width,
          height: 600,
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [legendOpen]);

  // Filtered connections & nodes
  const filteredConnections = useMemo(() => {
    return connections.filter((conn) => {
      const type = conn.relationship_type as RelationshipType;
      const matchesRel = selectedRelTypes.includes(type);
      const matchesMin = conn.interaction_count >= localMinInteractions;
      return matchesRel && matchesMin;
    });
  }, [connections, selectedRelTypes, localMinInteractions]);

  const filteredNodes = useMemo(() => {
    const activeCountries = new Set<string>();
    for (const c of filteredConnections) {
      activeCountries.add(c.from_country);
      activeCountries.add(c.to_country);
    }
    // Include selectedCountry always so it doesn't disappear if filtered
    if (selectedCountry) {
      activeCountries.add(selectedCountry);
    }
    return nodes.filter((n) => activeCountries.has(n.country_code));
  }, [nodes, filteredConnections, selectedCountry]);

  // Keep track of active nodes lookup mapping for O(1) checks
  const nodeMap = useMemo(() => {
    const map: Record<string, CountryNode> = {};
    for (const n of filteredNodes) {
      map[n.country_code] = n;
    }
    return map;
  }, [filteredNodes]);

  // Check if country has adversary connections in the filtered list
  const hasAdversaryRelation = (countryCode: string) => {
    return filteredConnections.some(
      (c) =>
        (c.from_country === countryCode || c.to_country === countryCode) &&
        c.relationship_type === 'ADVERSARY',
    );
  };

  // Determine if a node is connected to the hovered node
  const isConnectedToHovered = (code: string) => {
    if (!hoveredCountryCode) return false;
    return filteredConnections.some(
      (c) =>
        (c.from_country === code && c.to_country === hoveredCountryCode) ||
        (c.from_country === hoveredCountryCode && c.to_country === code),
    );
  };

  // Calculate top stats for hovered node
  const hoveredNodeStats = useMemo(() => {
    if (!hoveredCountryCode || !nodeMap[hoveredCountryCode]) return null;
    const node = nodeMap[hoveredCountryCode];

    // Count relationship types in filtered connections for this node
    const counts: Record<RelationshipType, number> = {
      ALLY: 0,
      PARTNER: 0,
      NEUTRAL: 0,
      CAUTIOUS: 0,
      ADVERSARY: 0,
    };

    let totalFilteredInteractions = 0;
    for (const c of filteredConnections) {
      if (c.from_country === hoveredCountryCode || c.to_country === hoveredCountryCode) {
        const type = c.relationship_type as RelationshipType;
        if (counts[type] !== undefined) {
          counts[type]++;
        }
        totalFilteredInteractions += c.interaction_count;
      }
    }

    // Sort to show top relationship types
    const relationBreakdown = Object.entries(counts)
      .filter(([_, val]) => val > 0)
      .map(([key, val]) => `${key}: ${val}`)
      .join(' | ');

    return {
      name: node.country_name,
      code: node.country_code,
      interactions: totalFilteredInteractions || node.total_mentions,
      emotion: getDominantEmotion(node.avg_sentiment),
      sentiment: node.avg_sentiment,
      breakdown: relationBreakdown || 'No relationships active',
    };
  }, [hoveredCountryCode, nodeMap, filteredConnections]);

  // D3 Force Simulation Setup
  useEffect(() => {
    if (!svgRef.current) return;

    const { width, height } = dimensions;

    // Preserve coordinates from existing simulation nodes if available
    const existingNodesMap = new Map<string, { x: number; y: number }>();
    if (simulationRef.current) {
      const currentNodes = simulationRef.current.nodes();
      for (const node of currentNodes) {
        if (node.x !== undefined && node.y !== undefined) {
          existingNodesMap.set(node.country_code, { x: node.x, y: node.y });
        }
      }
    }

    // Initialize nodes with radius, name, and position
    const graphNodes: SimulationNode[] = filteredNodes.map((n) => {
      const r = Math.max(8, Math.min(40, Math.sqrt(n.total_mentions || 0) * 4));
      const pos = existingNodesMap.get(n.country_code);
      return {
        ...n,
        id: n.country_code,
        r,
        x: pos ? pos.x : width / 2 + (Math.random() - 0.5) * 100,
        y: pos ? pos.y : height / 2 + (Math.random() - 0.5) * 100,
      };
    });

    const graphLinks: SimulationLink[] = filteredConnections
      .map((c) => {
        // Make sure both source and target exist in active nodes
        const hasSource = graphNodes.some((gn) => gn.country_code === c.from_country);
        const hasTarget = graphNodes.some((gn) => gn.country_code === c.to_country);
        if (!hasSource || !hasTarget) return null;
        return {
          ...c,
          source: c.from_country,
          target: c.to_country,
        };
      })
      .filter((l) => l !== null) as SimulationLink[];

    let simulation = simulationRef.current;

    if (!simulation) {
      simulation = d3
        .forceSimulation<SimulationNode, SimulationLink>()
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force(
          'collision',
          d3.forceCollide<SimulationNode>().radius((d) => d.r + 8),
        );
      simulationRef.current = simulation;
    } else {
      simulation.force('center', d3.forceCenter(width / 2, height / 2));
    }

    simulation.nodes(graphNodes);

    const linkForce = d3
      .forceLink<SimulationNode, SimulationLink>(graphLinks)
      .id((d) => d.country_code)
      .distance((d) => {
        const dist: Record<string, number> = {
          ALLY: 80,
          PARTNER: 100,
          NEUTRAL: 140,
          CAUTIOUS: 120,
          ADVERSARY: 180,
        };
        return dist[d.relationship_type] ?? 140;
      })
      .strength((d) => (d.relationship_type === 'ADVERSARY' ? 0.2 : 0.5));

    simulation.force('link', linkForce);

    // Clustering forces
    if (clusteringMode) {
      simulation
        .force(
          'x',
          d3
            .forceX<SimulationNode>((d) => {
              const dominant = getDominantRelType(d.country_code, filteredConnections);
              const targets: Record<string, number> = {
                ALLY: width * 0.22,
                PARTNER: width * 0.38,
                NEUTRAL: width * 0.52,
                CAUTIOUS: width * 0.68,
                ADVERSARY: width * 0.82,
              };
              return targets[dominant] ?? width / 2;
            })
            .strength(0.65),
        )
        .force('y', d3.forceY<SimulationNode>(height / 2).strength(0.35));
    } else {
      simulation.force('x', null).force('y', null);
    }

    if (!isPaused) {
      simulation.alpha(1).restart();
    } else {
      simulation.stop();
    }

    // Helper to safely update node and link elements directly in DOM (60fps performance)
    const updatePositionsDOM = () => {
      d3.select(svgRef.current)
        .selectAll<SVGLineElement, ResolvedSimulationLink>('.link')
        .attr('x1', (d) => d.source.x ?? 0)
        .attr('y1', (d) => d.source.y ?? 0)
        .attr('x2', (d) =>
          d.source.x === d.target.x && d.source.y === d.target.y
            ? (d.source.x ?? 0) + 0.1
            : (d.target.x ?? 0),
        )
        .attr('y2', (d) =>
          d.source.x === d.target.x && d.source.y === d.target.y
            ? (d.source.y ?? 0) + 0.1
            : (d.target.y ?? 0),
        );

      d3.select(svgRef.current)
        .selectAll<SVGGElement, SimulationNode>('.node')
        .attr('transform', (d) => `translate(${d.x ?? 0}, ${d.y ?? 0})`);
    };

    simulation.on('tick', updatePositionsDOM);

    // Zoom and Pan behavior
    const zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 6])
      .on('zoom', (event) => {
        d3.select(svgRef.current).select('.zoom-g').attr('transform', event.transform);
      });

    d3.select<SVGSVGElement, unknown>(svgRef.current).call(zoomBehavior);

    // Drag handler definition
    const dragBehavior = d3
      .drag<SVGGElement, SimulationNode>()
      .on('start', (event, d) => {
        if (!event.active && !isPaused) {
          simulation.alphaTarget(0.3).restart();
        }
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
        // If simulation is paused, manually update positions to reflect drag in real-time
        if (isPaused) {
          d.x = event.x;
          d.y = event.y;
          updatePositionsDOM();
        }
      })
      .on('end', (event, d) => {
        if (!event.active && !isPaused) {
          simulation.alphaTarget(0);
        }
        d.fx = null;
        d.fy = null;
      });

    d3.select(svgRef.current).selectAll<SVGGElement, SimulationNode>('.node').call(dragBehavior);

    return () => {
      simulation.on('tick', null);
    };
  }, [filteredNodes, filteredConnections, dimensions, clusteringMode, isPaused]);

  const handleCheckboxChange = (type: RelationshipType) => {
    if (selectedRelTypes.includes(type)) {
      setSelectedRelTypes(selectedRelTypes.filter((t) => t !== type));
    } else {
      setSelectedRelTypes([...selectedRelTypes, type]);
    }
  };

  return (
    <div
      ref={containerRef}
      className="flex w-full min-h-[600px] h-[600px] bg-carbon-950 border border-carbon-550 relative overflow-hidden"
    >
      {/* Main Graph Area */}
      <div className="relative flex-1 h-full select-none">
        {/* D3 SVG Container */}
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          className="w-full h-full cursor-grab active:cursor-grabbing pointer-events-auto"
        >
          {/* Definitions for arrow markers */}
          <defs>
            {/* Marker for CAUTIOUS connection type */}
            <marker
              id="arrow-cautious"
              viewBox="0 0 10 10"
              refX="20"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={RELATIONSHIP_COLORS.CAUTIOUS} />
            </marker>
            {/* Marker for ADVERSARY connection type */}
            <marker
              id="arrow-adversary"
              viewBox="0 0 10 10"
              refX="20"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill={RELATIONSHIP_COLORS.ADVERSARY} />
            </marker>
          </defs>

          {/* Custom embedded animations keyframes stylesheet */}
          <style>
            {`
							@keyframes pulse-ring {
								0% { transform: scale(0.95); opacity: 0.5; }
								50% { transform: scale(1.05); opacity: 0.15; }
								100% { transform: scale(0.95); opacity: 0.5; }
							}
							.pulsing-halo {
								transform-origin: center;
								animation: pulse-ring 2s infinite ease-in-out;
							}
						`}
          </style>

          <g className="zoom-g">
            {/* Links (Edges) Layer */}
            <g className="links-layer">
              {filteredConnections.map((link, idx) => {
                const hasSource = nodeMap[link.from_country] !== undefined;
                const hasTarget = nodeMap[link.to_country] !== undefined;
                if (!hasSource || !hasTarget) return null;

                const type = link.relationship_type as RelationshipType;
                const isAdversary = type === 'ADVERSARY';
                const isCautious = type === 'CAUTIOUS';

                // Hover styling mechanics
                const isLinkHighlighted =
                  hoveredCountryCode === null ||
                  link.from_country === hoveredCountryCode ||
                  link.to_country === hoveredCountryCode;

                const opacity = hoveredCountryCode === null ? 0.6 : isLinkHighlighted ? 1.0 : 0.15;

                // Line thickness based on formula: Math.log(interactionCount + 1) * 1.5
                const strokeWidth = Math.log(link.interaction_count + 1) * 1.5;

                // Direction indicator marker bindings
                let markerEnd = undefined;
                if (isAdversary) markerEnd = 'url(#arrow-adversary)';
                else if (isCautious) markerEnd = 'url(#arrow-cautious)';

                return (
                  <line
                    key={`link-${idx}-${link.from_country}-${link.to_country}`}
                    className="link transition-all duration-200"
                    stroke={RELATIONSHIP_COLORS[type]}
                    strokeWidth={strokeWidth}
                    strokeOpacity={opacity}
                    strokeDasharray={isAdversary ? '3,3' : undefined}
                    markerEnd={markerEnd}
                  />
                );
              })}
            </g>

            {/* Nodes Layer */}
            <g className="nodes-layer">
              {filteredNodes.map((node) => {
                const r = Math.max(8, Math.min(40, Math.sqrt(node.total_mentions || 0) * 4));

                const isDimmed =
                  hoveredCountryCode !== null &&
                  node.country_code !== hoveredCountryCode &&
                  !isConnectedToHovered(node.country_code);

                const opacity = isDimmed ? 0.2 : 1.0;

                const dominant = getDominantRelType(node.country_code, connections);
                const strokeColor = RELATIONSHIP_COLORS[dominant];

                const isNodeHovered = node.country_code === hoveredCountryCode;
                const isNodeSelected = node.country_code === selectedCountry;
                const strokeWidth = isNodeHovered || isNodeSelected ? 4 : 2;

                const hasAdversary = hasAdversaryRelation(node.country_code);

                return (
                  <g
                    key={`node-${node.country_code}`}
                    className="node cursor-pointer transition-all duration-200"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedCountry(
                        selectedCountry === node.country_code ? null : node.country_code,
                      );
                    }}
                    onMouseEnter={() => setHoveredCountryCode(node.country_code)}
                    onMouseLeave={() => setHoveredCountryCode(null)}
                    style={{ opacity }}
                  >
                    {/* Pulsing Adversary Halo Ring */}
                    {hasAdversary && (
                      <circle
                        r={r + 6}
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth={1.5}
                        className="pulsing-halo"
                      />
                    )}

                    {/* Outer Glow / shadow on hover */}
                    {(isNodeHovered || isNodeSelected) && (
                      <circle r={r + 3} fill="none" stroke={strokeColor} opacity={0.3} />
                    )}

                    {/* Inner circle fill and boundary */}
                    <circle
                      r={r}
                      fill={sentimentToColor(node.avg_sentiment)}
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                    />

                    {/* Lowercase ISO-A2 Code inside the node */}
                    <text
                      textAnchor="middle"
                      dy=".3em"
                      fill="#ffffff"
                      fontSize={r > 12 ? '9px' : '7px'}
                      fontWeight="bold"
                      className="pointer-events-none select-none font-mono"
                    >
                      {getIso2Label(node.country_code)}
                    </text>
                  </g>
                );
              })}
            </g>
          </g>
        </svg>

        {/* Floating Control Panel (Graph sağ üstü) */}
        <div className="absolute top-4 right-4 bg-carbon-900/95 border border-carbon-700/80 p-4 w-72 shadow-2xl backdrop-blur-md z-10 pointer-events-auto select-text font-mono text-[10px]">
          <div className="space-y-4">
            {/* Relationship Filters */}
            <div>
              <div className="text-carbon-400 font-bold border-b border-carbon-800 pb-1 mb-2 flex items-center gap-1.5 uppercase tracking-wider">
                <Filter className="w-3.5 h-3.5 text-indigo-400" />
                İlişki Filtresi
              </div>
              <div className="grid grid-cols-2 gap-y-2 gap-x-1">
                {(Object.keys(RELATIONSHIP_COLORS) as RelationshipType[]).map((type) => (
                  <label
                    key={type}
                    className="flex items-center gap-2 cursor-pointer text-carbon-300 hover:text-carbon-100 transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={selectedRelTypes.includes(type)}
                      onChange={() => handleCheckboxChange(type)}
                      className="w-3.5 h-3.5 bg-carbon-950 border border-carbon-550 text-indigo-500 rounded focus:ring-0 focus:ring-offset-0 cursor-pointer"
                    />
                    <span
                      className="w-2 h-2 rounded-full inline-block flex-shrink-0"
                      style={{ backgroundColor: RELATIONSHIP_COLORS[type] }}
                    />
                    <span>{type}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Min Interaction Slider */}
            <div>
              <div className="flex justify-between items-center text-carbon-400 font-bold border-b border-carbon-800 pb-1 mb-2 uppercase tracking-wider">
                <span>Min. Etkileşim</span>
                <span className="text-indigo-400 font-mono text-[11px]">
                  {localMinInteractions}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="1"
                  max="15"
                  value={localMinInteractions}
                  onChange={(e) => setLocalMinInteractions(Number(e.target.value))}
                  className="flex-1 accent-indigo-500 bg-carbon-950 rounded-none h-1 border border-carbon-800 appearance-none cursor-pointer"
                />
              </div>
            </div>

            {/* Clustering Mode Toggle */}
            <div>
              <div className="flex justify-between items-center text-carbon-400 font-bold border-b border-carbon-800 pb-1 mb-2 uppercase tracking-wider">
                <span>Kümelenme Modu</span>
                <span
                  className={`text-[9px] px-1.5 py-0.5 rounded font-bold font-mono ${
                    clusteringMode
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                      : 'bg-carbon-950 text-carbon-400 border border-carbon-800'
                  }`}
                >
                  {clusteringMode ? 'ON' : 'OFF'}
                </span>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-carbon-400 text-[9px]">
                  İlişkiye göre kolonlara yerleştir
                </span>
                <button
                  onClick={() => setClusteringMode(!clusteringMode)}
                  className="relative inline-flex h-4 w-9 shrink-0 cursor-pointer items-center rounded-full border border-carbon-600 bg-carbon-950 transition-colors focus-visible:outline-none"
                >
                  <span
                    className={`pointer-events-none block h-2.5 w-2.5 rounded-full transition-transform ${
                      clusteringMode
                        ? 'translate-x-5 bg-emerald-500'
                        : 'translate-x-1 bg-carbon-400'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Pause/Resume Simulation */}
            <div className="pt-2 border-t border-carbon-800">
              <button
                onClick={() => setIsPaused(!isPaused)}
                className={`w-full flex items-center justify-center gap-2 py-1.5 px-3 rounded-none text-xs border transition-all ${
                  isPaused
                    ? 'bg-indigo-950/20 border-indigo-700/50 text-indigo-400 hover:bg-indigo-950/40'
                    : 'bg-carbon-800 border-carbon-550 text-carbon-200 hover:bg-carbon-700 hover:text-carbon-50'
                }`}
              >
                {isPaused ? (
                  <>
                    <Play className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Simülasyonu Başlat</span>
                  </>
                ) : (
                  <>
                    <Pause className="w-3.5 h-3.5" />
                    <span>Simülasyonu Dondur</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {hoveredNodeStats && (
          <div className="absolute top-4 left-4 bg-carbon-950/95 border border-carbon-700/80 p-3.5 shadow-2xl z-10 w-72 pointer-events-none select-none rounded backdrop-blur-sm">
            <div className="flex flex-col gap-2.5 text-[11px] leading-normal text-carbon-100">
              <div className="flex items-center justify-between border-b border-carbon-800 pb-2">
                <span className="font-bold text-xs uppercase tracking-wider text-carbon-50 truncate max-w-[180px]">
                  {hoveredNodeStats.name}
                </span>
                <span className="text-[9px] bg-carbon-800 text-carbon-400 px-1.5 py-0.5 rounded font-mono uppercase tracking-wider">
                  Node Stats
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-carbon-400">Etkileşim:</span>
                <span className="font-semibold text-indigo-400 font-mono">
                  {hoveredNodeStats.interactions} segment
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-carbon-400">Dominant Duygu:</span>
                <span className="font-semibold text-emerald-400">{hoveredNodeStats.emotion}</span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-carbon-400">Ort. Sentiment:</span>
                <span
                  className="font-bold font-mono"
                  style={{ color: sentimentToColor(hoveredNodeStats.sentiment) }}
                >
                  {hoveredNodeStats.sentiment >= 0 ? '+' : ''}
                  {hoveredNodeStats.sentiment.toFixed(2)}
                </span>
              </div>

              {hoveredNodeStats.breakdown && (
                <div className="mt-1 pt-2 border-t border-carbon-800/60 text-carbon-400 text-[10px] leading-relaxed italic">
                  {hoveredNodeStats.breakdown}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Collapsible NetworkLegend panel (Sağda) */}
      <div
        className={`border-l border-carbon-550 bg-carbon-900 flex flex-col transition-all duration-300 relative ${
          legendOpen ? 'w-[280px]' : 'w-0'
        }`}
      >
        {/* Sidebar toggle tab */}
        <button
          onClick={() => setLegendOpen(!legendOpen)}
          className="absolute top-1/2 -left-4 transform -translate-y-1/2 bg-carbon-900 border-y border-l border-carbon-550 text-carbon-400 hover:text-carbon-200 py-3 px-0.5 rounded-l flex items-center justify-center cursor-pointer z-25 focus:outline-none"
          title={legendOpen ? 'Açıklamayı Kapat' : 'Açıklamayı Göster'}
        >
          {legendOpen ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <ChevronLeft className="w-3.5 h-3.5" />
          )}
        </button>

        {/* Sidebar Content */}
        {legendOpen && (
          <div className="flex-1 p-5 overflow-y-auto space-y-5 select-text font-mono text-[10px]">
            <div>
              <div className="text-carbon-50 font-bold text-[11px] mb-1 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-indigo-400" />
                DİPLOMATİK AĞ GRAFİĞİ
              </div>
              <p className="text-carbon-400 leading-relaxed text-[9px] mt-1.5">
                Bu grafik, ülkeler arası ikili diplomatik ilişkileri bir ağ yapısı olarak sunar. Her
                düğüm (node) bir ülkeyi, bağlantı (edge) ise bu ülkeler arasındaki diplomatik akışı
                temsil eder.
              </p>
            </div>

            {/* Sentiment Scale */}
            <div className="space-y-2">
              <div className="text-carbon-300 font-bold uppercase tracking-wider border-b border-carbon-800 pb-1">
                SENTIMENT SKALASI (DOLGU)
              </div>
              <div className="w-full h-3 bg-gradient-to-r from-[#7f1d1d] via-[#1e293b] to-[#064e3b] border border-carbon-800" />
              <div className="flex justify-between text-[9px] text-carbon-400 font-mono">
                <span>Negatif (-1)</span>
                <span>Nötr (0)</span>
                <span>Pozitif (+1)</span>
              </div>
            </div>

            {/* Relationship Colors */}
            <div className="space-y-2">
              <div className="text-carbon-300 font-bold uppercase tracking-wider border-b border-carbon-800 pb-1">
                DOMİNANT İLİŞKİ TİPİ (SINIR)
              </div>
              <div className="space-y-2 font-mono text-[9px]">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#10b981] inline-block border border-carbon-800" />
                  <span className="text-carbon-300">ALLY (Müttefik)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#3b82f6] inline-block border border-carbon-800" />
                  <span className="text-carbon-300">PARTNER (Ortak)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#6b7280] inline-block border border-carbon-800" />
                  <span className="text-carbon-300">NEUTRAL (Tarafsız)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#f59e0b] inline-block border border-carbon-800" />
                  <span className="text-carbon-300">CAUTIOUS (Mesafeli)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444] inline-block border border-carbon-800 animate-pulse" />
                  <span className="text-carbon-300">ADVERSARY (Karşıt)</span>
                </div>
              </div>
            </div>

            {/* Connections description */}
            <div className="space-y-2">
              <div className="text-carbon-300 font-bold uppercase tracking-wider border-b border-carbon-800 pb-1">
                BAĞLANTI ÖZELLİKLERİ
              </div>
              <div className="space-y-2 text-[9px] leading-relaxed text-carbon-400">
                <div>
                  <b className="text-carbon-200">Çizgi Kalınlığı:</b> İkili etkileşim hacmi ile
                  logaritmik olarak artar.
                </div>
                <div>
                  <b className="text-carbon-200">Kırmızı Pulsing Halka:</b> Karşıt (ADVERSARY)
                  ilişkisi bulunan riskli ülkelerin etrafında kırmızı titreşim halkası gösterilir.
                </div>
                <div>
                  <b className="text-carbon-200">Ok Başları:</b> Mesafeli (CAUTIOUS) ve Karşıt
                  (ADVERSARY) ilişkilerde akışın yönünü belirtir.
                </div>
                <div>
                  <b className="text-carbon-200">Kesikli Kırmızı Hat:</b> Karşıt (ADVERSARY)
                  ilişkiler kalın ve kesikli kırmızı çizgiyle gösterilir.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
