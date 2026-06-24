"""Tests for hybrid search API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_hybrid_search_service():
    """Mock hybrid search service."""
    service = MagicMock()
    service.search = AsyncMock()
    service.get_facets = AsyncMock()
    return service


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    service = MagicMock()
    service.get_embeddings = AsyncMock()
    return service


class TestHybridSearch:
    """Tests for hybrid search endpoint."""

    def test_hybrid_search_request_validation(self, client: TestClient):
        """Test that hybrid search request validates required fields."""
        # Missing query field
        response = client.post(
            "/api/v1/search",
            json={
                "country": "Turkey",
                "limit": 20,
            },
        )
        assert response.status_code == 422

        # Invalid limit (too high)
        response = client.post(
            "/api/v1/search",
            json={
                "query": "test query",
                "limit": 200,
            },
        )
        assert response.status_code == 422

    @patch("bb_paxdata.interfaces.api.routers.v1.search.HybridSearchService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_hybrid_search_success(
        self,
        mock_sbert_class,
        mock_hybrid_class,
        client: TestClient,
        mock_hybrid_search_service,
    ):
        """Test successful hybrid search."""
        # Setup mocks
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance
        mock_hybrid_class.return_value = mock_hybrid_search_service

        # Mock search results
        mock_hybrid_search_service.search.return_value = [
            {
                "sent_id": "sent1",
                "text": "Test sentence",
                "speaker_name": "Speaker A",
                "country": "Turkey",
                "file_id": "file1",
                "dominant_topic": "diplomacy",
                "risk_score": 5,
                "emotion_category": "neutral",
                "rrf_score": 0.5,
                "similarity_score": 0.8,
                "keyword_rank": 1,
                "semantic_rank": 2,
            }
        ]

        # Mock facets
        mock_hybrid_search_service.get_facets.return_value = {
            "countries": {"Turkey": 100, "USA": 50},
            "speakers": {"Speaker A": 30},
            "topics": {"diplomacy": 80},
            "emotions": {"neutral": 60},
        }

        response = client.post(
            "/api/v1/search",
            json={
                "query": "diplomatic relations",
                "country": "Turkey",
                "limit": 20,
                "include_facets": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["sent_id"] == "sent1"
        assert data["results"][0]["rrf_score"] == 0.5
        assert data["facets"] is not None
        assert "countries" in data["facets"]

        # Verify service was called correctly
        mock_hybrid_search_service.search.assert_called_once()
        call_args = mock_hybrid_search_service.search.call_args
        assert call_args.kwargs["query"] == "diplomatic relations"
        assert call_args.kwargs["country"] == "Turkey"

    @patch("bb_paxdata.interfaces.api.routers.v1.search.HybridSearchService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_hybrid_search_without_facets(
        self,
        mock_sbert_class,
        mock_hybrid_class,
        client: TestClient,
        mock_hybrid_search_service,
    ):
        """Test hybrid search without facets."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance
        mock_hybrid_class.return_value = mock_hybrid_search_service

        mock_hybrid_search_service.search.return_value = []

        response = client.post(
            "/api/v1/search",
            json={
                "query": "test",
                "include_facets": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["facets"] is None
        mock_hybrid_search_service.get_facets.assert_not_called()

    @patch("bb_paxdata.interfaces.api.routers.v1.search.HybridSearchService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_hybrid_search_with_all_filters(
        self,
        mock_sbert_class,
        mock_hybrid_class,
        client: TestClient,
        mock_hybrid_search_service,
    ):
        """Test hybrid search with all available filters."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance
        mock_hybrid_class.return_value = mock_hybrid_search_service

        mock_hybrid_search_service.search.return_value = []
        mock_hybrid_search_service.get_facets.return_value = {}

        response = client.post(
            "/api/v1/search",
            json={
                "query": "test",
                "file_id": "file1",
                "country": "Turkey",
                "speaker_name": "Speaker A",
                "dominant_topic": "diplomacy",
                "min_risk": 5,
                "emotion_category": "neutral",
                "limit": 10,
                "top_k_keyword": 30,
                "top_k_dense": 30,
            },
        )

        assert response.status_code == 200

        # Verify all filters were passed
        call_args = mock_hybrid_search_service.search.call_args
        assert call_args.kwargs["file_id"] == "file1"
        assert call_args.kwargs["country"] == "Turkey"
        assert call_args.kwargs["speaker_name"] == "Speaker A"
        assert call_args.kwargs["dominant_topic"] == "diplomacy"
        assert call_args.kwargs["min_risk"] == 5
        assert call_args.kwargs["emotion_category"] == "neutral"
        assert call_args.kwargs["limit"] == 10
        assert call_args.kwargs["top_k_keyword"] == 30
        assert call_args.kwargs["top_k_dense"] == 30


class TestAutoSuggest:
    """Tests for auto-suggest endpoint."""

    @patch("bb_paxdata.interfaces.api.routers.v1.search.search_sentences")
    def test_auto_suggest_speakers(self, mock_search, client: TestClient):
        """Test auto-suggest returns speaker suggestions."""
        mock_search.return_value = {
            "hits": [
                {"speaker_name": "Speaker A"},
                {"speaker_name": "Speaker A"},
                {"speaker_name": "Speaker B"},
            ]
        }

        response = client.get("/api/v1/search/suggest?q=Speaker&limit=10")

        assert response.status_code == 200
        suggestions = response.json()
        assert len(suggestions) > 0

        # Check speaker suggestions
        speaker_suggestions = [s for s in suggestions if s["type"] == "speaker"]
        assert len(speaker_suggestions) > 0
        assert speaker_suggestions[0]["text"] == "Speaker A"
        assert speaker_suggestions[0]["count"] == 2

    @patch("bb_paxdata.interfaces.api.routers.v1.search.search_sentences")
    def test_auto_suggest_diplomatic_terms(self, mock_search, client: TestClient):
        """Test auto-suggest returns diplomatic term suggestions."""
        mock_search.return_value = {"hits": []}

        response = client.get("/api/v1/search/suggest?q=dipl&limit=10")

        assert response.status_code == 200
        suggestions = response.json()

        # Check for diplomatic term suggestions
        term_suggestions = [s for s in suggestions if s["type"] == "term"]
        assert len(term_suggestions) > 0
        assert any("diplomatic" in s["text"].lower() for s in term_suggestions)

    @patch("bb_paxdata.interfaces.api.routers.v1.search.search_sentences")
    def test_auto_suggest_empty_query(self, mock_search, client: TestClient):
        """Test auto-suggest with empty query returns validation error."""
        response = client.get("/api/v1/search/suggest?q=")

        assert response.status_code == 422

    @patch("bb_paxdata.interfaces.api.routers.v1.search.search_sentences")
    def test_auto_suggest_limit(self, mock_search, client: TestClient):
        """Test auto-suggest respects limit parameter."""
        mock_search.return_value = {
            "hits": [{"speaker_name": f"Speaker {i}"} for i in range(20)]
        }

        response = client.get("/api/v1/search/suggest?q=Speaker&limit=5")

        assert response.status_code == 200
        suggestions = response.json()
        assert len(suggestions) <= 5


class TestRRFService:
    """Tests for RRF logic in hybrid search service."""

    def test_rrf_combines_results(self):
        """Test that RRF correctly combines keyword and semantic results."""
        from bb_paxdata.application.services.hybrid_search_service import (
            HybridSearchService,
        )

        service = HybridSearchService(
            session_factory=MagicMock(),
            embedding_service=MagicMock(),
            rrf_k=60,
        )

        keyword_results = [
            {
                "sent_id": "sent1",
                "text": "Test",
                "speaker_name": "A",
                "country": "TR",
                "file_id": "f1",
                "dominant_topic": "diplomacy",
                "risk_score": 5,
                "emotion_category": "neutral",
                "keyword_rank": 1,
                "semantic_rank": None,
            },
            {
                "sent_id": "sent2",
                "text": "Test 2",
                "speaker_name": "B",
                "country": "US",
                "file_id": "f1",
                "dominant_topic": "trade",
                "risk_score": 3,
                "emotion_category": "positive",
                "keyword_rank": 2,
                "semantic_rank": None,
            },
        ]

        semantic_results = [
            {
                "sent_id": "sent1",
                "text": "Test",
                "speaker_name": "A",
                "country": "TR",
                "file_id": "f1",
                "dominant_topic": "diplomacy",
                "risk_score": 5,
                "emotion_category": "neutral",
                "keyword_rank": None,
                "semantic_rank": 1,
                "similarity_score": 0.9,
            },
            {
                "sent_id": "sent3",
                "text": "Test 3",
                "speaker_name": "C",
                "country": "UK",
                "file_id": "f2",
                "dominant_topic": "security",
                "risk_score": 7,
                "emotion_category": "negative",
                "keyword_rank": None,
                "semantic_rank": 2,
                "similarity_score": 0.8,
            },
        ]

        combined = service._apply_rrf(keyword_results, semantic_results, k=60)

        # Should have 3 unique results
        assert len(combined) == 3

        # sent1 should have highest score (appears in both)
        sent1_result = next(r for r in combined if r["sent_id"] == "sent1")
        sent2_result = next(r for r in combined if r["sent_id"] == "sent2")
        sent3_result = next(r for r in combined if r["sent_id"] == "sent3")

        assert sent1_result["rrf_score"] > sent2_result["rrf_score"]
        assert sent1_result["rrf_score"] > sent3_result["rrf_score"]

        # Verify RRF calculation
        # sent1: 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.0328
        # sent2: 1/(60+2) = 1/62 ≈ 0.0161
        # sent3: 1/(60+2) = 1/62 ≈ 0.0161
        expected_sent1 = 1.0 / 61 + 1.0 / 61
        expected_sent2 = 1.0 / 62
        expected_sent3 = 1.0 / 62

        assert abs(sent1_result["rrf_score"] - expected_sent1) < 0.001
        assert abs(sent2_result["rrf_score"] - expected_sent2) < 0.001
        assert abs(sent3_result["rrf_score"] - expected_sent3) < 0.001

    def test_rrf_empty_keyword_results(self):
        """Test RRF with only semantic results."""
        from bb_paxdata.application.services.hybrid_search_service import (
            HybridSearchService,
        )

        service = HybridSearchService(
            session_factory=MagicMock(),
            embedding_service=MagicMock(),
            rrf_k=60,
        )

        keyword_results = []
        semantic_results = [
            {
                "sent_id": "sent1",
                "text": "Test",
                "speaker_name": "A",
                "country": "TR",
                "file_id": "f1",
                "dominant_topic": "diplomacy",
                "risk_score": 5,
                "emotion_category": "neutral",
                "keyword_rank": None,
                "semantic_rank": 1,
                "similarity_score": 0.9,
            }
        ]

        combined = service._apply_rrf(keyword_results, semantic_results, k=60)

        assert len(combined) == 1
        assert combined[0]["sent_id"] == "sent1"
        assert combined[0]["rrf_score"] == 1.0 / 61

    def test_rrf_empty_semantic_results(self):
        """Test RRF with only keyword results."""
        from bb_paxdata.application.services.hybrid_search_service import (
            HybridSearchService,
        )

        service = HybridSearchService(
            session_factory=MagicMock(),
            embedding_service=MagicMock(),
            rrf_k=60,
        )

        keyword_results = [
            {
                "sent_id": "sent1",
                "text": "Test",
                "speaker_name": "A",
                "country": "TR",
                "file_id": "f1",
                "dominant_topic": "diplomacy",
                "risk_score": 5,
                "emotion_category": "neutral",
                "keyword_rank": 1,
                "semantic_rank": None,
            }
        ]
        semantic_results = []

        combined = service._apply_rrf(keyword_results, semantic_results, k=60)

        assert len(combined) == 1
        assert combined[0]["sent_id"] == "sent1"
        assert combined[0]["rrf_score"] == 1.0 / 61


class TestSemanticSimilarity:
    """Tests for semantic similarity endpoint."""

    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticSimilarityService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_similarity_endpoint_success(
        self,
        mock_sbert_class,
        mock_similarity_class,
        client: TestClient,
    ):
        """Test successful similarity search."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance

        mock_similarity_instance = MagicMock()
        mock_similarity_class.return_value = mock_similarity_instance

        mock_similarity_instance.find_similar_sentences = AsyncMock(
            return_value=[
                {
                    "sent_id": "sent1",
                    "text": "Similar sentence",
                    "speaker_name": "Speaker A",
                    "country": "Turkey",
                    "file_id": "file1",
                    "dominant_topic": "diplomacy",
                    "risk_score": 5,
                    "emotion_category": "neutral",
                    "similarity_score": 0.85,
                }
            ]
        )

        response = client.post(
            "/api/v1/search/similarity",
            json={
                "sentence_text": "Test sentence about diplomacy",
                "min_similarity": 0.7,
                "limit": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["similarity_score"] == 0.85
        assert data["query"] == "Test sentence about diplomacy"

    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticSimilarityService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_similarity_with_filters(
        self,
        mock_sbert_class,
        mock_similarity_class,
        client: TestClient,
    ):
        """Test similarity search with filters."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance

        mock_similarity_instance = MagicMock()
        mock_similarity_class.return_value = mock_similarity_instance

        mock_similarity_instance.find_similar_sentences = AsyncMock(return_value=[])

        response = client.post(
            "/api/v1/search/similarity",
            json={
                "sentence_text": "test",
                "file_id": "file1",
                "country": "Turkey",
                "speaker_name": "Speaker A",
                "min_similarity": 0.8,
                "limit": 5,
            },
        )

        assert response.status_code == 200

        call_args = mock_similarity_instance.find_similar_sentences.call_args
        assert call_args.kwargs["file_id"] == "file1"
        assert call_args.kwargs["country"] == "Turkey"
        assert call_args.kwargs["speaker_name"] == "Speaker A"
        assert call_args.kwargs["min_similarity"] == 0.8


class TestSemanticClustering:
    """Tests for semantic clustering endpoints."""

    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticClusteringService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticSimilarityService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_clustering_endpoint_success(
        self,
        mock_sbert_class,
        mock_similarity_class,
        mock_clustering_class,
        client: TestClient,
    ):
        """Test successful semantic clustering."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance

        mock_similarity_instance = MagicMock()
        mock_similarity_class.return_value = mock_similarity_instance

        mock_clustering_instance = MagicMock()
        mock_clustering_class.return_value = mock_clustering_instance

        mock_clustering_instance.cluster_sentences = AsyncMock(
            return_value={
                "clusters": [
                    {
                        "cluster_id": 0,
                        "size": 50,
                        "dominant_topic": "diplomacy",
                        "topic_distribution": {"diplomacy": 40, "trade": 10},
                        "speaker_distribution": {"Speaker A": 30, "Speaker B": 20},
                        "avg_risk": 5.2,
                        "sentences": [],
                    }
                ],
                "total_sentences": 100,
                "noise_count": 10,
                "cluster_count": 1,
            }
        )

        response = client.post(
            "/api/v1/search/clusters",
            json={
                "file_id": "file1",
                "country": "Turkey",
                "limit": 500,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cluster_count"] == 1
        assert data["total_sentences"] == 100
        assert data["noise_count"] == 10
        assert len(data["clusters"]) == 1

    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticClusteringService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticSimilarityService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_cluster_summary_endpoint(
        self,
        mock_sbert_class,
        mock_similarity_class,
        mock_clustering_class,
        client: TestClient,
    ):
        """Test cluster summary generation."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance

        mock_similarity_instance = MagicMock()
        mock_similarity_class.return_value = mock_similarity_instance

        mock_clustering_instance = MagicMock()
        mock_clustering_class.return_value = mock_clustering_instance

        mock_clustering_instance.generate_cluster_summary = AsyncMock(
            return_value={
                "cluster_id": 0,
                "size": 50,
                "dominant_topic": "diplomacy",
                "summary": "This cluster discusses diplomatic relations...",
                "speaker_distribution": {"Speaker A": 30, "Speaker B": 20},
                "topic_distribution": {"diplomacy": 40, "trade": 10},
                "avg_risk": 5.2,
                "sample_sentences": ["Sentence 1", "Sentence 2"],
            }
        )

        response = client.get("/api/v1/search/clusters/0/summary?country=Turkey")

        assert response.status_code == 200
        data = response.json()
        assert data["cluster_id"] == 0
        assert data["summary"] == "This cluster discusses diplomatic relations..."
        assert len(data["sample_sentences"]) == 2

    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticClusteringService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticSimilarityService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_cluster_summary_not_found(
        self,
        mock_sbert_class,
        mock_similarity_class,
        mock_clustering_class,
        client: TestClient,
    ):
        """Test cluster summary with non-existent cluster."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance

        mock_similarity_instance = MagicMock()
        mock_similarity_class.return_value = mock_similarity_instance

        mock_clustering_instance = MagicMock()
        mock_clustering_class.return_value = mock_clustering_instance

        mock_clustering_instance.generate_cluster_summary = AsyncMock(
            return_value={"error": "Cluster 999 not found", "cluster_id": 999}
        )

        response = client.get("/api/v1/search/clusters/999/summary")

        assert response.status_code == 404


class TestTopicSummary:
    """Tests for topic-based summary endpoint."""

    @patch("bb_paxdata.interfaces.api.routers.v1.search.SemanticSimilarityService")
    @patch("bb_paxdata.interfaces.api.routers.v1.search.SBERTEmbeddingService")
    def test_topic_summary_success(
        self,
        mock_sbert_class,
        mock_similarity_class,
        client: TestClient,
    ):
        """Test successful topic summary generation."""
        mock_sbert_instance = MagicMock()
        mock_sbert_class.return_value = mock_sbert_instance

        mock_similarity_instance = MagicMock()
        mock_similarity_class.return_value = mock_similarity_instance

        mock_similarity_instance.get_topic_summary = AsyncMock(
            return_value={
                "topic": "diplomacy",
                "total_sentences": 150,
                "speaker_positions": {
                    "Speaker A": [
                        {
                            "sent_id": "sent1",
                            "text": "Test",
                            "sentiment": 0.5,
                            "risk_score": 5,
                        }
                    ]
                },
                "speaker_statistics": {
                    "Speaker A": {
                        "utterance_count": 50,
                        "avg_sentiment": 0.3,
                        "avg_risk": 5.0,
                        "emotion_distribution": {"neutral": 30},
                    }
                },
                "temporal_evolution": [
                    {
                        "start_order": 0,
                        "end_order": 50,
                        "sentence_count": 50,
                        "avg_sentiment": 0.2,
                        "avg_risk": 4.5,
                        "speakers": ["Speaker A"],
                    }
                ],
            }
        )

        response = client.post(
            "/api/v1/search/topics/summary",
            json={
                "topic": "diplomacy",
                "country": "Turkey",
                "file_id": "file1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "diplomacy"
        assert data["total_sentences"] == 150
        assert "speaker_positions" in data
        assert "speaker_statistics" in data
        assert "temporal_evolution" in data
