import { BookOpen, HelpCircle, Info, User } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { DiscourseEdge, DiscourseNode } from '@/types';
import { cn } from '@/utils/helpers';

interface DiscourseNetworkExplorerProps {
  nodes: DiscourseNode[];
  edges: DiscourseEdge[];
  minWeight: number;
}

export const DiscourseNetworkExplorer = ({
  nodes,
  edges,
  minWeight,
}: DiscourseNetworkExplorerProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const leftColRef = useRef<HTMLDivElement>(null);
  const rightColRef = useRef<HTMLDivElement>(null);

  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodePositions, setNodePositions] = useState<Record<string, number>>({});

  // Filter nodes and edges by minWeight
  const activeEdges = useMemo(() => {
    return edges.filter((e) => e.weight >= minWeight);
  }, [edges, minWeight]);

  const activeNodes = useMemo(() => {
    const nodeIdsWithEdges = new Set<string>();
    activeEdges.forEach((e) => {
      nodeIdsWithEdges.add(e.source);
      nodeIdsWithEdges.add(e.target);
    });
    return nodes.filter((n) => nodeIdsWithEdges.has(n.id));
  }, [nodes, activeEdges]);

  // Separate actors and concepts
  const actors = useMemo(() => {
    return activeNodes.filter((n) => n.type === 'actor');
  }, [activeNodes]);

  const concepts = useMemo(() => {
    return activeNodes.filter((n) => n.type === 'concept');
  }, [activeNodes]);

  // Calculate metrics per node
  const nodeStats = useMemo(() => {
    const stats: Record<string, { degree: number; avgWeight: number; totalWeight: number }> = {};

    activeNodes.forEach((n) => {
      stats[n.id] = { degree: 0, avgWeight: 0, totalWeight: 0 };
    });

    activeEdges.forEach((e) => {
      if (stats[e.source]) {
        stats[e.source].degree += 1;
        stats[e.source].totalWeight += e.weight;
      }
      if (stats[e.target]) {
        stats[e.target].degree += 1;
        stats[e.target].totalWeight += e.weight;
      }
    });

    Object.keys(stats).forEach((id) => {
      const s = stats[id];
      s.avgWeight = s.degree > 0 ? s.totalWeight / s.degree : 0;
    });

    return stats;
  }, [activeNodes, activeEdges]);

  // Map of connections for quick lookup
  const connections = useMemo(() => {
    const map: Record<string, Set<string>> = {};
    activeNodes.forEach((n) => {
      map[n.id] = new Set<string>();
    });

    activeEdges.forEach((e) => {
      if (map[e.source]) map[e.source].add(e.target);
      if (map[e.target]) map[e.target].add(e.source);
    });

    return map;
  }, [activeNodes, activeEdges]);

  // Update Y coordinate of each node relative to the main container
  const updatePositions = useCallback(() => {
    if (!containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const positions: Record<string, number> = {};

    activeNodes.forEach((n) => {
      const el = document.getElementById(`discourse-node-${n.id}`);
      if (el) {
        const rect = el.getBoundingClientRect();
        // center Y relative to the container
        positions[n.id] = rect.top - containerRect.top + rect.height / 2;
      }
    });

    setNodePositions(positions);
  }, [activeNodes]);

  // Run on mount, resize, scroll or data changes
  useEffect(() => {
    updatePositions();
    const timer = setTimeout(updatePositions, 100); // Wait for DOM layout pass

    window.addEventListener('resize', updatePositions);

    // Add scroll listeners to columns to keep SVG paths updated
    const leftCol = leftColRef.current;
    const rightCol = rightColRef.current;
    if (leftCol) leftCol.addEventListener('scroll', updatePositions);
    if (rightCol) rightCol.addEventListener('scroll', updatePositions);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updatePositions);
      if (leftCol) leftCol.removeEventListener('scroll', updatePositions);
      if (rightCol) rightCol.removeEventListener('scroll', updatePositions);
    };
  }, [activeNodes, activeEdges, updatePositions]);

  // Force re-measure when hover/select changes in case of DOM reflows
  useEffect(() => {
    updatePositions();
  }, [hoveredNodeId, selectedNodeId, updatePositions]);

  // Find relationships for the selected node
  const selectedNodeDetails = useMemo(() => {
    if (!selectedNodeId) return null;
    const node = nodes.find((n) => n.id === selectedNodeId);
    if (!node) return null;

    const rels = activeEdges
      .filter((e) => e.source === selectedNodeId || e.target === selectedNodeId)
      .map((e) => {
        const otherId = e.source === selectedNodeId ? e.target : e.source;
        const otherNode = nodes.find((n) => n.id === otherId);
        return {
          nodeId: otherId,
          label: otherNode?.label || otherId,
          type: otherNode?.type || 'concept',
          weight: e.weight,
          tf: e.tf,
          idf: e.idf,
        };
      })
      .sort((a, b) => b.weight - a.weight);

    return {
      node,
      relationships: rels,
      stats: nodeStats[selectedNodeId],
    };
  }, [selectedNodeId, nodes, activeEdges, nodeStats]);

  // Hover highlighting helpers
  const isNodeHighlighted = (id: string) => {
    if (hoveredNodeId === id || selectedNodeId === id) return true;
    if (hoveredNodeId && connections[hoveredNodeId]?.has(id)) return true;
    if (selectedNodeId && connections[selectedNodeId]?.has(id)) return true;
    return false;
  };

  const isEdgeHighlighted = (edge: DiscourseEdge) => {
    if (hoveredNodeId === edge.source || hoveredNodeId === edge.target) return true;
    if (selectedNodeId === edge.source || selectedNodeId === edge.target) return true;
    return false;
  };

  const hasActiveHighlight = hoveredNodeId !== null || selectedNodeId !== null;

  return (
    <div className="space-y-6">
      <div
        ref={containerRef}
        className="relative grid grid-cols-12 gap-0 border border-hair border-carbon-550 bg-carbon-900/60 rounded-none h-[600px] overflow-hidden select-none"
      >
        {/* Left Column: Actors */}
        <div
          ref={leftColRef}
          className="col-span-4 border-r border-hair border-carbon-550 overflow-y-auto p-4 space-y-2 custom-scrollbar h-full"
        >
          <div className="flex items-center gap-2 pb-3 mb-2 border-b border-hair border-carbon-550 sticky top-0 bg-carbon-900/90 z-10">
            <User className="w-4 h-4 text-carbon-400" />
            <span className="text-xs font-semibold text-carbon-100 uppercase tracking-wider">
              Aktörler
            </span>
            <span className="ml-auto text-3xs bg-carbon-800 text-carbon-300 px-1.5 py-0.5 font-mono">
              {actors.length}
            </span>
          </div>

          {actors.length === 0 ? (
            <div className="text-center py-8 text-xs text-carbon-500">Aktör bulunamadı.</div>
          ) : (
            actors.map((actor) => {
              const stats = nodeStats[actor.id];
              const isHighlighted = isNodeHighlighted(actor.id);
              const isSelected = selectedNodeId === actor.id;
              const isHovered = hoveredNodeId === actor.id;

              return (
                <div
                  key={actor.id}
                  id={`discourse-node-${actor.id}`}
                  onMouseEnter={() => setHoveredNodeId(actor.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  onClick={() => setSelectedNodeId(isSelected ? null : actor.id)}
                  className={cn(
                    'p-3 border transition-all duration-swift cursor-pointer group flex flex-col gap-1',
                    isSelected
                      ? 'bg-carbon-800 border-carbon-300'
                      : isHovered
                        ? 'bg-carbon-800/60 border-carbon-400'
                        : isHighlighted
                          ? 'bg-carbon-900 border-carbon-500 text-carbon-100'
                          : hasActiveHighlight
                            ? 'bg-carbon-950/40 border-transparent opacity-40 text-carbon-500'
                            : 'bg-carbon-900/40 border-carbon-800 text-carbon-300 hover:border-carbon-600',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold tracking-tight truncate max-w-[180px]">
                      {actor.label}
                    </span>
                    <span className="text-3xs font-mono text-carbon-400">
                      {stats?.degree || 0} bağ
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-3xs text-carbon-500">
                    <span>Ort. Ağırlık</span>
                    <span className="font-mono text-carbon-300">
                      {stats?.avgWeight.toFixed(3) || '0.000'}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Center Column: SVG Canvas */}
        <div className="col-span-4 relative h-full pointer-events-none bg-carbon-950/20">
          <svg className="absolute inset-0 w-full h-full">
            <defs>
              <linearGradient id="edge-gradient-default" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#3A3A3A" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#3A3A3A" stopOpacity="0.15" />
              </linearGradient>
              <linearGradient id="edge-gradient-highlight" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#8A8A8A" stopOpacity="0.8" />
                <stop offset="50%" stopColor="#E0E0E0" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#8A8A8A" stopOpacity="0.8" />
              </linearGradient>
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            {/* Draw all edges */}
            {activeEdges.map((edge, index) => {
              const ySource = nodePositions[edge.source];
              const yTarget = nodePositions[edge.target];

              // Skip drawing if coordinates aren't measured yet
              if (ySource === undefined || yTarget === undefined) return null;

              const isHighlighted = isEdgeHighlighted(edge);
              const strokeColor = isHighlighted
                ? 'url(#edge-gradient-highlight)'
                : 'url(#edge-gradient-default)';
              const strokeWidth = isHighlighted ? 2.5 : 1;

              // Bezier control points for clean S-curves
              // Left side is source (X=0), right side is target (X=100%)
              return (
                <g key={`edge-${edge.source}-${edge.target}-${index}`}>
                  <path
                    d={`M 0 ${ySource} C 120 ${ySource}, 120 ${yTarget}, 240 ${yTarget}`}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    className={cn(
                      'transition-all duration-swift',
                      isHighlighted && 'animate-[blink-status_2s_ease-in-out_infinite]',
                    )}
                    style={
                      isHighlighted
                        ? {
                            filter: 'url(#glow)',
                            strokeDasharray: '6, 4',
                            animation:
                              'dash 30s linear infinite, blink-status 2s ease-in-out infinite',
                          }
                        : undefined
                    }
                  />
                  {/* Additional highlight curve */}
                  {isHighlighted && (
                    <path
                      d={`M 0 ${ySource} C 120 ${ySource}, 120 ${yTarget}, 240 ${yTarget}`}
                      fill="none"
                      stroke="#FFFFFF"
                      strokeWidth={0.8}
                      opacity={0.6}
                    />
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* Right Column: Concepts */}
        <div
          ref={rightColRef}
          className="col-span-4 border-l border-hair border-carbon-550 overflow-y-auto p-4 space-y-2 custom-scrollbar h-full"
        >
          <div className="flex items-center gap-2 pb-3 mb-2 border-b border-hair border-carbon-550 sticky top-0 bg-carbon-900/90 z-10">
            <BookOpen className="w-4 h-4 text-carbon-400" />
            <span className="text-xs font-semibold text-carbon-100 uppercase tracking-wider">
              Kavramlar
            </span>
            <span className="ml-auto text-3xs bg-carbon-800 text-carbon-300 px-1.5 py-0.5 font-mono">
              {concepts.length}
            </span>
          </div>

          {concepts.length === 0 ? (
            <div className="text-center py-8 text-xs text-carbon-500">Kavram bulunamadı.</div>
          ) : (
            concepts.map((concept) => {
              const stats = nodeStats[concept.id];
              const isHighlighted = isNodeHighlighted(concept.id);
              const isSelected = selectedNodeId === concept.id;
              const isHovered = hoveredNodeId === concept.id;

              return (
                <div
                  key={concept.id}
                  id={`discourse-node-${concept.id}`}
                  onMouseEnter={() => setHoveredNodeId(concept.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  onClick={() => setSelectedNodeId(isSelected ? null : concept.id)}
                  className={cn(
                    'p-3 border transition-all duration-swift cursor-pointer group flex flex-col gap-1',
                    isSelected
                      ? 'bg-carbon-800 border-carbon-300'
                      : isHovered
                        ? 'bg-carbon-800/60 border-carbon-400'
                        : isHighlighted
                          ? 'bg-carbon-900 border-carbon-500 text-carbon-100'
                          : hasActiveHighlight
                            ? 'bg-carbon-950/40 border-transparent opacity-40 text-carbon-500'
                            : 'bg-carbon-900/40 border-carbon-800 text-carbon-300 hover:border-carbon-600',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold tracking-tight truncate max-w-[180px]">
                      {concept.label}
                    </span>
                    <span className="text-3xs font-mono text-carbon-400">
                      {stats?.degree || 0} bağ
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-3xs text-carbon-500">
                    <span>Ort. Ağırlık</span>
                    <span className="font-mono text-carbon-300">
                      {stats?.avgWeight.toFixed(3) || '0.000'}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* SVG Dash Animation styles */}
      <style>{`
        @keyframes dash {
          to {
            stroke-dashoffset: -1000;
          }
        }
      `}</style>

      {/* Details Panel: Displayed when a node is selected */}
      {selectedNodeDetails ? (
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 space-y-4 transition-all duration-swift">
          <div className="flex items-center justify-between border-b border-hair border-carbon-550 pb-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-carbon-800 border border-hair border-carbon-600 flex items-center justify-center">
                {selectedNodeDetails.node.type === 'actor' ? (
                  <User className="w-4 h-4 text-carbon-100" />
                ) : (
                  <BookOpen className="w-4 h-4 text-carbon-100" />
                )}
              </div>
              <div>
                <h4 className="text-sm font-semibold text-carbon-50">
                  {selectedNodeDetails.node.label}
                </h4>
                <p className="text-3xs text-carbon-400 uppercase tracking-widest mt-0.5">
                  {selectedNodeDetails.node.type === 'actor' ? 'Aktör Profili' : 'Söylem Kavramı'}
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="text-right">
                <span className="block text-3xs text-carbon-450 uppercase">Toplam Bağlantı</span>
                <span className="text-xs font-mono font-bold text-carbon-100">
                  {selectedNodeDetails.stats?.degree || 0}
                </span>
              </div>
              <div className="text-right border-l border-hair border-carbon-700 pl-4">
                <span className="block text-3xs text-carbon-450 uppercase">
                  Ort. Fischer Ağırlığı
                </span>
                <span className="text-xs font-mono font-bold text-carbon-100">
                  {selectedNodeDetails.stats?.avgWeight.toFixed(4) || '0.0000'}
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-1 text-2xs font-semibold text-carbon-300 mb-1">
              <Info className="w-3.5 h-3.5" />
              <span>Söylem Bağlantıları Ağırlık Kırılımı (Fischer DNA)</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[160px] overflow-y-auto custom-scrollbar pr-2">
              {selectedNodeDetails.relationships.map((rel) => (
                <div
                  key={rel.nodeId}
                  className="bg-carbon-950/40 border border-hair border-carbon-800 hover:border-carbon-700 p-2.5 flex items-center justify-between"
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="text-2xs font-medium text-carbon-200">{rel.label}</span>
                    <span className="text-4xs text-carbon-500 uppercase tracking-wider font-semibold">
                      {rel.type === 'actor' ? 'aktör' : 'kavram'}
                    </span>
                  </div>
                  <div className="flex gap-3 text-right">
                    <div className="flex flex-col">
                      <span className="text-4xs text-carbon-500 font-mono">
                        TF: {rel.tf.toFixed(2)}
                      </span>
                      <span className="text-4xs text-carbon-500 font-mono">
                        IDF: {rel.idf.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex flex-col justify-center">
                      <span className="text-2xs font-mono font-semibold text-carbon-100">
                        {rel.weight.toFixed(4)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="border border-hair border-carbon-800 bg-carbon-900/30 p-5 text-center text-xs text-carbon-500 flex flex-col items-center justify-center gap-2">
          <HelpCircle className="w-5 h-5 text-carbon-600" />
          <p>
            Bağlantı katsayılarını (TF, IDF, Ağırlık) detaylandırmak için bir aktör veya kavram
            hücresine tıklayın.
          </p>
        </div>
      )}
    </div>
  );
};
