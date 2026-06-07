"""GAT Feature Extraction Service — SBERT mean-pooling for actors and concepts.

(GAP-03) This service computes initial features for GAT nodes:
- Actor features: Mean-pooled SBERT embeddings of actor sentences
- Concept features: Topic centroid embeddings (BERTopic or SBERT)

Routes through existing SBERTEmbeddingService cache layer to avoid redundant inference.
"""

from __future__ import annotations

import logging

from bb_paxdata.application.domain.ports.embedding_port import EmbeddingService

logger = logging.getLogger(__name__)


class GATFeatureExtractionService:
    """Extracts initial features for GAT graph nodes.

    Computes:
    - Actor features: Mean-pooled SBERT embeddings of actor sentences
    - Concept features: Topic centroid embeddings (from topic descriptions or BERTopic)

    Uses the existing EmbeddingService (SBERTEmbeddingService) which includes
    Redis + In-Memory LRU cache for efficiency.
    """

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedding_service = embedding_service

    async def extract_actor_features(
        self,
        actor_sentences: dict[str, list[str]],
    ) -> dict[str, list[float]]:
        """Compute mean-pooled SBERT embeddings for each actor.

        Args:
            actor_sentences: {actor_id: [sentence1, sentence2, ...]}

        Returns:
            {actor_id: [384-dim float vector]}
        """
        if not actor_sentences:
            return {}

        actor_features: dict[str, list[float]] = {}

        for actor_id, sentences in actor_sentences.items():
            if not sentences:
                # Fallback: zero vector for actors with no sentences
                dim = self._embedding_service.get_model_dimension()
                actor_features[actor_id] = [0.0] * dim
                logger.warning(
                    f"Actor {actor_id} has no sentences, using zero vector fallback"
                )
                continue

            # Get embeddings for all sentences
            embeddings = await self._embedding_service.get_embeddings(sentences)
            # Mean-pool across sentences
            mean_embedding = embeddings.mean(axis=0)
            actor_features[actor_id] = mean_embedding.tolist()

        logger.info(f"Extracted features for {len(actor_features)} actors")
        return actor_features

    async def extract_concept_features(
        self,
        concept_descriptions: dict[str, str],
    ) -> dict[str, list[float]]:
        """Compute SBERT embeddings for concept/topic descriptions.

        Args:
            concept_descriptions: {concept_id: "topic description or representative text"}

        Returns:
            {concept_id: [384-dim float vector]}
        """
        if not concept_descriptions:
            return {}

        concept_ids = list(concept_descriptions.keys())
        descriptions = [concept_descriptions[cid] for cid in concept_ids]

        # Batch compute embeddings
        embeddings = await self._embedding_service.get_embeddings(descriptions)

        concept_features = {
            cid: emb.tolist() for cid, emb in zip(concept_ids, embeddings)
        }

        logger.info(f"Extracted features for {len(concept_features)} concepts")
        return concept_features

    async def extract_all_features(
        self,
        actor_sentences: dict[str, list[str]],
        concept_descriptions: dict[str, str],
    ) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
        """Extract both actor and concept features in parallel.

        Args:
            actor_sentences: {actor_id: [sentence1, sentence2, ...]}
            concept_descriptions: {concept_id: "topic description"}

        Returns:
            (actor_features, concept_features)
        """
        import asyncio

        actor_task = self.extract_actor_features(actor_sentences)
        concept_task = self.extract_concept_features(concept_descriptions)

        actor_features, concept_features = await asyncio.gather(
            actor_task, concept_task
        )

        return actor_features, concept_features
