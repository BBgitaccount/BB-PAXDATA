# src/bb_paxdata/interfaces/api/routers/v1/visualization.py

import hashlib
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import DTOs
from bb_paxdata.application.domain.dtos.visualization_dtos import (
    BilateralFlowDTO,
    CountryNodeDTO,
    CountryRiskProfileDTO,
    ReferenceFlowDTO,
    SentimentMatrixDTO,
    SessionTimelineDTO,
)
from bb_paxdata.application.use_cases.visualization.get_bilateral_flows_use_case import (
    GetBilateralFlowsUseCase,
)

# Import Use Cases
from bb_paxdata.application.use_cases.visualization.get_country_nodes_use_case import (
    GetCountryNodesUseCase,
)
from bb_paxdata.application.use_cases.visualization.get_country_risk_profile_use_case import (
    GetCountryRiskProfileUseCase,
)
from bb_paxdata.application.use_cases.visualization.get_reference_flows_use_case import (
    GetReferenceFlowsUseCase,
)
from bb_paxdata.application.use_cases.visualization.get_sentiment_matrix_use_case import (
    GetSentimentMatrixUseCase,
)
from bb_paxdata.application.use_cases.visualization.get_session_timeline_use_case import (
    GetSessionTimelineUseCase,
)
from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.infrastructure.db.repositories.visualization_repository import (
    VisualizationRepository,
)
from bb_paxdata.interfaces.api.dependencies import (
    get_cache,
    get_current_reviewer,
    get_db,
)

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/viz",
    tags=["Visualization"],
    dependencies=[Depends(get_current_reviewer)],
)


def get_visualization_repository(
    db: AsyncSession = Depends(get_db),
) -> VisualizationRepository:
    """Dependency injection helper for the Visualization Repository."""
    return VisualizationRepository(db)


def generate_cache_key(endpoint: str, params: dict[str, Any]) -> str:
    """
    Generates a deterministic cache key by sorting parameters
    and hashing their string representation.
    """
    parts = []
    for k in sorted(params.keys()):
        v = params[k]
        if v is None:
            parts.append(f"{k}=None")
        elif isinstance(v, list):
            parts.append(f"{k}={sorted(str(x) for x in v)}")
        else:
            parts.append(f"{k}={v}")
    param_str = "&".join(parts)
    param_hash = hashlib.md5(
        param_str.encode("utf-8"), usedforsecurity=False
    ).hexdigest()
    return f"viz:{endpoint}:{param_hash}"


@router.get("/country-nodes", response_model=list[CountryNodeDTO])
async def get_country_nodes(
    request: Request,
    session_id: list[str] | None = Query(None),
    relationship_type: list[str] | None = Query(None),
    repo: VisualizationRepository = Depends(get_visualization_repository),
    cache: RedisCacheBackend = Depends(get_cache),
) -> list[CountryNodeDTO]:
    """
    Retrieves statistical nodes for each country involved in diplomatic discourse.
    Allows filtering by session IDs and relationship types.
    """
    cache_params = {"session_id": session_id, "relationship_type": relationship_type}
    cache_key = generate_cache_key("country-nodes", cache_params)

    cached = await cache.get(cache_key)
    if cached is not None:
        logger.info("cache hit", cache_key=cache_key)
        return [CountryNodeDTO(**c) for c in cached]

    use_case = GetCountryNodesUseCase(repo)
    result = await use_case.execute(session_id, relationship_type)

    # Store serialized result in cache
    serialized = [r.model_dump() for r in result]
    await cache.set(cache_key, serialized, ttl=300)

    return result


@router.get("/bilateral-flows", response_model=list[BilateralFlowDTO])
async def get_bilateral_flows(
    request: Request,
    session_id: list[str] | None = Query(None),
    min_interactions: int = Query(2),
    relationship_types: list[str] | None = Query(None),
    min_affinity: float = Query(-1.0),
    repo: VisualizationRepository = Depends(get_visualization_repository),
    cache: RedisCacheBackend = Depends(get_cache),
) -> list[BilateralFlowDTO]:
    """
    Retrieves aggregated bilateral interaction flows between country pairs.
    Filters out pairs below min_interactions or min_affinity.
    """
    cache_params = {
        "session_id": session_id,
        "min_interactions": min_interactions,
        "relationship_types": relationship_types,
        "min_affinity": min_affinity,
    }
    cache_key = generate_cache_key("bilateral-flows", cache_params)

    cached = await cache.get(cache_key)
    if cached is not None:
        logger.info("cache hit", cache_key=cache_key)
        return [BilateralFlowDTO(**b) for b in cached]

    use_case = GetBilateralFlowsUseCase(repo)
    result = await use_case.execute(
        session_ids=session_id,
        min_interactions=min_interactions,
        relationship_types=relationship_types,
        min_affinity=min_affinity,
    )

    serialized = [r.model_dump() for r in result]
    await cache.set(cache_key, serialized, ttl=300)

    return result


