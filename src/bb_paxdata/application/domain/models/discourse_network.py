"""
DEPRECATED — discourse_network.py

This module has been merged into discourse_flow.py as part of CIDDI-8.
All imports from this module will continue to work via re-export,
but should be updated to import from discourse_flow.py directly.

TODO: Delete this file once all imports have been updated.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing from discourse_network is deprecated. "
    "Use discourse_flow instead (CIDDI-8). "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export migrated classes from discourse_flow.py
# NOTE: DiscourseFlow remains defined here due to the merge conflict with
# discourse_flow.py's own DiscourseFlow class (representing directed edges).
from pydantic import BaseModel, Field  # noqa: E402

from bb_paxdata.application.domain.models.discourse_flow import (  # noqa: F401, E402
    DyadicMetrics,
    NetworkEdge,
)


class DiscourseFlow(BaseModel):
    """Fischer DNA: Complete discourse flow for a single analysis session."""

    model_config = {"frozen": True}

    session_id: str
    edges: tuple[NetworkEdge, ...] = Field(default_factory=tuple)
    actor_ids: tuple[str, ...] = Field(default_factory=tuple)
    concept_ids: tuple[str, ...] = Field(default_factory=tuple)
    topic_ids: list[str] = Field(
        default_factory=list, description="IDs of topics present in this flow (Faz 5)"
    )

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def add_edge(self, edge: NetworkEdge) -> DiscourseFlow:
        new_edges = (*self.edges, edge)
        new_actors = tuple(sorted(set(self.actor_ids) | {edge.actor_id}))
        new_concepts = tuple(sorted(set(self.concept_ids) | {edge.concept_id}))
        return self.model_copy(
            update={
                "edges": new_edges,
                "actor_ids": new_actors,
                "concept_ids": new_concepts,
            }
        )
