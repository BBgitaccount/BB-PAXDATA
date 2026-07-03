import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Clock, GitBranch, Hash } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Background,
  Controls,
  type Edge,
  MarkerType,
  MiniMap,
  type Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from 'reactflow';
import {
  type ProvenanceGraph as ProvenanceGraphType,
  provenanceService,
} from '@/services/provenanceService';
import 'reactflow/dist/style.css';

interface ProvenanceGraphProps {
  resultId?: string;
}

interface CustomNodeData {
  stageName: string;
  operationType: string;
  durationMs: number | null;
  outputHash: string;
  inputHash: string;
  timestamp: string;
  correlationId: string | null;
  metadata: Record<string, unknown>;
}

const nodeTypes = {
  default: ({ data }: { data: CustomNodeData }) => (
    <div
      className="px-4 py-2 rounded-none border bg-carbon-900 hover:border-carbon-450 transition-all min-w-[200px]"
      style={{
        borderColor:
          data.operationType === 'ANOMALY_DETECTION' ? 'var(--signal-fail)' : 'var(--signal-info)',
      }}
    >
      <div className="font-semibold text-sm text-carbon-50">{data.stageName}</div>
      <div className="text-xs text-carbon-400 mt-1">{data.operationType}</div>
      {data.durationMs && (
        <div className="flex items-center gap-1 text-xs text-carbon-450 mt-1">
          <Clock size={12} />
          <span>{data.durationMs.toFixed(2)}ms</span>
        </div>
      )}
      <div className="flex items-center gap-1 text-xs text-carbon-500 mt-1">
        <Hash size={12} />
        <span className="font-mono">{data.outputHash?.slice(0, 8)}...</span>
      </div>
    </div>
  ),
};

export const ProvenanceGraph = ({ resultId: propResultId }: ProvenanceGraphProps) => {
  const [resultId, setResultId] = useState(propResultId || '');
  const [selectedNode, setSelectedNode] = useState<ProvenanceGraphType['nodes'][0] | null>(null);

  const {
    data: graph,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['provenance', resultId],
    queryFn: () => provenanceService.getGraph(resultId),
    enabled: !!resultId,
  });

  const { data: mermaidData } = useQuery({
    queryKey: ['provenance-mermaid', resultId],
    queryFn: () => provenanceService.getMermaidFormat(resultId),
    enabled: !!resultId,
  });

  const initialNodes: Node[] = useMemo(() => {
    if (!graph) return [];

    return graph.nodes.map((node, index) => ({
      id: node.id,
      type: 'default',
      position: { x: index * 300, y: 100 + (index % 3) * 150 },
      data: {
        stageName: node.stage_name,
        operationType: node.operation_type,
        durationMs: node.duration_ms,
        outputHash: node.output_hash,
        inputHash: node.input_hash,
        timestamp: node.timestamp,
        correlationId: node.correlation_id,
        metadata: node.metadata,
      },
    }));
  }, [graph]);

  const initialEdges: Edge[] = useMemo(() => {
    if (!graph) return [];

    return graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source_node_id,
      target: edge.target_node_id,
      animated: true,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed },
    }));
  }, [graph]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const graphNode = graph?.nodes.find((n) => n.id === node.id);
      if (graphNode) {
        setSelectedNode(graphNode);
      }
    },
    [graph],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (resultId.trim()) {
      setSelectedNode(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-carbon-400">Loading provenance graph...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle size={20} />
          <span>Error loading provenance graph</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col animate-[fade-in-up_300ms_ease-out_both]">
      <div className="p-4 border-b border-hair bg-carbon-900">
        <h2 className="text-xl font-semibold tracking-tight text-carbon-50 mb-4 flex items-center gap-2">
          <GitBranch size={24} />
          Provenance Graph
        </h2>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={resultId}
            onChange={(e) => setResultId(e.target.value)}
            placeholder="Enter result ID..."
            className="flex-1 px-3 py-2 border-hair bg-carbon-850 text-carbon-100 rounded-none focus:outline-none focus:border-carbon-400"
          />
          <button type="submit" className="px-4 py-2 btn-primary rounded-none">
            Load Graph
          </button>
        </form>
      </div>

      {graph && (
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 bg-carbon-950">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              fitView
              className="h-full"
            >
              <Background color="var(--border-hair)" gap={16} />
              <Controls
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '0.5px solid var(--border-hair)',
                  borderRadius: 0,
                  color: 'var(--text-primary)',
                }}
              />
              <MiniMap
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '0.5px solid var(--border-hair)',
                  borderRadius: 0,
                }}
                nodeColor="var(--sentiment-partner)"
                maskColor="rgba(0, 0, 0, 0.6)"
              />
            </ReactFlow>
          </div>

          {selectedNode && (
            <div className="w-80 bg-carbon-900 border-l border-hair p-4 overflow-y-auto">
              <h3 className="font-semibold text-sm tracking-wider uppercase mb-4 text-carbon-450">
                Node Details
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                    Stage Name
                  </label>
                  <div className="text-sm text-carbon-100 mt-1">{selectedNode.stage_name}</div>
                </div>
                <div>
                  <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                    Operation Type
                  </label>
                  <div className="text-sm text-carbon-100 mt-1">{selectedNode.operation_type}</div>
                </div>
                <div>
                  <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                    Duration
                  </label>
                  <div className="text-sm text-carbon-100 mt-1">
                    {selectedNode.duration_ms?.toFixed(2)} ms
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                    Timestamp
                  </label>
                  <div className="text-sm text-carbon-100 mt-1">
                    {new Date(selectedNode.timestamp).toLocaleString()}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                    Input Hash
                  </label>
                  <div className="text-xs font-mono bg-carbon-950 border border-hair p-2 rounded-none break-all text-carbon-200 mt-1">
                    {selectedNode.input_hash}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                    Output Hash
                  </label>
                  <div className="text-xs font-mono bg-carbon-950 border border-hair p-2 rounded-none break-all text-carbon-200 mt-1">
                    {selectedNode.output_hash}
                  </div>
                </div>
                {selectedNode.correlation_id && (
                  <div>
                    <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                      Correlation ID
                    </label>
                    <div className="text-xs font-mono text-carbon-200 mt-1">
                      {selectedNode.correlation_id}
                    </div>
                  </div>
                )}
                {Object.keys(selectedNode.metadata).length > 0 && (
                  <div>
                    <label className="text-xs font-semibold tracking-wider text-carbon-450 uppercase">
                      Metadata
                    </label>
                    <pre className="text-xs bg-carbon-950 border border-hair p-2 rounded-none overflow-auto max-h-40 text-carbon-200 mt-1">
                      {JSON.stringify(selectedNode.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {mermaidData && (
            <div className="w-80 bg-carbon-900 border-l border-hair p-4 overflow-y-auto">
              <h3 className="font-semibold text-sm tracking-wider uppercase mb-4 text-carbon-450">
                Mermaid Diagram
              </h3>
              <pre className="text-xs bg-carbon-950 border border-hair p-2 rounded-none overflow-auto max-h-96 text-carbon-200">
                {mermaidData.content}
              </pre>
            </div>
          )}
        </div>
      )}

      {!graph && !isLoading && (
        <div className="flex-1 flex items-center justify-center text-carbon-450 bg-carbon-950">
          <div className="text-center">
            <GitBranch size={48} className="mx-auto mb-4 opacity-50" />
            <p>Enter a result ID to view its provenance graph</p>
          </div>
        </div>
      )}
    </div>
  );
};
