from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.services.hybrid_search_service import HybridSearchService
from bb_paxdata.application.services.semantic_clustering_service import (
    SemanticClusteringService,
)
from bb_paxdata.application.services.semantic_similarity_service import (
    SemanticSimilarityService,
)
from bb_paxdata.infrastructure.db.repositories.sentence import SentenceRepository
from bb_paxdata.infrastructure.nlp.sbert_embedding_service import SBERTEmbeddingService
from bb_paxdata.infrastructure.search.meilisearch_client import (
    search_communities,
    search_sentences,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter(prefix="/search", tags=["Search"])


# Dependency for hybrid search service
def get_hybrid_search_service(
    session: AsyncSession = Depends(get_db),
) -> HybridSearchService:
    """Get hybrid search service instance."""

    # Create a session factory that returns the current session
    def session_factory() -> AsyncSession:
        return session

    embedding_service = SBERTEmbeddingService()
    return HybridSearchService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        rrf_k=60,
    )


# Dependency for semantic similarity service
def get_semantic_similarity_service(
    session: AsyncSession = Depends(get_db),
) -> SemanticSimilarityService:
    """Get semantic similarity service instance."""

    def session_factory() -> AsyncSession:
        return session

    embedding_service = SBERTEmbeddingService()
    return SemanticSimilarityService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_dim=384,
    )


# Dependency for semantic clustering service
def get_semantic_clustering_service(
    session: AsyncSession = Depends(get_db),
    similarity_service: SemanticSimilarityService = Depends(
        get_semantic_similarity_service
    ),
) -> SemanticClusteringService:
    """Get semantic clustering service instance."""

    def session_factory() -> AsyncSession:
        return session

    return SemanticClusteringService(
        session_factory=session_factory,
        similarity_service=similarity_service,
        min_cluster_size=5,
        min_samples=None,
    )


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


class HybridSearchRequest(BaseModel):
    """Request model for hybrid search."""

    query: str = Field(..., min_length=1, max_length=512, description="Search query")
    file_id: str | None = Field(None, max_length=200, description="Filter by file ID")
    country: str | None = Field(None, max_length=100, description="Filter by country")
    speaker_name: str | None = Field(
        None, max_length=200, description="Filter by speaker name"
    )
    dominant_topic: str | None = Field(
        None, max_length=100, description="Filter by topic"
    )
    min_risk: int | None = Field(None, ge=0, le=10, description="Minimum risk score")
    emotion_category: str | None = Field(
        None, max_length=50, description="Filter by emotion"
    )
    limit: int = Field(20, ge=1, le=100, description="Maximum results")
    top_k_keyword: int = Field(
        50, ge=1, le=200, description="Keyword results to retrieve"
    )
    top_k_dense: int = Field(
        50, ge=1, le=200, description="Semantic results to retrieve"
    )
    include_facets: bool = Field(True, description="Include facet counts")


class HybridSearchResult(BaseModel):
    """Result model for hybrid search."""

    sent_id: str
    text: str
    speaker_name: str
    country: str
    file_id: str
    dominant_topic: str
    risk_score: int
    emotion_category: str
    rrf_score: float
    similarity_score: float | None = None
    keyword_rank: int | None = None
    semantic_rank: int | None = None


class HybridSearchResponse(BaseModel):
    """Response model for hybrid search."""

    results: list[HybridSearchResult]
    total_hits: int
    query: str
    facets: dict[str, Any] | None = None
    processing_time_ms: int


class SuggestRequest(BaseModel):
    """Request model for auto-suggest."""

    q: str = Field(..., min_length=1, max_length=100, description="Partial query")
    limit: int = Field(10, ge=1, le=20, description="Maximum suggestions")


class Suggestion(BaseModel):
    """Single suggestion item."""

    text: str
    type: str  # "speaker" or "term"
    count: int | None = None


