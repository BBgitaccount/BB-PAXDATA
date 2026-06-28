// src/bb_paxdata/interfaces/web/src/hooks/useNetworkSimulationWorker.ts
// Custom hook to manage D3 force simulation in Web Worker

import { useEffect, useRef, useState } from 'react';
import type {
  SimulationLink,
  SimulationNode,
  WorkerMessage,
} from '../workers/networkSimulation.worker';

export interface NodePosition {
  id: string;
  x: number;
  y: number;
  country_code: string;
}

export interface LinkPosition {
  source: string;
  target: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface TickMessage {
  type: 'tick';
  nodes: NodePosition[];
  links: LinkPosition[];
}

export const useNetworkSimulationWorker = () => {
  const workerRef = useRef<Worker | null>(null);
  const [nodePositions, setNodePositions] = useState<Record<string, NodePosition>>({});
  const [linkPositions, setLinkPositions] = useState<LinkPosition[]>([]);
  const [isWorkerReady, setIsWorkerReady] = useState(false);

  useEffect(() => {
    // Create worker from the worker file
    const worker = new Worker(new URL('../workers/networkSimulation.worker.ts', import.meta.url), {
      type: 'module',
    });

    workerRef.current = worker;

    worker.onmessage = (e: MessageEvent<TickMessage>) => {
      const { type, nodes, links } = e.data;

      if (type === 'tick') {
        // Update node positions
        const newNodePositions: Record<string, NodePosition> = {};
        for (const node of nodes) {
          newNodePositions[node.country_code] = node;
        }
        setNodePositions(newNodePositions);
        setLinkPositions(links);
      }
    };

    worker.onerror = (error) => {
      console.error('Worker error:', error);
    };

    setIsWorkerReady(true);

    return () => {
      worker.terminate();
      workerRef.current = null;
    };
  }, []);

  const initSimulation = (
    nodes: SimulationNode[],
    links: SimulationLink[],
    width: number,
    height: number,
    clusteringMode: boolean,
    filteredConnections: Array<Record<string, unknown>>,
  ) => {
    if (!workerRef.current || !isWorkerReady) return;

    const message: WorkerMessage = {
      type: 'init',
      nodes,
      links,
      width,
      height,
      clusteringMode,
      filteredConnections,
    };

    workerRef.current.postMessage(message);
  };

  const updateSimulation = (
    nodes?: SimulationNode[],
    links?: SimulationLink[],
    width?: number,
    height?: number,
    clusteringMode?: boolean,
    filteredConnections?: Array<Record<string, unknown>>,
  ) => {
    if (!workerRef.current || !isWorkerReady) return;

    const message: WorkerMessage = {
      type: 'update',
      nodes,
      links,
      width,
      height,
      clusteringMode,
      filteredConnections,
    };

    workerRef.current.postMessage(message);
  };

  const startSimulation = () => {
    if (!workerRef.current || !isWorkerReady) return;
    workerRef.current.postMessage({ type: 'start' });
  };

  const stopSimulation = () => {
    if (!workerRef.current || !isWorkerReady) return;
    workerRef.current.postMessage({ type: 'stop' });
  };

  return {
    nodePositions,
    linkPositions,
    isWorkerReady,
    initSimulation,
    updateSimulation,
    startSimulation,
    stopSimulation,
  };
};
