from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


class RAGatoulleColBERTService:
    """
    Concrete implementation of ColBERTEmbeddingService using ragatouille.
    Wraps ColBERT-v2 (Santhanam et al. 2022) via the ragatouille library.

    PLAID engine (Santhanam et al. 2022b) provides compressed late-interaction
    retrieval at < 200ms/query on CPU for corpora up to ~1M passages.

    Index lifecycle:
        1. build_index(passages, passage_ids) — one-time or incremental
        2. retrieve(query, k) — returns RetrievedContext list
    """

    _MODEL_NAME = "colbert-ir/colbertv2.0"

    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path
        self._model: Any = None

    def _load_or_raise(self) -> Any:
        if self._model is None:
            raise RuntimeError(
                "ColBERT model not initialized. Call build_index() or load_index() first."
            )
        return self._model

    def build_index(
        self,
        passages: list[str],
        passage_ids: list[str],
        index_name: str = "bb_paxdata_rag",
        max_document_length: int = 180,
        split_documents: bool = True,
    ) -> None:
        """
        Build PLAID index from passage corpus.

        Args:
            passages: Raw text passages (segments, sentences, or chunks).
            passage_ids: Stable string IDs corresponding to each passage.
            index_name: Subdirectory name within index_path.
            max_document_length: Token limit per passage (ColBERT default: 180).
            split_documents: If True, ragatouille auto-splits long passages.

        Raises:
            ValueError: If len(passages) != len(passage_ids).
        """
        if len(passages) != len(passage_ids):
            raise ValueError(
                f"passages ({len(passages)}) and passage_ids ({len(passage_ids)}) "
                "must have equal length."
            )

        try:
            from ragatouille import RAGPretrainedModel
        except ImportError:
            raise ImportError(
                "ragatouille is not installed. Install it with: poetry add ragatouille"
            )

        model = RAGPretrainedModel.from_pretrained(self._MODEL_NAME)
        model.index(
            collection=passages,
            document_ids=passage_ids,
            index_name=index_name,
            max_document_length=max_document_length,
            split_documents=split_documents,
        )
        self._model = model

    def load_index(self, index_name: str = "bb_paxdata_rag") -> None:
        """Load an existing PLAID index from disk."""
        try:
            from ragatouille import RAGPretrainedModel
        except ImportError:
            raise ImportError(
                "ragatouille is not installed. Install it with: poetry add ragatouille"
            )

        index_dir = self._index_path / index_name
        if not index_dir.exists():
            raise FileNotFoundError(f"PLAID index not found at {index_dir}")
        self._model = RAGPretrainedModel.from_index(str(index_dir))

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        """
        Late-interaction MaxSim retrieval.

        Score formula (Khattab & Zaharia 2020):
            S(q, d) = Σ_{t ∈ q} max_{t' ∈ d} (q_t · d_t')

        Returns:
            List of dicts: {"content": str, "document_id": str, "score": float}
            Ordered by descending MaxSim score.
        """
        model = self._load_or_raise()
        results = model.search(query=query, k=k)
        return results

    def encode_queries(self, queries: list[str]) -> list[np.ndarray]:
        """ColBERTEmbeddingService protocol — query-side token embeddings."""
        model = self._load_or_raise()
        return [
            model.model.query_tokenizer.tensorize([q]).cpu().numpy() for q in queries
        ]

    def encode_passages(self, passages: list[str]) -> list[np.ndarray]:
        """ColBERTEmbeddingService protocol — passage-side token embeddings."""
        model = self._load_or_raise()
        return [
            model.model.doc_tokenizer.tensorize([p]).cpu().numpy() for p in passages
        ]

    def embedding_dim(self) -> int:
        """ColBERT-v2 hidden dim: 128."""
        return 128

    def is_index_ready(self) -> bool:
        """
        Returns True if the PLAID index is loaded and ready for retrieval.
        """
        return self._model is not None
