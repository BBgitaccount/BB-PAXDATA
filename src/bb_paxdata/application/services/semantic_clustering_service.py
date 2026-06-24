"""Semantic clustering service using HDBSCAN for sentence grouping."""

from collections.abc import Callable
from typing import Any

import numpy as np
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.services.semantic_similarity_service import (
    SemanticSimilarityService,
)

logger = structlog.get_logger(__name__)


class SemanticClusteringService:
    """Service for semantic clustering using HDBSCAN."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        similarity_service: SemanticSimilarityService,
        min_cluster_size: int = 5,
        min_samples: int | None = None,
    ) -> None:
        """
        Initialize semantic clustering service.

        Args:
            session_factory: Database session factory
            similarity_service: Semantic similarity service for embeddings
            min_cluster_size: Minimum cluster size for HDBSCAN
            min_samples: Minimum samples for HDBSCAN (default: min_cluster_size)
        """
        self._session_factory = session_factory
        self._similarity_service = similarity_service
        self._min_cluster_size = min_cluster_size
        self._min_samples = min_samples or min_cluster_size

    async def cluster_sentences(
        self,
        file_id: str | None = None,
        country: str | None = None,
        dominant_topic: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """
        Perform semantic clustering on sentences using HDBSCAN.

        Args:
            file_id: Optional file filter
            country: Optional country filter
            dominant_topic: Optional topic filter
            limit: Maximum number of sentences to cluster

        Returns:
            Dictionary with cluster assignments and metadata
        """
        # Get embeddings
        sentence_ids, embeddings, metadata = (
            await self._similarity_service.get_sentence_embeddings_for_clustering(
                file_id=file_id,
                country=country,
                dominant_topic=dominant_topic,
                limit=limit,
            )
        )

        if not embeddings:
            return {
                "clusters": [],
                "total_sentences": 0,
                "noise_count": 0,
                "cluster_count": 0,
            }

        # Convert to numpy array
        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Perform HDBSCAN clustering
        try:
            import hdbscan

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=self._min_cluster_size,
                min_samples=self._min_samples,
                metric="cosine",
                cluster_selection_method="eom",
            )

            cluster_labels = clusterer.fit_predict(embeddings_array)

            # Get cluster probabilities
            probabilities = clusterer.probabilities_

        except ImportError:
            logger.warning("HDBSCAN not available, using KMeans fallback")
            from sklearn.cluster import KMeans

            # Estimate number of clusters using elbow method
            n_clusters = min(10, len(embeddings) // self._min_cluster_size)
            n_clusters = max(n_clusters, 2)

            clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = clusterer.fit_predict(embeddings_array)
            probabilities = np.ones(len(cluster_labels))

        # Group sentences by cluster
        clusters: dict[int, list[dict[str, Any]]] = {}
        noise_count = 0

        for sent_id, label, prob, meta in zip(
            sentence_ids, cluster_labels, probabilities, metadata
        ):
            if label == -1:  # Noise point
                noise_count += 1
                continue

            if label not in clusters:
                clusters[label] = []

            clusters[label].append(
                {
                    **meta,
                    "cluster_probability": float(prob),
                }
            )

        # Sort clusters by size
        sorted_clusters = sorted(
            clusters.items(), key=lambda x: len(x[1]), reverse=True
        )

        # Calculate cluster statistics
        cluster_stats = []
        for label, sentences in sorted_clusters:
            # Get dominant topic in cluster
            topic_counts: dict[str, int] = {}
            speaker_counts: dict[str, int] = {}

            for sent in sentences:
                topic = sent["dominant_topic"]
                speaker = sent["speaker_name"]

                topic_counts[topic] = topic_counts.get(topic, 0) + 1
                speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

            dominant_topic = (
                max(topic_counts.items(), key=lambda x: x[1])[0] if topic_counts else ""
            )
            avg_risk = sum(s["risk_score"] for s in sentences) / len(sentences)

            cluster_stats.append(
                {
                    "cluster_id": int(label),
                    "size": len(sentences),
                    "dominant_topic": dominant_topic,
                    "topic_distribution": topic_counts,
                    "speaker_distribution": speaker_counts,
                    "avg_risk": avg_risk,
                    "sentences": sentences[:10],  # Return first 10 for preview
                }
            )

        logger.info(
            "clustering_completed",
            total_sentences=len(sentence_ids),
            cluster_count=len(clusters),
            noise_count=noise_count,
        )

        return {
            "clusters": cluster_stats,
            "total_sentences": len(sentence_ids),
            "noise_count": noise_count,
            "cluster_count": len(clusters),
        }

    async def generate_cluster_summary(
        self,
        cluster_id: int,
        file_id: str | None = None,
        country: str | None = None,
        dominant_topic: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate AI-powered summary for a specific cluster.

        Args:
            cluster_id: Cluster ID to summarize
            file_id: Optional file filter
            country: Optional country filter
            dominant_topic: Optional topic filter

        Returns:
            Dictionary with cluster summary
        """
        # Get clustering results
        clustering_result = await self.cluster_sentences(
            file_id=file_id,
            country=country,
            dominant_topic=dominant_topic,
            limit=1000,
        )

        # Find the requested cluster
        cluster = next(
            (c for c in clustering_result["clusters"] if c["cluster_id"] == cluster_id),
            None,
        )

        if not cluster:
            return {
                "error": f"Cluster {cluster_id} not found",
                "cluster_id": cluster_id,
            }

        # Extract sentences for summary
        sentences = [s["text"] for s in cluster["sentences"]]

        # Generate summary (placeholder for AI generation)
        # In production, this would call an LLM service
        summary_text = self._generate_summary_placeholder(
            sentences,
            cluster["dominant_topic"],
            cluster["speaker_distribution"],
        )

        return {
            "cluster_id": cluster_id,
            "size": cluster["size"],
            "dominant_topic": cluster["dominant_topic"],
            "summary": summary_text,
            "speaker_distribution": cluster["speaker_distribution"],
            "topic_distribution": cluster["topic_distribution"],
            "avg_risk": cluster["avg_risk"],
            "sample_sentences": sentences[:5],
        }

    def _generate_summary_placeholder(
        self,
        sentences: list[str],
        dominant_topic: str,
        speaker_distribution: dict[str, int],
    ) -> str:
        """
        Generate a placeholder summary (to be replaced with AI generation).

        Args:
            sentences: Sentences in the cluster
            dominant_topic: Dominant topic
            speaker_distribution: Distribution of speakers

        Returns:
            Summary text
        """
        top_speakers = sorted(
            speaker_distribution.items(), key=lambda x: x[1], reverse=True
        )[:3]

        speakers_text = ", ".join([s[0] for s in top_speakers])

        summary = (
            f"This cluster contains {len(sentences)} sentences primarily about {dominant_topic}. "
            f"Main speakers: {speakers_text}. "
            f"The sentences share semantic similarity and discuss related concepts within this topic. "
        )

        return summary

    async def get_cluster_visualization_data(
        self,
        file_id: str | None = None,
        country: str | None = None,
        dominant_topic: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        """
        Get data for interactive cluster visualization.

        Uses UMAP for dimensionality reduction to 2D for visualization.

        Args:
            file_id: Optional file filter
            country: Optional country filter
            dominant_topic: Optional topic filter
            limit: Maximum number of sentences

        Returns:
            Dictionary with 2D coordinates and cluster labels
        """
        # Get embeddings
        sentence_ids, embeddings, metadata = (
            await self._similarity_service.get_sentence_embeddings_for_clustering(
                file_id=file_id,
                country=country,
                dominant_topic=dominant_topic,
                limit=limit,
            )
        )

        if not embeddings:
            return {
                "points": [],
                "total_sentences": 0,
            }

        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Perform clustering
        try:
            import hdbscan

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=self._min_cluster_size,
                min_samples=self._min_samples,
                metric="cosine",
            )
            cluster_labels = clusterer.fit_predict(embeddings_array)
        except ImportError:
            from sklearn.cluster import KMeans

            n_clusters = min(10, len(embeddings) // self._min_cluster_size)
            n_clusters = max(n_clusters, 2)

            clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = clusterer.fit_predict(embeddings_array)

        # Dimensionality reduction for visualization
        try:
            import umap

            reducer = umap.UMAP(
                n_components=2,
                metric="cosine",
                random_state=42,
            )
            embeddings_2d = reducer.fit_transform(embeddings_array)
        except ImportError:
            from sklearn.decomposition import PCA

            reducer = PCA(n_components=2, random_state=42)
            embeddings_2d = reducer.fit_transform(embeddings_array)

        # Prepare visualization data
        points = []
        for sent_id, coords, label, meta in zip(
            sentence_ids, embeddings_2d, cluster_labels, metadata
        ):
            points.append(
                {
                    "sent_id": sent_id,
                    "x": float(coords[0]),
                    "y": float(coords[1]),
                    "cluster": int(label),
                    "text": meta["text"],
                    "speaker": meta["speaker_name"],
                    "country": meta["country"],
                    "topic": meta["dominant_topic"],
                }
            )

        return {
            "points": points,
            "total_sentences": len(points),
            "cluster_count": len(set(cluster_labels) - {-1}),
        }
