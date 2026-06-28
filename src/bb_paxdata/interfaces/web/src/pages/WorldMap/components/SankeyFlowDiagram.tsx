import { useQuery } from '@tanstack/react-query';
import { Activity, Calendar, ChevronDown, Filter, Info, RefreshCw, X } from 'lucide-react';
import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';
import { getReferenceFlows, getSessionTimeline } from '../../../api/visualizationApi';
import type { ReferenceContext } from '../../../types/visualization';
import { sentimentToColor } from '../../../utils/visualizationHelpers';

interface SankeyFlowDiagramProps {
  height?: number;
}

interface SankeyNode {
  id: string;
  name: string;
  layer: number;
  type: 'speaker' | 'context' | 'referenced';
}

interface SankeyLink {
  source: string | SankeyNode;
  target: string | SankeyNode;
  value: number;
  avgSentiment: number;
  sessions: string[];
}

interface SankeyLayoutNode extends SankeyNode {
  x0?: number;
  x1?: number;
  y0?: number;
  y1?: number;
  value?: number;
  depth?: number;
  index?: number;
}

interface SankeyLayoutLink extends Omit<SankeyLink, 'source' | 'target'> {
  source: SankeyLayoutNode;
  target: SankeyLayoutNode;
  width?: number;
  index?: number;
  y0?: number;
  y1?: number;
}

