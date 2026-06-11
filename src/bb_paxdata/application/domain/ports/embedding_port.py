from collections.abc import Sequence
from typing import Protocol, runtime_checkable

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


@runtime_checkable
class ColBERTEmbeddingService(Protocol):
    """
    Protocol for ColBERT late-interaction token-level embedding services.
    Distinct from EmbeddingService — returns per-token vectors, not pooled.

    Reference: Khattab & Zaharia (2020) "ColBERT: Efficient and Effective
    Passage Search via Contextualized Late Interaction over BERT"
    """

    def encode_queries(self, queries: list[str]) -> list[np.ndarray]:
        """
        Encode query strings into token-level embeddings.

        Returns:
            List of ndarrays, each shape (T_q, D) float32.
            T_q = query token count (padded to fixed length in ColBERT: 32 tokens).
            D = model hidden dimension (128 for ColBERT-v2).
        """
        ...

    def encode_passages(self, passages: list[str]) -> list[np.ndarray]:
        """
        Encode passage strings into token-level embeddings.

        Returns:
            List of ndarrays, each shape (T_d, D) float32.
            T_d = document token count (variable, max 180 tokens for ColBERT-v2).
            D = model hidden dimension (128).
        """
        ...

    def embedding_dim(self) -> int:
        """Return token embedding dimension (128 for ColBERT-v2)."""
        ...

    def is_index_ready(self) -> bool:
        """
        Returns True if the PLAID index is loaded and ready for retrieval.
        Replaces precompute_and_cache() semantics — document encoding is
        performed offline during index build, not on-demand.
        """
        ...
