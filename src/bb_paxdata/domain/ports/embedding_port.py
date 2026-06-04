from typing import Protocol, Sequence, runtime_checkable

import numpy as np


@runtime_checkable
class EmbeddingService(Protocol):
    """Domain port interface for sentence embedding services."""

    async def get_embeddings(self, texts: Sequence[str]) -> np.ndarray:
        """Return (N, D) float32 array where N = len(texts), D = model dimension."""
        ...

    async def warm_cache(self, texts: Sequence[str]) -> int:
        """Pre-compute and cache embeddings. Returns count of new embeddings."""
        ...

    def get_model_dimension(self) -> int:
        """Return embedding dimension (e.g., 384 for MiniLM)."""
        ...
