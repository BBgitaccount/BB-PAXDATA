"""Meilisearch client and index management for BB-PAXDATA."""

import logging
from typing import Any

from bb_paxdata.config.settings import get_settings
from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.models.settings import MeilisearchSettings

logger = logging.getLogger(__name__)
_settings = get_settings()

MEILISEARCH_URL = "http://localhost:7700"
MEILISEARCH_MASTER_KEY = "paxdata-meilisearch-key"

INDEX_SENTENCES = "sentences"
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
        "sentence_text",
        "speaker_name",
        "country",
        "AI_Birincil_Konu",
    ],
    filterable_attributes=[
        "country",
        "speaker_name",
        "AI_Risk_Skoru",
        "AI_Diplomatik_Ton",
        "file_id",
        "created_at",
    ],
    sortable_attributes=["AI_Risk_Skoru", "created_at"],
    ranking_rules=["words", "typo", "proximity", "attribute", "sort", "exactness"],
    stop_words=TURKISH_STOP_WORDS,
    typo_tolerance={
        "enabled": True,
        "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
    },
)

SETTINGS_COMMUNITIES = MeilisearchSettings(
    searchable_attributes=["community_name", "node_labels", "description"],
    filterable_attributes=["cohesion_score", "node_count", "edge_count"],
    sortable_attributes=["cohesion_score", "node_count"],
)


async def get_meilisearch_client() -> AsyncClient:
    """Return a shared async Meilisearch client."""
    url = getattr(_settings, "meilisearch_url", MEILISEARCH_URL)
    key = getattr(_settings, "meilisearch_master_key", MEILISEARCH_MASTER_KEY)
    return AsyncClient(url=url, api_key=key)


async def ensure_indexes() -> None:
    """Idempotently create and configure the sentences and communities indexes."""
    async with await get_meilisearch_client() as client:
        for idx, settings in [
            (INDEX_SENTENCES, SETTINGS_SENTENCES),
            (INDEX_COMMUNITIES, SETTINGS_COMMUNITIES),
        ]:
            try:
                index = await client.get_index(idx)
            except Exception:
                await client.create_index(
                    idx, primary_key="id" if idx == INDEX_COMMUNITIES else "sent_id"
                )
                index = await client.get_index(idx)
            await index.update_settings(settings)
        logger.info("Meilisearch indexes configured successfully.")


async def index_sentences(documents: list[dict[str, Any]]) -> None:
    """Bulk-index sentence documents. Upserts by sent_id."""
    async with await get_meilisearch_client() as client:
        index = await client.get_index(INDEX_SENTENCES)
        await index.add_documents(documents, primary_key="sent_id")


async def index_communities(documents: list[dict[str, Any]]) -> None:
    """Bulk-index community documents. Upserts by id."""
    async with await get_meilisearch_client() as client:
        index = await client.get_index(INDEX_COMMUNITIES)
        await index.add_documents(documents, primary_key="id")


async def search_sentences(
    query: str,
    filters: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Full-text search over sentences with optional filter."""
    async with await get_meilisearch_client() as client:
        index = await client.get_index(INDEX_SENTENCES)
        result = await index.search(
            query=query,
            filter=filters,
            limit=limit,
            offset=offset,
            attributes_to_highlight=["sentence_text"],
        )
        return result.model_dump()


async def search_communities(
    query: str,
    filters: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Full-text search over communities with optional filter."""
    async with await get_meilisearch_client() as client:
        index = await client.get_index(INDEX_COMMUNITIES)
        result = await index.search(
            query=query,
            filter=filters,
            limit=limit,
            offset=offset,
        )
        return result.model_dump()