class SimilarityRequest(BaseModel):
    """Request model for sentence similarity."""

    sentence_text: str = Field(
        ..., min_length=1, max_length=2000, description="Input sentence text"
    )
    file_id: str | None = Field(None, max_length=200, description="Filter by file ID")
    country: str | None = Field(None, max_length=100, description="Filter by country")
    speaker_name: str | None = Field(
        None, max_length=200, description="Filter by speaker name"
    )
    min_similarity: float = Field(
        0.7, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    limit: int = Field(20, ge=1, le=100, description="Maximum results")


class SimilarityResult(BaseModel):
    """Result model for sentence similarity."""

    sent_id: str
    text: str
    speaker_name: str
    country: str
    file_id: str
    dominant_topic: str
    risk_score: int
    emotion_category: str
    similarity_score: float


class SimilarityResponse(BaseModel):
    """Response model for sentence similarity."""

    query: str
    results: list[SimilarityResult]
    total_hits: int
    processing_time_ms: int


class ClusteringRequest(BaseModel):
    """Request model for semantic clustering."""

    file_id: str | None = Field(None, max_length=200, description="Filter by file ID")
    country: str | None = Field(None, max_length=100, description="Filter by country")
    dominant_topic: str | None = Field(
        None, max_length=100, description="Filter by topic"
    )
    limit: int = Field(1000, ge=10, le=5000, description="Maximum sentences to cluster")


class ClusteringResponse(BaseModel):
    """Response model for semantic clustering."""

    clusters: list[dict[str, Any]]
    total_sentences: int
    noise_count: int
    cluster_count: int
    processing_time_ms: int


class ClusterSummaryResponse(BaseModel):
    """Response model for cluster summary."""

    cluster_id: int
    size: int
    dominant_topic: str
    summary: str
    speaker_distribution: dict[str, int]
    topic_distribution: dict[str, int]
    avg_risk: float
    sample_sentences: list[str]


class TopicSummaryRequest(BaseModel):
    """Request model for topic-based summary."""

    topic: str = Field(
        ..., min_length=1, max_length=100, description="Topic to summarize"
    )
    file_id: str | None = Field(None, max_length=200, description="Filter by file ID")
    country: str | None = Field(None, max_length=100, description="Filter by country")
    start_date: str | None = Field(None, max_length=50, description="Start date filter")
    end_date: str | None = Field(None, max_length=50, description="End date filter")


class TopicSummaryResponse(BaseModel):
    """Response model for topic-based summary."""

    topic: str
    total_sentences: int
    speaker_positions: dict[str, list[dict[str, Any]]]
    speaker_statistics: dict[str, dict[str, Any]]
    temporal_evolution: list[dict[str, Any]]
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


@router.post("", response_model=HybridSearchResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    hybrid_service: HybridSearchService = Depends(get_hybrid_search_service),
) -> HybridSearchResponse:
    """
    Hybrid search combining keyword (Meilisearch) and semantic (pgvector) search using RRF.

    Supports faceted search with filters for date, speaker, country, topic, risk, and emotion.
    Returns aggregated facet counts for navigation.
    """
    import time

    start_time = time.time()

    # Perform hybrid search
    results = await hybrid_service.search(
        query=request.query,
        file_id=request.file_id,
        country=request.country,
        speaker_name=request.speaker_name,
        dominant_topic=request.dominant_topic,
        min_risk=request.min_risk,
        emotion_category=request.emotion_category,
        limit=request.limit,
        top_k_keyword=request.top_k_keyword,
        top_k_dense=request.top_k_dense,
    )

    # Get facets if requested
    facets = None
    if request.include_facets:
        facets = await hybrid_service.get_facets(
            query=request.query,
            file_id=request.file_id,
        )

    processing_time_ms = int((time.time() - start_time) * 1000)

    return HybridSearchResponse(
        results=[
            HybridSearchResult(
                sent_id=r["sent_id"],
                text=r["text"],
                speaker_name=r["speaker_name"],
                country=r["country"],
                file_id=r["file_id"],
                dominant_topic=r["dominant_topic"],
                risk_score=r["risk_score"],
                emotion_category=r["emotion_category"],
                rrf_score=r["rrf_score"],
                similarity_score=r.get("similarity_score"),
                keyword_rank=r.get("keyword_rank"),
                semantic_rank=r.get("semantic_rank"),
            )
            for r in results
        ],
        total_hits=len(results),
        query=request.query,
        facets=facets,
        processing_time_ms=processing_time_ms,
    )


@router.get("/suggest", response_model=list[Suggestion])
async def auto_suggest(
    q: str = Query(..., min_length=1, max_length=100, description="Partial query"),
    limit: int = Query(10, ge=1, le=20, description="Maximum suggestions"),
) -> list[Suggestion]:
    """
    Auto-suggest endpoint for query completion.

    Provides speaker name completions and diplomatic term suggestions.
    """
    from bb_paxdata.infrastructure.search.meilisearch_client import (
        search_sentences,
    )

    suggestions: list[Suggestion] = []

    # Get speaker suggestions from Meilisearch
    speaker_result = await search_sentences(
        query=q,
        filters=None,
        limit=limit,
    )

    speaker_counts: dict[str, int] = {}
    for hit in speaker_result.get("hits", []):
        speaker = hit.get("speaker_name", "")
        if speaker and q.lower() in speaker.lower():
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

    # Add speaker suggestions
    for speaker, count in sorted(
        speaker_counts.items(), key=lambda x: x[1], reverse=True
    )[:limit]:
        suggestions.append(Suggestion(text=speaker, type="speaker", count=count))

    # Diplomatic terms (static list for now)
    diplomatic_terms = [
        "diplomatic relations",
        "bilateral talks",
        "negotiations",
        "consensus",
        "agreement",
        "treaty",
        "summit",
        "dialogue",
        "cooperation",
        "framework",
        "protocol",
        "memorandum",
        "declaration",
        "resolution",
        "sanctions",
        "embargo",
    ]

    matching_terms = [term for term in diplomatic_terms if q.lower() in term.lower()]

    for term in matching_terms[: (limit - len(suggestions))]:
        suggestions.append(Suggestion(text=term, type="term", count=None))

    return suggestions


@router.post("/similarity", response_model=SimilarityResponse)
async def sentence_similarity(
    request: SimilarityRequest,
    similarity_service: SemanticSimilarityService = Depends(
        get_semantic_similarity_service
    ),
) -> SimilarityResponse:
    """
    Find sentences similar to the given text using pgvector cosine similarity.

    Supports threshold filtering and various filters (file, country, speaker).
    """
    import time

    start_time = time.time()

    results = await similarity_service.find_similar_sentences(
        sentence_text=request.sentence_text,
        file_id=request.file_id,
        country=request.country,
        speaker_name=request.speaker_name,
        min_similarity=request.min_similarity,
        limit=request.limit,
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    return SimilarityResponse(
        query=request.sentence_text,
        results=[
            SimilarityResult(
                sent_id=r["sent_id"],
                text=r["text"],
                speaker_name=r["speaker_name"],
                country=r["country"],
                file_id=r["file_id"],
                dominant_topic=r["dominant_topic"],
                risk_score=r["risk_score"],
                emotion_category=r["emotion_category"],
                similarity_score=r["similarity_score"],
            )
            for r in results
        ],
        total_hits=len(results),
        processing_time_ms=processing_time_ms,
    )


@router.post("/clusters", response_model=ClusteringResponse)
async def semantic_clustering(
    request: ClusteringRequest,
    clustering_service: SemanticClusteringService = Depends(
        get_semantic_clustering_service
    ),
) -> ClusteringResponse:
    """
    Perform semantic clustering on sentences using HDBSCAN.

    Groups semantically similar sentences into clusters for analysis.
    """
    import time

    start_time = time.time()

    result = await clustering_service.cluster_sentences(
        file_id=request.file_id,
        country=request.country,
        dominant_topic=request.dominant_topic,
        limit=request.limit,
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    return ClusteringResponse(
        clusters=result["clusters"],
        total_sentences=result["total_sentences"],
        noise_count=result["noise_count"],
        cluster_count=result["cluster_count"],
        processing_time_ms=processing_time_ms,
    )


@router.get("/clusters/{cluster_id}/summary", response_model=ClusterSummaryResponse)
async def cluster_summary(
    cluster_id: int,
    file_id: str | None = Query(None, description="Filter by file ID"),
    country: str | None = Query(None, description="Filter by country"),
    dominant_topic: str | None = Query(None, description="Filter by topic"),
    clustering_service: SemanticClusteringService = Depends(
        get_semantic_clustering_service
    ),
) -> ClusterSummaryResponse:
    """
    Generate AI-powered summary for a specific semantic cluster.

    Provides insights into the cluster's content and themes.
    """
    result = await clustering_service.generate_cluster_summary(
        cluster_id=cluster_id,
        file_id=file_id,
        country=country,
        dominant_topic=dominant_topic,
    )

    if "error" in result:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=result["error"])

    return ClusterSummaryResponse(
        cluster_id=result["cluster_id"],
        size=result["size"],
        dominant_topic=result["dominant_topic"],
        summary=result["summary"],
        speaker_distribution=result["speaker_distribution"],
        topic_distribution=result["topic_distribution"],
        avg_risk=result["avg_risk"],
        sample_sentences=result["sample_sentences"],
    )


@router.get("/clusters/visualization", response_model=dict[str, Any])
async def cluster_visualization(
    file_id: str | None = Query(None, description="Filter by file ID"),
    country: str | None = Query(None, description="Filter by country"),
    dominant_topic: str | None = Query(None, description="Filter by topic"),
    limit: int = Query(500, ge=10, le=2000, description="Maximum sentences"),
    clustering_service: SemanticClusteringService = Depends(
        get_semantic_clustering_service
    ),
) -> dict[str, Any]:
    """
    Get data for interactive cluster visualization.

    Returns 2D coordinates (UMAP) and cluster labels for visualization.
    """
    result = await clustering_service.get_cluster_visualization_data(
        file_id=file_id,
        country=country,
        dominant_topic=dominant_topic,
        limit=limit,
    )

    return result


@router.post("/topics/summary", response_model=TopicSummaryResponse)
async def topic_summary(
    request: TopicSummaryRequest,
    similarity_service: SemanticSimilarityService = Depends(
        get_semantic_similarity_service
    ),
) -> TopicSummaryResponse:
    """
    Get topic-based summary with speaker positions and temporal evolution.

    Answers "What was said about this topic?" with speaker breakdown.
    """
    import time

    start_time = time.time()

    result = await similarity_service.get_topic_summary(
        topic=request.topic,
        file_id=request.file_id,
        country=request.country,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    return TopicSummaryResponse(
        topic=result["topic"],
        total_sentences=result["total_sentences"],
        speaker_positions=result["speaker_positions"],
        speaker_statistics=result["speaker_statistics"],
        temporal_evolution=result["temporal_evolution"],
        processing_time_ms=processing_time_ms,
    )