@router.get("/sentiment-matrix", response_model=SentimentMatrixDTO)
async def get_sentiment_matrix(
    request: Request,
    repo: VisualizationRepository = Depends(get_visualization_repository),
    cache: RedisCacheBackend = Depends(get_cache),
) -> SentimentMatrixDTO:
    """
    Retrieves global N x N matrices representing average sentiments,
    interaction counts, and relationship classifications between all countries.
    """
    cache_key = generate_cache_key("sentiment-matrix", {})

    cached = await cache.get(cache_key)
    if cached is not None:
        logger.info("cache hit", cache_key=cache_key)
        return SentimentMatrixDTO(**cached)

    use_case = GetSentimentMatrixUseCase(repo)
    result = await use_case.execute()

    await cache.set(cache_key, result.model_dump(), ttl=300)

    return result


@router.get("/session-timeline", response_model=list[SessionTimelineDTO])
async def get_session_timeline(
    request: Request,
    repo: VisualizationRepository = Depends(get_visualization_repository),
    cache: RedisCacheBackend = Depends(get_cache),
) -> list[SessionTimelineDTO]:
    """
    Retrieves the chronological progression of sessions along with key metrics,
    active countries, and top relationships per session.
    """
    cache_key = generate_cache_key("session-timeline", {})

    cached = await cache.get(cache_key)
    if cached is not None:
        logger.info("cache hit", cache_key=cache_key)
        return [SessionTimelineDTO(**s) for s in cached]

    use_case = GetSessionTimelineUseCase(repo)
    result = await use_case.execute()

    serialized = [r.model_dump() for r in result]
    await cache.set(cache_key, serialized, ttl=300)

    return result


@router.get("/reference-flows", response_model=list[ReferenceFlowDTO])
async def get_reference_flows(
    request: Request,
    session_id: str | None = Query(None),
    context_type: str | None = Query(None),
    repo: VisualizationRepository = Depends(get_visualization_repository),
    cache: RedisCacheBackend = Depends(get_cache),
) -> list[ReferenceFlowDTO]:
    """
    Retrieves directed citation/reference flows between countries.
    Groups by speaker country, target country, and citation context.
    """
    cache_params = {"session_id": session_id, "context_type": context_type}
    cache_key = generate_cache_key("reference-flows", cache_params)

    cached = await cache.get(cache_key)
    if cached is not None:
        logger.info("cache hit", cache_key=cache_key)
        return [ReferenceFlowDTO(**rf) for rf in cached]

    use_case = GetReferenceFlowsUseCase(repo)
    result = await use_case.execute(session_id, context_type)

    serialized = [r.model_dump() for r in result]
    await cache.set(cache_key, serialized, ttl=300)

    return result


@router.get("/country-risk-profile", response_model=CountryRiskProfileDTO)
async def get_country_risk_profile(
    request: Request,
    country: str = Query(...),
    repo: VisualizationRepository = Depends(get_visualization_repository),
    cache: RedisCacheBackend = Depends(get_cache),
) -> CountryRiskProfileDTO:
    """
    Retrieves a comprehensive security and risk report for a specific country,
    calculating sentiment asymmetries, alliance breakdowns, and top accusers.
    """
    cache_params = {"country": country}
    cache_key = generate_cache_key("country-risk-profile", cache_params)

    cached = await cache.get(cache_key)
    if cached is not None:
        logger.info("cache hit", cache_key=cache_key)
        return CountryRiskProfileDTO(**cached)

    use_case = GetCountryRiskProfileUseCase(repo)
    result = await use_case.execute(country)

    await cache.set(cache_key, result.model_dump(), ttl=300)

    return result
