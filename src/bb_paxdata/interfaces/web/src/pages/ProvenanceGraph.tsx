import {
  ProvenanceGraph as ProvenanceGraphType,
  provenanceService,
} from '@/services/provenanceService';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Clock, GitBranch, Hash } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import {
  Background,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

interface ProvenanceGraphProps {
  resultId?: string;
}

const nodeTypes = {
  default: ({ data }: { data: Record<string, unknown> }) => (
    <div
      className="px-4 py-2 rounded-lg border-2 bg-white shadow-md hover:shadow-lg transition-shadow min-w-[200px]"
      style={{
        borderColor: data.operationType === 'ANOMALY_DETECTION' ? '#ef4444' : '#3b82f6',
      }}
    >
      <div className="font-semibold text-sm text-gray-900">{data.stageName}</div>
      <div className="text-xs text-gray-600 mt-1">{data.operationType}</div>
      {data.durationMs && (
        <div className="flex items-center gap-1 text-xs text-gray-500 mt-1">
          <Clock size={12} />
          <span>{data.durationMs.toFixed(2)}ms</span>
        </div>
      )}
      <div className="flex items-center gap-1 text-xs text-gray-400 mt-1">
        <Hash size={12} />
        <span className="font-mono">{data.outputHash.slice(0, 8)}...</span>
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

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const onNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
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
        <div className="text-gray-500">Loading provenance graph...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-2 text-red-500">
          <AlertCircle size={20} />
          <span>Error loading provenance graph</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b bg-white">
        <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
          <GitBranch size={24} />
          Provenance Graph
        </h2>
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={resultId}
            onChange={(e) => setResultId(e.target.value)}
            placeholder="Enter result ID..."
            className="flex-1 px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            Load Graph
          </button>
        </form>
      </div>

      {graph && (
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 bg-gray-50">
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
              <Background />
              <Controls />
              <MiniMap />
            </ReactFlow>
          </div>

          {selectedNode && (
            <div className="w-80 bg-white border-l p-4 overflow-y-auto">
              <h3 className="font-bold text-lg mb-4">Node Details</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium text-gray-500">Stage Name</label>
                  <div className="text-sm">{selectedNode.stage_name}</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Operation Type</label>
                  <div className="text-sm">{selectedNode.operation_type}</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Duration</label>
                  <div className="text-sm">{selectedNode.duration_ms?.toFixed(2)} ms</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Timestamp</label>
                  <div className="text-sm">{new Date(selectedNode.timestamp).toLocaleString()}</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Input Hash</label>
                  <div className="text-xs font-mono bg-gray-100 p-2 rounded break-all">
                    {selectedNode.input_hash}
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">Output Hash</label>
                  <div className="text-xs font-mono bg-gray-100 p-2 rounded break-all">
                    {selectedNode.output_hash}
                  </div>
                </div>
                {selectedNode.correlation_id && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">Correlation ID</label>
                    <div className="text-xs font-mono">{selectedNode.correlation_id}</div>
                  </div>
                )}
                {Object.keys(selectedNode.metadata).length > 0 && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">Metadata</label>
                    <pre className="text-xs bg-gray-100 p-2 rounded overflow-auto max-h-40">
                      {JSON.stringify(selectedNode.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {mermaidData && (
            <div className="w-80 bg-white border-l p-4 overflow-y-auto">
              <h3 className="font-bold text-lg mb-4">Mermaid Diagram</h3>
              <pre className="text-xs bg-gray-100 p-2 rounded overflow-auto max-h-96">
                {mermaidData.content}
              </pre>
            </div>
          )}
        </div>
      )}

      {!graph && !isLoading && (
        <div className="flex-1 flex items-center justify-center text-gray-400">
          <div className="text-center">
            <GitBranch size={48} className="mx-auto mb-4 opacity-50" />
            <p>Enter a result ID to view its provenance graph</p>
          </div>
        </div>
      )}
    </div>
  );
};
