# src/bb_paxdata/domain/services/protocols/rag_protocols.py
from __future__ import annotations

from typing import AsyncIterator, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field


class RetrievedContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    sentence_id: str
    text: str
    speaker_name: str
    country: str
    panel_id: str
    similarity_score: float  # 0.0 – 1.0, unified across retrievers
    retrieval_source: str  # "meilisearch" | "pgvector" | "reranker"


class RAGQueryRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    query: str = Field(..., min_length=1, max_length=4096)
    panel_id_filter: str | None = None
    country_filters: list[str] | None = None
    speaker_filter: str | None = None
    top_k_keyword: int = Field(default=20, ge=1, le=100)
    top_k_dense: int = Field(default=20, ge=1, le=100)
    top_k_rerank: int = Field(default=5, ge=1, le=20)
    stream: bool = False
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class RAGQueryResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    query: str
    answer: str
    sources: list[RetrievedContext]
    latency_ms: float
    total_tokens: int | None = None


class KeywordRetrieverProtocol(Protocol):
    async def search(self, request: RAGQueryRequest) -> Sequence[RetrievedContext]: ...


class DenseRetrieverProtocol(Protocol):
    async def search(self, request: RAGQueryRequest) -> Sequence[RetrievedContext]: ...


class RerankerProtocol(Protocol):
    async def rerank(
        self, query: str, candidates: Sequence[RetrievedContext], top_n: int
    ) -> Sequence[RetrievedContext]: ...


class RAGSynthesisProtocol(Protocol):
    async def synthesize(
        self, query: str, contexts: Sequence[RetrievedContext], stream: bool
    ) -> str | AsyncIterator[str]: ...
