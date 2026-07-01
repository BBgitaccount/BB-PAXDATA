// src/bb_paxdata/interfaces/web/src/workers/networkSimulation.worker.ts
// D3 Force Simulation Worker - Offloads heavy computation from UI thread

import * as d3 from 'd3';

export interface SimulationNode extends d3.SimulationNodeDatum {
  country_code: string;
  country_name: string;
  total_mentions: number;
  avg_sentiment: number;
  r: number;
}

export interface SimulationLink extends d3.SimulationLinkDatum<SimulationNode> {
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

export interface WorkerMessage {
  type: 'init' | 'update' | 'start' | 'stop' | 'tick';
  nodes?: SimulationNode[];
  links?: SimulationLink[];
  width?: number;
  height?: number;
  clusteringMode?: boolean;
  filteredConnections?: Array<Record<string, unknown>>;
}

export interface TickMessage {
  type: 'tick';
  nodes: Array<{ id: string; x: number; y: number; country_code: string }>;
  links: Array<{ source: string; target: string; x1: number; y1: number; x2: number; y2: number }>;
}

let simulation: d3.Simulation<SimulationNode, SimulationLink> | null = null;
let nodes: SimulationNode[] = [];
let links: SimulationLink[] = [];
let isRunning = false;

const getDominantRelType = (
  countryCode: string,
  connections: Array<Record<string, unknown>>,
): string => {
  const countryConns = connections.filter(
    (c) => c.from_country === countryCode || c.to_country === countryCode,
  );
  if (countryConns.length === 0) return 'NEUTRAL';

  const counts: Record<string, number> = {};
  for (const c of countryConns) {
    const type = String(c.relationship_type || 'NEUTRAL');
    const count = Number(c.interaction_count || 0);
    counts[type] = (counts[type] || 0) + count;
  }

  let dominant = 'NEUTRAL';
  let maxVal = -1;
  for (const type of Object.keys(counts)) {
    if (counts[type] > maxVal) {
      maxVal = counts[type];
      dominant = type;
    }
  }
  return dominant;
};

self.onmessage = (e: MessageEvent<WorkerMessage>) => {
  const {
    type,
    nodes: newNodes,
    links: newLinks,
    width = 800,
    height = 600,
    clusteringMode = false,
    filteredConnections = [],
  } = e.data;

  switch (type) {
    case 'init':
      nodes = newNodes || [];
      links = newLinks || [];
      initSimulation(width, height, clusteringMode, filteredConnections);
      break;

    case 'update':
      if (newNodes) nodes = newNodes;
      if (newLinks) links = newLinks;
      updateSimulation(width, height, clusteringMode, filteredConnections);
      break;

    case 'start':
      if (simulation) {
        isRunning = true;
        simulation.alpha(1).restart();
      }
      break;

    case 'stop':
      isRunning = false;
      if (simulation) {
        simulation.stop();
      }
      break;
  }
};

function initSimulation(
  width: number,
  height: number,
  clusteringMode: boolean,
  filteredConnections: Array<Record<string, unknown>>,
) {
  if (simulation) {
    simulation.stop();
  }

  simulation = d3
    .forceSimulation<SimulationNode, SimulationLink>(nodes)
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force(
      'collision',
      d3.forceCollide<SimulationNode>().radius((d) => d.r + 8),
    );

  const linkForce = d3
    .forceLink<SimulationNode, SimulationLink>(links)
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
  }

  simulation.on('tick', () => {
    if (!isRunning) return;

    const tickData: TickMessage = {
      type: 'tick',
      nodes: nodes.map((n) => ({
        id: n.country_code,
        x: n.x ?? 0,
        y: n.y ?? 0,
        country_code: n.country_code,
      })),
      links: links.map((l) => {
        const source = l.source as SimulationNode;
        const target = l.target as SimulationNode;
        return {
          source: source.country_code,
          target: target.country_code,
          x1: source.x ?? 0,
          y1: source.y ?? 0,
          x2: target.x ?? 0,
          y2: target.y ?? 0,
        };
      }),
    };

    self.postMessage(tickData);
  });

  isRunning = true;
  simulation.alpha(1).restart();
}

function updateSimulation(
  width: number,
  height: number,
  clusteringMode: boolean,
  filteredConnections: Array<Record<string, unknown>>,
) {
  if (!simulation) {
    initSimulation(width, height, clusteringMode, filteredConnections);
    return;
  }

  simulation.nodes(nodes);

  const linkForce = d3
    .forceLink<SimulationNode, SimulationLink>(links)
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
  simulation.force('center', d3.forceCenter(width / 2, height / 2));

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

  if (isRunning) {
    simulation.alpha(1).restart();
  }
}
