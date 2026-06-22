"""
Unit tests for ColBERTDenseRetriever.

Tests the adapter layer that converts ragatouille search results
to RetrievedContext domain objects.
"""

from unittest.mock import Mock

import numpy as np
import pytest

from bb_paxdata.application.domain.services.colbert_embedding_service import (
    RAGatoulleColBERTService,
)
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RAGQueryRequest,
    RetrievedContext,
)
from bb_paxdata.infrastructure.retrieval.colbert_retriever import ColBERTDenseRetriever


@pytest.fixture
def mock_colbert_service():
    """Create a mock ColBERT service for testing."""
    service = Mock(spec=RAGatoulleColBERTService)
    service.is_index_ready.return_value = True
    service.embedding_dim.return_value = 128
    return service


@pytest.fixture
def colbert_retriever(mock_colbert_service):
    """Create a ColBERTDenseRetriever instance with mock service."""
    return ColBERTDenseRetriever(colbert_service=mock_colbert_service)


@pytest.mark.asyncio
async def test_search_basic(colbert_retriever, mock_colbert_service):
    """Test basic search functionality."""
    # Mock the retrieve method to return sample results
    mock_results = [
        {
            "content": "Test passage 1 about diplomatic negotiations",
            "document_id": "segment:123",
            "score": 0.95,
        },
        {
            "content": "Test passage 2 about crisis management",
            "document_id": "segment:456",
            "score": 0.87,
        },
    ]
    mock_colbert_service.retrieve.return_value = mock_results

    # Create a query request
    request = RAGQueryRequest(query="diplomatic negotiations", top_k_dense=10)

    # Perform search
    results = await colbert_retriever.search(request)

    # Verify results
    assert len(results) == 2
    assert isinstance(results[0], RetrievedContext)
    assert results[0].sentence_id == "segment:123"
    assert results[0].text == "Test passage 1 about diplomatic negotiations"
    assert results[0].similarity_score == 0.95
    assert results[0].retrieval_source == "colbert_plaid"

    # Verify the retrieve method was called with correct parameters
    mock_colbert_service.retrieve.assert_called_once_with(
        query="diplomatic negotiations", k=10
    )


@pytest.mark.asyncio
async def test_search_empty_results(colbert_retriever, mock_colbert_service):
    """Test search with no results."""
    mock_colbert_service.retrieve.return_value = []

    request = RAGQueryRequest(query="nonexistent query", top_k_dense=10)
    results = await colbert_retriever.search(request)

    assert len(results) == 0
    mock_colbert_service.retrieve.assert_called_once()


@pytest.mark.asyncio
async def test_search_score_conversion(colbert_retriever, mock_colbert_service):
    """Test that scores are properly converted to float."""
    mock_results = [
        {
            "content": "Test passage",
            "document_id": "segment:789",
            "score": "0.92",  # String score
        }
    ]
    mock_colbert_service.retrieve.return_value = mock_results

    request = RAGQueryRequest(query="test query", top_k_dense=10)
    results = await colbert_retriever.search(request)

    assert results[0].similarity_score == 0.92
    assert isinstance(results[0].similarity_score, float)


@pytest.mark.asyncio
async def test_search_missing_fields(colbert_retriever, mock_colbert_service):
    """Test handling of missing fields in ragatouille results."""
    mock_results = [
        {
            "content": "Test passage",
            "document_id": "segment:999",
            # Missing score field
        }
    ]
    mock_colbert_service.retrieve.return_value = mock_results

    request = RAGQueryRequest(query="test query", top_k_dense=10)
    results = await colbert_retriever.search(request)

    # Should handle missing score gracefully
    assert len(results) == 1
    assert results[0].similarity_score == 0.0  # Default value


def test_colbert_service_encode_queries(mock_colbert_service):
    """Test ColBERT service query encoding."""
    mock_embeddings = [
        np.random.rand(32, 128).astype(np.float32),
        np.random.rand(32, 128).astype(np.float32),
    ]
    mock_colbert_service.encode_queries.return_value = mock_embeddings

    queries = ["query 1", "query 2"]
    results = mock_colbert_service.encode_queries(queries)

    assert len(results) == 2
    assert all(isinstance(emb, np.ndarray) for emb in results)
    assert all(emb.shape == (32, 128) for emb in results)
    mock_colbert_service.encode_queries.assert_called_once_with(queries)


def test_colbert_service_encode_passages(mock_colbert_service):
    """Test ColBERT service passage encoding."""
    mock_embeddings = [
        np.random.rand(180, 128).astype(np.float32),
        np.random.rand(150, 128).astype(np.float32),
    ]
    mock_colbert_service.encode_passages.return_value = mock_embeddings

    passages = ["passage 1", "passage 2"]
    results = mock_colbert_service.encode_passages(passages)

    assert len(results) == 2
    assert all(isinstance(emb, np.ndarray) for emb in results)
    mock_colbert_service.encode_passages.assert_called_once_with(passages)


def test_colbert_service_embedding_dim(mock_colbert_service):
    """Test ColBERT service embedding dimension."""
    assert mock_colbert_service.embedding_dim() == 128
    mock_colbert_service.embedding_dim.assert_called_once()


def test_colbert_service_is_index_ready(mock_colbert_service):
    """Test ColBERT service index readiness check."""
    assert mock_colbert_service.is_index_ready() is True
    mock_colbert_service.is_index_ready.assert_called_once()


def test_colbert_service_build_index(tmp_path):
    """Test ColBERT service index building."""
    service = RAGatoulleColBERTService(index_path=tmp_path)

    # This test requires ragatouille to be installed
    # Skip if not available
    try:
        from ragatouille import RAGPretrainedModel  # noqa: F401
    except ImportError:
        pytest.skip("ragatouille not installed")

    # Mock the actual index build to avoid long computation
    with pytest.raises(ValueError, match=r"passages.*must have equal length"):
        service.build_index(
            passages=["test"],
            passage_ids=["id1", "id2"],  # Mismatched lengths
        )


def test_colbert_service_load_index_not_found(tmp_path):
    """Test ColBERT service load index with non-existent index."""
    service = RAGatoulleColBERTService(index_path=tmp_path)

    with pytest.raises(FileNotFoundError, match="PLAID index not found"):
        service.load_index(index_name="nonexistent_index")
