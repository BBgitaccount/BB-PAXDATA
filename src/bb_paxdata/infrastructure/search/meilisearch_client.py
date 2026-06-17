"""Meilisearch client and index management for BB-PAXDATA."""

from typing import Any

import structlog
from bb_paxdata.config.settings import get_settings
from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.models.settings import MeilisearchSettings

logger = structlog.get_logger(__name__)
_settings = get_settings()

MEILISEARCH_URL = "http://localhost:7700"
MEILISEARCH_MASTER_KEY = "paxdata-meilisearch-key"

INDEX_SENTENCES = "sentences"
INDEX_SEGMENTS = "segments"
INDEX_FILES = "files"
INDEX_COMMUNITIES = "communities"

TURKISH_STOP_WORDS = [
    "bir",
    "bu",
    "şu",
    "o",
    "biz",
    "siz",
    "onlar",
    "ve",
    "veya",
    "ile",
    "için",
    "da",
    "de",
    "ki",
    "ama",
    "fakat",
    "lakin",
    "ancak",
    "çünkü",
    "yani",
    "ise",
    "gibi",
    "kadar",
    "daha",
]

SETTINGS_SENTENCES = MeilisearchSettings(
    searchable_attributes=[
        "text",
        "speaker_name",
        "country",
        "dominant_topic",
    ],
    filterable_attributes=[
        "country",
        "speaker_name",
        "risk_score",
        "file_id",
        "seg_id",
        "emotion_category",
        "dominant_topic",
    ],
    sortable_attributes=["risk_score", "vader_compound"],
    ranking_rules=["words", "typo", "proximity", "attribute", "sort", "exactness"],
    stop_words=TURKISH_STOP_WORDS,
    typo_tolerance={
        "enabled": True,
        "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
    },
)

SETTINGS_SEGMENTS = MeilisearchSettings(
    searchable_attributes=[
        "text",
        "speaker_name",
        "country",
        "dominant_topic",
        "key_phrases",
    ],
    filterable_attributes=[
        "country",
        "speaker_name",
        "file_id",
        "emotion_category",
        "dominant_topic",
        "risk_score",
    ],
    sortable_attributes=["risk_score", "duration_sec"],
    ranking_rules=["words", "typo", "proximity", "attribute", "sort", "exactness"],
    stop_words=TURKISH_STOP_WORDS,
    typo_tolerance={
        "enabled": True,
        "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
    },
)

SETTINGS_FILES = MeilisearchSettings(
    searchable_attributes=[
        "file_name",
        "title",
        "inferred_theme",
    ],
    filterable_attributes=[
        "panel_number",
        "inferred_theme",
        "date_str",
    ],
    sortable_attributes=["n_segments", "n_sentences", "total_words"],
    ranking_rules=["words", "typo", "proximity", "attribute", "sort", "exactness"],
    stop_words=TURKISH_STOP_WORDS,
)

SETTINGS_COMMUNITIES = MeilisearchSettings(
    searchable_attributes=["community_name", "node_labels", "description"],
    filterable_attributes=["cohesion_score", "node_count", "edge_count"],
    sortable_attributes=["cohesion_score", "node_count"],
)


async def get_meilisearch_client() -> AsyncClient:
    """Return a shared async Meilisearch client."""
    url = getattr(_settings, "meilisearch_url", None) or MEILISEARCH_URL
    key = getattr(_settings, "meilisearch_master_key", None) or MEILISEARCH_MASTER_KEY
    return AsyncClient(url=url, api_key=key)


async def ensure_indexes() -> None:
    """Idempotently create and configure the sentences, segments, files, and communities indexes."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index_configs = [
            (INDEX_SENTENCES, SETTINGS_SENTENCES, "sent_id"),
            (INDEX_SEGMENTS, SETTINGS_SEGMENTS, "seg_id"),
            (INDEX_FILES, SETTINGS_FILES, "file_id"),
            (INDEX_COMMUNITIES, SETTINGS_COMMUNITIES, "id"),
        ]
        for idx, settings, primary_key in index_configs:
            try:
                index = await client.get_index(idx)
            except Exception:
                await client.create_index(idx, primary_key=primary_key)
                index = await client.get_index(idx)
            await index.update_settings(settings)
        logger.info("Meilisearch indexes configured successfully.")


async def index_sentences(documents: list[dict[str, Any]]) -> None:
    """Bulk-index sentence documents. Upserts by sent_id."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_SENTENCES)
        await index.add_documents(documents, primary_key="sent_id")


async def index_segments(documents: list[dict[str, Any]]) -> None:
    """Bulk-index segment documents. Upserts by seg_id."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_SEGMENTS)
        await index.add_documents(documents, primary_key="seg_id")


async def index_files(documents: list[dict[str, Any]]) -> None:
    """Bulk-index file documents. Upserts by file_id."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_FILES)
        await index.add_documents(documents, primary_key="file_id")


async def index_communities(documents: list[dict[str, Any]]) -> None:
    """Bulk-index community documents. Upserts by id."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_COMMUNITIES)
        await index.add_documents(documents, primary_key="id")


async def search_sentences(
    query: str,
    filters: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Full-text search over sentences with optional filter."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_SENTENCES)
        result = await index.search(
            query=query,
            filter=filters,
            limit=limit,
            offset=offset,
            attributes_to_highlight=["text"],
        )
        return result.model_dump()


async def search_segments(
    query: str,
    filters: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Full-text search over segments with optional filter."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_SEGMENTS)
        result = await index.search(
            query=query,
            filter=filters,
            limit=limit,
            offset=offset,
            attributes_to_highlight=["text"],
        )
        return result.model_dump()


async def search_files(
    query: str,
    filters: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Full-text search over files with optional filter."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_FILES)
        result = await index.search(
            query=query,
            filter=filters,
            limit=limit,
            offset=offset,
            attributes_to_highlight=["title", "file_name"],
        )
        return result.model_dump()


async def search_communities(
    query: str,
    filters: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Full-text search over communities with optional filter."""
    async with await get_meilisearch_client() as client:  # type: ignore
        index = await client.get_index(INDEX_COMMUNITIES)
        result = await index.search(
            query=query,
            filter=filters,
            limit=limit,
            offset=offset,
        )
        return result.model_dump()
