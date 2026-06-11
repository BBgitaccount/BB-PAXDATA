"""FastAPI router for full-text search over sentences and communities."""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from bb_paxdata.infrastructure.search.meilisearch_client import (
    search_communities,
    search_sentences,
)

router = APIRouter(prefix="/search", tags=["Search"])


class SearchResponse(BaseModel):
    hits: list[dict[str, Any]]
    estimated_total_hits: int
    query: str
    processing_time_ms: int


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
