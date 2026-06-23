from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OperationType(StrEnum):
    """Types of operations in the provenance graph."""

    NER = "NER"
    AI_ANALYSIS = "AI_ANALYSIS"
    AGGREGATION = "AGGREGATION"
    VALIDATION = "VALIDATION"
    SENTIMENT_ANALYSIS = "SENTIMENT_ANALYSIS"
    FRAME_DETECTION = "FRAME_DETECTION"
    ANOMALY_DETECTION = "ANOMALY_DETECTION"
    COLLECT = "COLLECT"
    ASSEMBLE = "ASSEMBLE"
    FINALIZE = "FINALIZE"
    CUSTOM = "CUSTOM"


class ProvenanceNode(BaseModel):
    """Represents a node in the provenance graph (an operation)."""

    id: UUID = Field(default_factory=uuid4)
    operation_type: OperationType
    stage_name: str
    input_hash: str
    output_hash: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: float | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }


class ProvenanceEdge(BaseModel):
    """Represents an edge in the provenance graph (input → output relationship)."""

    id: UUID = Field(default_factory=uuid4)
    source_node_id: UUID
    target_node_id: UUID
    edge_type: str = "data_flow"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvenanceGraph(BaseModel):
    """Complete provenance graph tracking the production chain of a result."""

    id: UUID = Field(default_factory=uuid4)
    result_id: str
    nodes: list[ProvenanceNode] = Field(default_factory=list)
    edges: list[ProvenanceEdge] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None

    def add_node(self, node: ProvenanceNode) -> None:
        """Add a node to the graph."""
        self.nodes.append(node)

    def add_edge(self, edge: ProvenanceEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    def get_node_by_id(self, node_id: UUID) -> ProvenanceNode | None:
        """Retrieve a node by its ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_production_chain(self, result_id: str) -> list[ProvenanceNode]:
        """Get the ordered production chain for a specific result."""
        chain = []
        visited = set()

        def dfs(node_id: UUID) -> None:
            if node_id in visited:
                return
            visited.add(node_id)

            node = self.get_node_by_id(node_id)
            if node:
                chain.append(node)

            # Find incoming edges (dependencies)
            for edge in self.edges:
                if edge.target_node_id == node_id:
                    dfs(edge.source_node_id)

        # Find the final node with the result_id in metadata
        for node in self.nodes:
            if node.metadata.get("result_id") == result_id:
                dfs(node.id)
                break

        return list(reversed(chain))

    def to_dot_format(self) -> str:
        """Convert the provenance graph to Graphviz DOT format."""
        lines = ["digraph ProvenanceGraph {"]
        lines.append("  rankdir=LR;")
        lines.append('  node [shape=box, style="rounded,filled", fontname="Arial"];')

        # Add nodes
        for node in self.nodes:
            label = f"{node.operation_type}\\n{node.stage_name}"
            if node.duration_ms:
                label += f"\\n{node.duration_ms:.2f}ms"
            lines.append(f'  "{node.id}" [label="{label}", fillcolor="#e0e0e0"];')

        # Add edges
        for edge in self.edges:
            lines.append(f'  "{edge.source_node_id}" -> "{edge.target_node_id}";')

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid_format(self) -> str:
        """Convert the provenance graph to Mermaid diagram format."""
        lines = ["graph TD"]

        # Add nodes
        for node in self.nodes:
            node_id = str(node.id)[:8]
            label = f"{node.operation_type}<br>{node.stage_name}"
            if node.duration_ms:
                label += f"<br>{node.duration_ms:.2f}ms"
            lines.append(f'  {node_id}["{label}"]')

        # Add edges
        for edge in self.edges:
            source_id = str(edge.source_node_id)[:8]
            target_id = str(edge.target_node_id)[:8]
            lines.append(f"  {source_id} --> {target_id}")

        return "\n".join(lines)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str,
        }
