from __future__ import annotations

from typing import Protocol, runtime_checkable

from bb_paxdata.application.domain.models.discourse_network import DiscourseFlow
from bb_paxdata.application.domain.models.gat_models import GATEmbedding


@runtime_checkable
class IGATEmbeddingService(Protocol):
    """Domain port for GAT (Graph Attention Network) actor embedding computation.

    Distinct from IGATEmbeddingRepository which covers persistence.
    This port covers the *computation* step: DiscourseFlow → GATEmbedding[].

    Concrete implementation:
        src/bb_paxdata/application/domain/services/gat_embedding_service.GATEmbeddingService
    After MİMARİ-5:
        src/bb_paxdata/infrastructure/nlp/gat_embedding_service.GATEmbeddingService

    References:
        - MİMARİ-4: Architecture port alignment task.
        - TASK-E02: GAT integration spec — uses this port for feature injection.
    """

    async def compute_embeddings(
        self,
        flow: DiscourseFlow,
        actor_features: dict[str, list[float]],
        concept_features: dict[str, list[float]],
    ) -> list[GATEmbedding]:
        """Compute 256-dim GAT actor embeddings from a Fischer DNA graph.

        Args:
            flow:             DiscourseFlow with actor_ids, edges, session_id.
            actor_features:   {actor_id: [384-dim SBERT mean-pool vector]}.
            concept_features: {concept_id: [384-dim description embedding]}.

        Returns:
            List of GATEmbedding, one per actor in flow.actor_ids.
            Each embedding includes anomaly_score and characteristic_concepts.
        """
        ...
