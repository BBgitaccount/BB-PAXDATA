"""ColBERT v2 PLAID service — ragatouille backend.

Infrastructure implementation of the ColBERTEmbeddingService Protocol.
This file is the single canonical location for all ragatouille imports.

Reference: Khattab & Zaharia (2020) "ColBERT: Efficient and Effective
Passage Search via Contextualized Late Interaction over BERT"
Santhanam et al. (2022) "ColBERTv2: Effective and Efficient Retrieval"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from bb_paxdata.application.domain.ports.embedding_port import (
    ColBERTEmbeddingService as ColBERTEmbeddingServiceProtocol,
)


class RAGatoulleColBERTService:
    """Concrete ColBERT implementation backed by ragatouille + PLAID index.

    Satisfies: ColBERTEmbeddingServiceProtocol (embedding_port.py).
    Injected into: ColBERTDenseRetriever (infrastructure/retrieval/).
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
        if len(passages) != len(passage_ids):
            raise ValueError(
                f"passages ({len(passages)}) and passage_ids ({len(passage_ids)}) "
                "must have equal length."
            )
        try:
            from ragatouille import RAGPretrainedModel
        except ImportError:
            raise ImportError(
                "ragatouille is not installed. Install with: poetry add ragatouille"
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
        try:
            from ragatouille import RAGPretrainedModel
        except ImportError:
            raise ImportError(
                "ragatouille is not installed. Install with: poetry add ragatouille"
            )
        index_dir = self._index_path / index_name
        if not index_dir.exists():
            raise FileNotFoundError(f"PLAID index not found at {index_dir}")
        self._model = RAGPretrainedModel.from_index(str(index_dir))

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        model = self._load_or_raise()
        return model.search(query=query, k=k)

    def encode_queries(self, queries: list[str]) -> list[np.ndarray]:
        model = self._load_or_raise()
        return [
            model.model.query_tokenizer.tensorize([q]).cpu().numpy() for q in queries
        ]

    def encode_passages(self, passages: list[str]) -> list[np.ndarray]:
        model = self._load_or_raise()
        return [
            model.model.doc_tokenizer.tensorize([p]).cpu().numpy() for p in passages
        ]

    def embedding_dim(self) -> int:
        return 128

    def is_index_ready(self) -> bool:
        return self._model is not None


# Runtime Protocol conformance guard
_svc_stub = RAGatoulleColBERTService.__new__(RAGatoulleColBERTService)
assert isinstance(
    _svc_stub, ColBERTEmbeddingServiceProtocol
), "RAGatoulleColBERTService must satisfy ColBERTEmbeddingServiceProtocol"
del _svc_stub
