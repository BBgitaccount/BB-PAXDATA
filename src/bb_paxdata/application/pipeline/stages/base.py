# src/bb_paxdata/application/pipeline/stages/base.py
from __future__ import annotations

import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.domain.models.provenance import (
    OperationType,
    ProvenanceEdge,
    ProvenanceGraph,
    ProvenanceNode,
)
from bb_paxdata.application.domain.utils.context import get_correlation_id

if TYPE_CHECKING:
    from bb_paxdata.application.pipeline.models.collect_result import CollectResult
    from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult


def compute_hash(obj: Any) -> str:
    """Compute a SHA256 hash of a Python object for provenance tracking."""
    try:
        # Convert object to JSON string
        if hasattr(obj, "model_dump"):
            serialized = json.dumps(obj.model_dump(), sort_keys=True, default=str)
        elif hasattr(obj, "dict"):
            serialized = json.dumps(obj.dict(), sort_keys=True, default=str)
        elif isinstance(obj, dict | list | str | int | float | bool):
            serialized = json.dumps(obj, sort_keys=True, default=str)
        else:
            serialized = str(obj)

        return hashlib.sha256(serialized.encode()).hexdigest()
    except Exception:
        # Fallback to string representation if serialization fails
        return hashlib.sha256(str(obj).encode()).hexdigest()


class ProvenanceAwareStage(ABC):
    """Mixin for stages that support provenance tracking."""

    def __init__(self):
        self._provenance_graph: ProvenanceGraph | None = None
        self._previous_node_id: str | None = None

    def set_provenance_graph(self, graph: ProvenanceGraph) -> None:
        """Set the provenance graph for this stage."""
        self._provenance_graph = graph

    def get_provenance_graph(self) -> ProvenanceGraph | None:
        """Get the current provenance graph."""
        return self._provenance_graph

    def record_provenance(
        self,
        operation_type: OperationType,
        stage_name: str,
        input_data: Any,
        output_data: Any,
        metadata: dict[str, Any] | None = None,
    ) -> ProvenanceNode:
        """Record a provenance node for this stage execution."""
        start_time = time.time()

        input_hash = compute_hash(input_data)
        output_hash = compute_hash(output_data)

        duration_ms = (time.time() - start_time) * 1000

        correlation_id = get_correlation_id()

        node = ProvenanceNode(
            operation_type=operation_type,
            stage_name=stage_name,
            input_hash=input_hash,
            output_hash=output_hash,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )

        if self._provenance_graph:
            self._provenance_graph.add_node(node)

            # Create edge from previous node if exists
            if self._previous_node_id:
                edge = ProvenanceEdge(
                    source_node_id=self._previous_node_id,
                    target_node_id=node.id,
                )
                self._provenance_graph.add_edge(edge)

            self._previous_node_id = node.id

        return node


class BaseAssemblyStage(ProvenanceAwareStage, ABC):
    """Base class for pipeline ASSEMBLE stages."""

    @abstractmethod
    async def process(self, analysis: Analysis) -> Analysis:
        raise NotImplementedError


class BaseFinalizeStage(ProvenanceAwareStage, ABC):
    """Base class for pipeline FINALIZE stages."""

    @abstractmethod
    async def process(self, session: Any, analysis: Analysis) -> Analysis:
        raise NotImplementedError

    @abstractmethod
    async def run(
        self,
        analysis: Analysis,
        collect_result: CollectResult,
        success: bool,
        errors: list[str],
        session: Any = None,
    ) -> PipelineResult:
        raise NotImplementedError