export const SankeyFlowDiagram: React.FC<SankeyFlowDiagramProps> = ({ height = 600 }) => {
  // Filters State
  const [selectedSession, setSelectedSession] = useState<string>('');
  const [selectedContexts, setSelectedContexts] = useState<ReferenceContext[]>([
    'PRAISE',
    'ACCUSATION',
    'NEUTRAL_MENTION',
  ]);
  const [minConnectionCount, setMinConnectionCount] = useState<number>(2);
  const [countrySearch, setCountrySearch] = useState<string>('');
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);

  // Hover states for interactions
  const [hoveredLinkIdx, setHoveredLinkIdx] = useState<number | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // DOM Elements Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const sessionDropdownRef = useRef<HTMLDivElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  const [sessionDropdownOpen, setSessionDropdownOpen] = useState<boolean>(false);
  const [dimensions, setDimensions] = useState({ width: 800, height: height });

  // Handle outside clicks to close overlays
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        sessionDropdownRef.current &&
        !sessionDropdownRef.current.contains(event.target as Node)
      ) {
        setSessionDropdownOpen(false);
      }
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
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
        setDimensions({
          width: Math.max(400, entry.contentRect.width),
          height: height,
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [height]);

  // Fetch Session Timeline dropdown list
  const sessionsQuery = useQuery({
    queryKey: ['sessions-timeline'],
    queryFn: () => getSessionTimeline(),
  });

  // Fetch Reference Flows
  const flowsQuery = useQuery({
    queryKey: ['reference-flows', selectedSession],
    queryFn: () => getReferenceFlows(selectedSession ? { sessionId: selectedSession } : undefined),
  });

  // Client-side filtering of reference flows
  const filteredFlows = useMemo(() => {
    const data = flowsQuery.data || [];
    return data.filter((flow) => {
      // 1. Context check
      if (!selectedContexts.includes(flow.context)) return false;

      // 2. Minimum Connection Count check
      if (flow.count < minConnectionCount) return false;

      // 3. Country text search query
      if (countrySearch.trim() !== '') {
        const query = countrySearch.toLowerCase().trim();
        const matchSpeaker = flow.speakerCountry.toLowerCase().includes(query);
        const matchReferenced = flow.referencedCountry.toLowerCase().includes(query);
        if (!matchSpeaker && !matchReferenced) return false;
      }

      return true;
    });
  }, [flowsQuery.data, selectedContexts, minConnectionCount, countrySearch]);

  // Auto-complete suggestions list for countries
  const countrySuggestions = useMemo(() => {
    const data = flowsQuery.data || [];
    const countries = new Set<string>();
    for (const f of data) {
      countries.add(f.speakerCountry);
      countries.add(f.referencedCountry);
    }
    const uniqueList = Array.from(countries).sort();

    if (countrySearch.trim() === '') {
      return uniqueList.slice(0, 8);
    }
    const query = countrySearch.toLowerCase().trim();
    return uniqueList.filter((c) => c.toLowerCase().includes(query)).slice(0, 8);
  }, [flowsQuery.data, countrySearch]);

  // Generate nodes and links lists
  const { nodesList, linksList } = useMemo(() => {
    const speakerSet = new Set<string>();
    const contextSet = new Set<ReferenceContext>();
    const referencedSet = new Set<string>();

    for (const f of filteredFlows) {
      speakerSet.add(f.speakerCountry);
      contextSet.add(f.context);
      referencedSet.add(f.referencedCountry);
    }

    // Nodes Construction
    const speakerNodes: SankeyNode[] = Array.from(speakerSet)
      .sort()
      .map((name) => ({
        id: `s_${name}`,
        name,
        layer: 0,
        type: 'speaker',
      }));

    const contextNodes: SankeyNode[] = Array.from(contextSet)
      .sort()
      .map((name) => ({
        id: `c_${name}`,
        name,
        layer: 1,
        type: 'context',
      }));

    const referencedNodes: SankeyNode[] = Array.from(referencedSet)
      .sort()
      .map((name) => ({
        id: `r_${name}`,
        name,
        layer: 2,
        type: 'referenced',
      }));

    const nodes = [...speakerNodes, ...contextNodes, ...referencedNodes];

    // Links Construction
    // 1. Speaker -> Context
    const s2cMap = new Map<
      string,
      { count: number; sentimentWeighted: number; sessions: Set<string> }
    >();
    // 2. Context -> Referenced
    const c2rMap = new Map<
      string,
      { count: number; sentimentWeighted: number; sessions: Set<string> }
    >();

    for (const f of filteredFlows) {
      const s2cKey = `${f.speakerCountry}::${f.context}`;
      if (!s2cMap.has(s2cKey)) {
        s2cMap.set(s2cKey, {
          count: 0,
          sentimentWeighted: 0,
          sessions: new Set(),
        });
      }
      const s2cVal = s2cMap.get(s2cKey)!;
      s2cVal.count += f.count;
      s2cVal.sentimentWeighted += f.avgSentiment * f.count;
      f.sessions.forEach((s) => s2cVal.sessions.add(s));

      const c2rKey = `${f.context}::${f.referencedCountry}`;
      if (!c2rMap.has(c2rKey)) {
        c2rMap.set(c2rKey, {
          count: 0,
          sentimentWeighted: 0,
          sessions: new Set(),
        });
      }
      const c2rVal = c2rMap.get(c2rKey)!;
      c2rVal.count += f.count;
      c2rVal.sentimentWeighted += f.avgSentiment * f.count;
      f.sessions.forEach((s) => c2rVal.sessions.add(s));
    }

    const links: SankeyLink[] = [];

    s2cMap.forEach((data, key) => {
      const [speaker, context] = key.split('::');
      links.push({
        source: `s_${speaker}`,
        target: `c_${context}`,
        value: data.count,
        avgSentiment: data.count > 0 ? data.sentimentWeighted / data.count : 0,
        sessions: Array.from(data.sessions),
      });
    });

    c2rMap.forEach((data, key) => {
      const [context, referenced] = key.split('::');
      links.push({
        source: `c_${context}`,
        target: `r_${referenced}`,
        value: data.count,
        avgSentiment: data.count > 0 ? data.sentimentWeighted / data.count : 0,
        sessions: Array.from(data.sessions),
      });
    });

    return {
      nodesList: nodes,
      linksList: links,
    };
  }, [filteredFlows]);

  // Run D3-Sankey Layout Generator
  const { sankeyNodes, sankeyLinks } = useMemo(() => {
    if (nodesList.length === 0 || linksList.length === 0) {
      return { sankeyNodes: [], sankeyLinks: [] };
    }

    // Prevent mutating React states in-place by creating copies
    const graphNodes = nodesList.map((n) => ({ ...n }));
    const graphLinks = linksList.map((l) => ({ ...l }));

    try {
      const layout = sankey<SankeyNode, SankeyLink>()
        .nodeId((d) => d.id)
        .nodeWidth(16)
        .nodePadding(14)
        .extent([
          [80, 50],
          [dimensions.width - 80, dimensions.height - 40],
        ]);

      const result = layout({ nodes: graphNodes, links: graphLinks });
      return {
        sankeyNodes: result.nodes,
        sankeyLinks: result.links,
      };
    } catch (e) {
      console.error('D3 Sankey layout failed:', e);
      return { sankeyNodes: [], sankeyLinks: [] };
    }
  }, [nodesList, linksList, dimensions]);

  // Calculate sentiment-based node color for Country nodes
  const getNodeColor = (node: SankeyLayoutNode) => {
    if (node.type === 'context') {
      if (node.name === 'PRAISE') return '#10b981';
      if (node.name === 'ACCUSATION') return '#ef4444';
      return '#6b7280';
    }

    // Aggregate average sentiment for this country node in the filtered flows
    const flows = filteredFlows.filter((f) =>
      node.type === 'speaker' ? f.speakerCountry === node.name : f.referencedCountry === node.name,
    );
    if (flows.length === 0) return '#4b5563';

    const totalCount = flows.reduce((sum, f) => sum + f.count, 0);
    const sentimentSum = flows.reduce((sum, f) => sum + f.avgSentiment * f.count, 0);
    const avgSentiment = sentimentSum / totalCount;

    return sentimentToColor(avgSentiment);
  };

  // Determine Link Ribbon Color
  const getLinkContext = (link: SankeyLayoutLink) => {
    return link.source.type === 'context' ? link.source.name : link.target.name;
  };

  const getLinkColor = (link: SankeyLayoutLink) => {
    const ctx = getLinkContext(link);
    if (ctx === 'PRAISE') return '#10b981';
    if (ctx === 'ACCUSATION') return '#ef4444';
    return '#6b7280';
  };

  // Determine Link Ribbon Opacity
  const getLinkOpacity = (link: SankeyLayoutLink, idx: number) => {
    const ctx = getLinkContext(link);
    const defaultOpacity = ctx === 'NEUTRAL_MENTION' ? 0.35 : 0.55;

    if (hoveredLinkIdx !== null) {
      return hoveredLinkIdx === idx ? 0.85 : 0.08;
    }

    if (hoveredNodeId !== null) {
      const isConnected = link.source.id === hoveredNodeId || link.target.id === hoveredNodeId;
      return isConnected ? 0.85 : 0.08;
    }

    return defaultOpacity;
  };

  const handleContextToggle = (ctx: ReferenceContext) => {
    if (selectedContexts.includes(ctx)) {
      setSelectedContexts(selectedContexts.filter((c) => c !== ctx));
    } else {
      setSelectedContexts([...selectedContexts, ctx]);
    }
  };

  const resetFilters = () => {
    setSelectedSession('');
    setSelectedContexts(['PRAISE', 'ACCUSATION', 'NEUTRAL_MENTION']);
    setMinConnectionCount(2);
    setCountrySearch('');
  };

  // Tooltip detail info model
  const tooltipDetails = useMemo(() => {
    if (hoveredLinkIdx === null || !sankeyLinks[hoveredLinkIdx]) return null;
    const link = sankeyLinks[hoveredLinkIdx] as unknown as SankeyLayoutLink;

    const sourceName = link.source.name;
    const targetName = link.target.name;
    const ctx = getLinkContext(link);

    let flowLabel = '';
    if (link.source.type === 'speaker') {
      flowLabel = `${sourceName} ─[${ctx}]─▶ [Bahsedilenler]`;
    } else {
      flowLabel = `[Konuşmacılar] ─[${ctx}]─▶ ${targetName}`;
    }

    return {
      flowLabel,
      count: link.value,
      sentiment: link.avgSentiment,
      sessions: link.sessions.join(', ') || 'Belirtilmemiş',
    };
  }, [hoveredLinkIdx, sankeyLinks]);

  return (
    <div
      ref={containerRef}
      className="w-full flex flex-col bg-carbon-950 border border-carbon-550 min-h-[600px] p-5 relative overflow-hidden font-mono select-none"
    >
      {/* Sankey Controls Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-carbon-800 z-30 select-text">
        <div className="flex flex-wrap items-center gap-4 text-[10px]">
          {/* Session Timeline dropdown */}
          <div className="relative" ref={sessionDropdownRef}>
            <button
              onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
              className="flex items-center gap-2 bg-carbon-900 border border-carbon-700 px-3 py-1.5 text-carbon-200 hover:text-carbon-50 hover:bg-carbon-800 transition-colors"
            >
              <Calendar className="w-3.5 h-3.5 text-indigo-400" />
              <span>
                {selectedSession === ''
                  ? 'Tüm Oturumlar'
                  : sessionsQuery.data?.find((s) => s.sessionId === selectedSession)
                      ?.sessionLabel || selectedSession}
              </span>
              <ChevronDown className="w-3 h-3 text-carbon-400" />
            </button>
            {sessionDropdownOpen && (
              <div className="absolute top-full left-0 mt-1.5 bg-carbon-900 border border-carbon-700 p-2 w-60 shadow-2xl z-50 flex flex-col gap-1.5">
                <button
                  onClick={() => {
                    setSelectedSession('');
                    setSessionDropdownOpen(false);
                  }}
                  className={`text-left px-2 py-1 text-carbon-300 hover:text-carbon-50 hover:bg-carbon-800 transition-colors rounded ${
                    selectedSession === '' ? 'bg-indigo-950/40 text-indigo-400' : ''
                  }`}
                >
                  Tüm Oturumlar
                </button>
                {sessionsQuery.isPending && (
                  <div className="text-carbon-400 py-1 text-2xs animate-pulse">Yükleniyor...</div>
                )}
                {sessionsQuery.data?.map((session) => (
                  <button
                    key={session.sessionId}
                    onClick={() => {
                      setSelectedSession(session.sessionId);
                      setSessionDropdownOpen(false);
                    }}
                    className={`text-left px-2 py-1 text-carbon-300 hover:text-carbon-50 hover:bg-carbon-800 transition-colors rounded truncate ${
                      selectedSession === session.sessionId
                        ? 'bg-indigo-950/40 text-indigo-400 font-bold'
                        : ''
                    }`}
                  >
                    {session.sessionLabel}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Context Checkboxes */}
          <div className="flex items-center gap-3 bg-carbon-900 border border-carbon-800 px-3 py-1.5 rounded-none text-carbon-300">
            <span className="text-carbon-400 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5 text-indigo-400" /> BAĞLAM:
            </span>
            <label className="flex items-center gap-1.5 cursor-pointer hover:text-carbon-50">
              <input
                type="checkbox"
                checked={selectedContexts.includes('PRAISE')}
                onChange={() => handleContextToggle('PRAISE')}
                className="w-3.5 h-3.5 bg-carbon-950 border border-carbon-700 text-indigo-500 rounded focus:ring-0 focus:ring-offset-0 cursor-pointer"
              />
              <span className="text-emerald-500">Praise</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer hover:text-carbon-50">
              <input
                type="checkbox"
                checked={selectedContexts.includes('ACCUSATION')}
                onChange={() => handleContextToggle('ACCUSATION')}
                className="w-3.5 h-3.5 bg-carbon-950 border border-carbon-700 text-indigo-500 rounded focus:ring-0 focus:ring-offset-0 cursor-pointer"
              />
              <span className="text-red-500">Accusation</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer hover:text-carbon-50">
              <input
                type="checkbox"
                checked={selectedContexts.includes('NEUTRAL_MENTION')}
                onChange={() => handleContextToggle('NEUTRAL_MENTION')}
                className="w-3.5 h-3.5 bg-carbon-950 border border-carbon-700 text-indigo-500 rounded focus:ring-0 focus:ring-offset-0 cursor-pointer"
              />
              <span className="text-carbon-400">Neutral</span>
            </label>
          </div>
        </div>

        {/* Slider and Autocomplete Search */}
        <div className="flex flex-wrap items-center gap-4 text-[10px]">
          {/* Slider */}
          <div className="flex items-center gap-2 bg-carbon-900 border border-carbon-800 px-3 py-1.5">
            <span className="text-carbon-400 uppercase font-bold tracking-wider">
              Min. Bağlantı:
            </span>
            <span className="text-indigo-400 font-bold w-4">{minConnectionCount}</span>
            <input
              type="range"
              min="1"
              max="15"
              value={minConnectionCount}
              onChange={(e) => setMinConnectionCount(Number(e.target.value))}
              className="accent-indigo-500 w-24 bg-carbon-950 rounded-none h-1 border border-carbon-800 appearance-none cursor-pointer"
            />
          </div>

          {/* Country text search with Autocomplete suggestions popup */}
          <div className="relative" ref={suggestionsRef}>
            <div className="flex items-center bg-carbon-900 border border-carbon-700 px-2.5 py-1">
              <input
                type="text"
                placeholder="Konuşmacı veya hedef ülke..."
                value={countrySearch}
                onChange={(e) => {
                  setCountrySearch(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                className="bg-transparent border-none text-carbon-200 focus:outline-none focus:ring-0 w-44 placeholder-carbon-500 text-[10px]"
              />
              {countrySearch && (
                <button
                  onClick={() => setCountrySearch('')}
                  className="text-carbon-400 hover:text-carbon-100 pl-1"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {showSuggestions && countrySuggestions.length > 0 && (
              <div className="absolute top-full right-0 mt-1 bg-carbon-900 border border-carbon-700 w-48 shadow-2xl z-50 flex flex-col">
                {countrySuggestions.map((country) => (
                  <button
                    key={country}
                    onClick={() => {
                      setCountrySearch(country);
                      setShowSuggestions(false);
                    }}
                    className="text-left px-3 py-1.5 hover:bg-carbon-800 text-carbon-300 hover:text-carbon-50 transition-colors border-b border-carbon-800 last:border-0 truncate"
                  >
                    {country}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main visualization container */}
      <div className="flex-1 relative flex flex-col justify-center min-h-[460px]">
        {flowsQuery.isPending && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-carbon-950/60 z-20">
            <RefreshCw className="w-6 h-6 text-indigo-400 animate-spin" />
            <span className="text-xs text-carbon-400">Veriler yükleniyor...</span>
          </div>
        )}

        {!flowsQuery.isPending && filteredFlows.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-carbon-950 text-carbon-400 text-xs">
            <Info className="w-6 h-6 text-carbon-600" />
            <span>Seçili filtrelere uygun akış verisi bulunamadı.</span>
            <button
              onClick={resetFilters}
              className="mt-2 btn-primary bg-indigo-900 border border-indigo-700/80 hover:bg-indigo-800 px-4 py-1.5 text-[10px] text-carbon-100 transition-colors"
            >
              Filtreleri Sıfırla
            </button>
          </div>
        )}

        {filteredFlows.length > 0 && sankeyNodes.length > 0 && (
          <>
            {/* Column Title Labels at the top of the Sankey columns */}
            <div
              className="absolute top-2 w-full flex justify-between px-20 font-bold uppercase text-[9px] tracking-wider text-carbon-400 pointer-events-none"
              style={{ left: 0 }}
            >
              <span>KONUŞAN</span>
              <span className="transform translate-x-[4px]">BAĞLAM</span>
              <span>BAHSEDİLEN</span>
            </div>

            {/* D3 Sankey SVG Render */}
            <svg width={dimensions.width} height={dimensions.height} className="overflow-visible">
              {/* Links Ribbons Layer */}
              <g className="links-layer">
                {sankeyLinks.map((link, idx: number) => {
                  const layoutLink = link as unknown as SankeyLayoutLink;
                  const pathData = sankeyLinkHorizontal<SankeyLayoutNode, SankeyLayoutLink>()(
                    layoutLink,
                  );
                  if (!pathData) return null;

                  const strokeColor = getLinkColor(layoutLink);
                  const opacity = getLinkOpacity(layoutLink, idx);

                  return (
                    <path
                      key={`link-${idx}`}
                      d={pathData}
                      fill="none"
                      stroke={strokeColor}
                      strokeOpacity={opacity}
                      strokeWidth={Math.max(1, layoutLink.width || 1)}
                      className="transition-all duration-150 cursor-pointer"
                      onMouseEnter={(e) => {
                        setHoveredLinkIdx(idx);
                        setTooltipPos({ x: e.clientX, y: e.clientY });
                      }}
                      onMouseMove={(e) => {
                        setTooltipPos({ x: e.clientX, y: e.clientY });
                      }}
                      onMouseLeave={() => setHoveredLinkIdx(null)}
                    />
                  );
                })}
              </g>

              {/* Nodes Columns Layer */}
              <g className="nodes-layer">
                {sankeyNodes.map((node) => {
                  const layoutNode = node as unknown as SankeyLayoutNode;
                  const nodeHeight = Math.max(2, (layoutNode.y1 ?? 0) - (layoutNode.y0 ?? 0));
                  const nodeWidth = (layoutNode.x1 ?? 0) - (layoutNode.x0 ?? 0);
                  const isNodeHovered = layoutNode.id === hoveredNodeId;

                  // Hover dim logic for nodes
                  let nodeOpacity = 1.0;
                  if (hoveredLinkIdx !== null && sankeyLinks[hoveredLinkIdx]) {
                    const link = sankeyLinks[hoveredLinkIdx] as unknown as SankeyLayoutLink;
                    const isConnected =
                      link.source.id === layoutNode.id || link.target.id === layoutNode.id;
                    nodeOpacity = isConnected ? 1.0 : 0.25;
                  } else if (hoveredNodeId !== null) {
                    const isSameNode = layoutNode.id === hoveredNodeId;
                    const isConnected = sankeyLinks.some((l) => {
                      const layoutL = l as unknown as SankeyLayoutLink;
                      return (
                        (layoutL.source.id === hoveredNodeId &&
                          layoutL.target.id === layoutNode.id) ||
                        (layoutL.target.id === hoveredNodeId && layoutL.source.id === layoutNode.id)
                      );
                    });
                    nodeOpacity = isSameNode || isConnected ? 1.0 : 0.25;
                  }

                  // Text label properties based on column layer
                  let textX = (layoutNode.x0 ?? 0) - 8;
                  let textAnchor: 'start' | 'end' = 'end';
                  if (layoutNode.layer > 0) {
                    textX = (layoutNode.x1 ?? 0) + 8;
                    textAnchor = 'start';
                  }

                  const nodeColor = getNodeColor(layoutNode);

                  return (
                    <g
                      key={layoutNode.id}
                      className="node cursor-pointer"
                      onMouseEnter={() => setHoveredNodeId(layoutNode.id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                      style={{ opacity: nodeOpacity }}
                    >
                      {/* Node block */}
                      <rect
                        x={layoutNode.x0}
                        y={layoutNode.y0}
                        width={nodeWidth}
                        height={nodeHeight}
                        fill={nodeColor}
                        stroke="#020617"
                        strokeWidth={isNodeHovered ? 2 : 1}
                        className="transition-all duration-150"
                      />

                      {/* Node text label */}
                      <text
                        x={textX}
                        y={((layoutNode.y0 ?? 0) + (layoutNode.y1 ?? 0)) / 2}
                        dy=".35em"
                        textAnchor={textAnchor}
                        fill={isNodeHovered ? '#ffffff' : '#c8c8c8'}
                        fontSize="8px"
                        fontWeight={isNodeHovered ? 'bold' : 'normal'}
                        className="pointer-events-none select-none font-mono tracking-wider transition-colors duration-150"
                      >
                        {layoutNode.name}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>

            {/* Custom Tooltip Overlay */}
            {tooltipDetails && (
              <div
                className="fixed bg-carbon-950 border border-carbon-700/80 p-3 shadow-2xl pointer-events-none z-[100] max-w-xs font-mono text-[9px] text-carbon-100"
                style={{
                  left: tooltipPos.x + 16,
                  top: tooltipPos.y + 16,
                }}
              >
                {/* ASCII Tooltip borders design */}
                <div className="leading-normal">
                  <div className="font-bold text-carbon-50 mb-1">{tooltipDetails.flowLabel}</div>
                  <div className="h-px bg-carbon-800 my-1" />
                  <div className="flex justify-between py-0.5">
                    <span className="text-carbon-400">Toplam:</span>
                    <span className="font-bold text-carbon-100">
                      {tooltipDetails.count} referans
                    </span>
                  </div>
                  <div className="flex justify-between py-0.5">
                    <span className="text-carbon-400">Avg Sentiment:</span>
                    <span
                      className="font-bold"
                      style={{ color: sentimentToColor(tooltipDetails.sentiment) }}
                    >
                      {tooltipDetails.sentiment >= 0 ? '+' : ''}
                      {tooltipDetails.sentiment.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between py-0.5">
                    <span className="text-carbon-400">Oturumlar:</span>
                    <span
                      className="font-bold text-carbon-300 truncate max-w-[140px]"
                      title={tooltipDetails.sessions}
                    >
                      {tooltipDetails.sessions}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer help guide banner */}
      <div className="border-t border-carbon-800 pt-3 flex items-center gap-2 text-carbon-400 text-[9px] mt-2 select-text">
        <Activity className="w-3.5 h-3.5 text-indigo-400" />
        <span>
          Sankey diyagramı diplomatik referans bağlamlarını gösterir. Akış kalınlıkları toplam
          referans sayısıyla orantılıdır. Linklerin üzerine gelerek detayları inceleyebilirsiniz.
        </span>
      </div>
    </div>
  );
};
