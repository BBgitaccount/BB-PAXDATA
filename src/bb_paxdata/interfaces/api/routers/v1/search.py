from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository
from bb_paxdata.infrastructure.search.meilisearch_client import (
    search_communities,
    search_sentences,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(prefix="/search", tags=["Search"])


class SearchResponse(BaseModel):
    hits: list[dict[str, Any]]
    estimated_total_hits: int
    query: str
    processing_time_ms: int


class VectorSearchRequest(BaseModel):
    query_vector: list[float] = Field(..., min_length=1, max_length=4096)
    file_id: str | None = Field(None, max_length=200)
    country: str | None = Field(None, max_length=100)
    speaker_name: str | None = Field(None, max_length=200)
    limit: int = Field(20, ge=1, le=200)
    embedding_dim: int = Field(384, ge=64, le=4096)

    @model_validator(mode="after")
    def validate_vector_dimension(self) -> "VectorSearchRequest":
        if len(self.query_vector) != self.embedding_dim:
            raise ValueError(
                f"Length of query_vector ({len(self.query_vector)}) must match embedding_dim ({self.embedding_dim})"
            )
        return self


class VectorSearchResult(BaseModel):
    sent_id: str
    text: str
    speaker_name: str
    country: str
    file_id: str
    similarity_score: float


@router.get("/sentences", response_model=SearchResponse)
async def search_sentences_endpoint(
    q: str = Query(..., min_length=1, max_length=512, description="Search query"),
    country: str | None = Query(default=None),
    min_risk: int | None = Query(default=None, ge=0, le=10),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    """Typo-tolerant full-text search over sentences."""
    filter_parts: list[str] = []
    if country:
        filter_parts.append(f'country = "{country}"')
    if min_risk is not None:
        filter_parts.append(f"AI_Risk_Skoru >= {min_risk}")

    result = await search_sentences(
        query=q,
        filters=" AND ".join(filter_parts) if filter_parts else None,
        limit=limit,
        offset=offset,
    )
    return SearchResponse(
        hits=result.get("hits", []),
        estimated_total_hits=result.get("estimatedTotalHits", 0),
        query=q,
        processing_time_ms=result.get("processingTimeMs", 0),
    )


@router.get("/communities", response_model=SearchResponse)
async def search_communities_endpoint(
    q: str = Query(..., min_length=1, max_length=512, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SearchResponse:
    """Full-text search over network communities."""
    result = await search_communities(
        query=q,
        limit=limit,
        offset=offset,
    )
    return SearchResponse(
        hits=result.get("hits", []),
        estimated_total_hits=result.get("estimatedTotalHits", 0),
        query=q,
        processing_time_ms=result.get("processingTimeMs", 0),
    )


@router.post("/sentences/vector", response_model=list[VectorSearchResult])
async def search_sentences_by_vector(
    request: VectorSearchRequest,
    session: AsyncSession = Depends(get_db),
) -> list[VectorSearchResult]:
    """
    Vector similarity search over sentences using pgvector.

    Accepts a query embedding vector and returns similar sentences ordered by cosine similarity.
    """
    repo = SentenceRepository(session=session)
    results = await repo.search_by_vector(
        query_vector=request.query_vector,
        file_id=request.file_id,
        country=request.country,
        speaker_name=request.speaker_name,
        limit=request.limit,
        embedding_dim=request.embedding_dim,
    )

    return [
        VectorSearchResult(
            sent_id=sent.sent_id,
            text=sent.text,
            speaker_name=sent.speaker_name,
            country=sent.country or "",
            file_id=sent.file_id,
            similarity_score=score,
        )
        for sent, score in results
    ]
