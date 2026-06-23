import { apiClient } from './apiClient';

export interface ProvenanceNode {
  id: string;
  operation_type: string;
  stage_name: string;
  input_hash: string;
  output_hash: string;
  timestamp: string;
  duration_ms: number | null;
  correlation_id: string | null;
  metadata: Record<string, unknown>;
  version: string;
}

export interface ProvenanceEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  metadata: Record<string, unknown>;
}

export interface ProvenanceGraph {
  id: string;
  result_id: string;
  nodes: ProvenanceNode[];
  edges: ProvenanceEdge[];
  created_at: string;
  correlation_id: string | null;
}

export interface ProvenanceDotResponse {
  result_id: string;
  format: string;
  content: string;
}

export interface ProvenanceMermaidResponse {
  result_id: string;
  format: string;
  content: string;
}

export const provenanceService = {
  async getGraph(resultId: string): Promise<ProvenanceGraph> {
    return apiClient.get<ProvenanceGraph>(`/api/v1/provenance/${resultId}`);
  },

  async getDotFormat(resultId: string): Promise<ProvenanceDotResponse> {
    return apiClient.get<ProvenanceDotResponse>(`/api/v1/provenance/${resultId}/dot`);
  },

  async getMermaidFormat(resultId: string): Promise<ProvenanceMermaidResponse> {
    return apiClient.get<ProvenanceMermaidResponse>(`/api/v1/provenance/${resultId}/mermaid`);
  },

  async getByCorrelationId(correlationId: string): Promise<ProvenanceGraph[]> {
    return apiClient.get<ProvenanceGraph[]>(`/api/v1/provenance/correlation/${correlationId}`);
  },
};
