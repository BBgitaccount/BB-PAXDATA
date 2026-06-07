from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..models.gat_models import GATEmbedding


@runtime_checkable
class IGATEmbeddingRepository(Protocol):
    """Domain port interface for persisting and retrieving GAT embeddings.

    Implementations should handle storage (e.g., SQLAlchemy ORM, NoSQL, etc.)
    and be injected into services that need GAT embeddings.
    """

    async def get_by_actor_and_session(
        self, actor_id: str, session_id: str
    ) -> GATEmbedding | None:
        """Retrieve a single GATEmbedding for the given actor and session.

        Returns ``None`` if no embedding is found.
        """
        ...

    async def save(self, embedding: GATEmbedding) -> None:
        """Persist a single GATEmbedding instance."""
        ...

    async def save_batch(self, embeddings: Sequence[GATEmbedding]) -> None:
        """Persist a batch of GATEmbedding instances."""
        ...
