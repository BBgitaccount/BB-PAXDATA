"""
A/B evaluation harness for RAG retrieval variants.

Tests three retrieval variants:
- Baseline-A: MeilisearchKeywordRetriever (BM25/TF-IDF)
- Baseline-B: PgvectorDenseRetriever (SBERT cosine)
- Treatment: ColBERTDenseRetriever (MaxSim PLAID)

Success criterion: ColBERT Recall@10 ≥ SBERT Recall@10 × 1.20
"""

import pytest
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RAGQueryRequest,
    RetrievedContext,
)


def recall_at_k(result_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Calculate Recall@K metric.

    Args:
        result_ids: List of retrieved document IDs (top-k results)
        relevant_ids: List of ground-truth relevant document IDs
        k: Number of top results to consider

    Returns:
        Recall@K score (0.0 to 1.0)
    """
    relevant_set = set(relevant_ids)
    retrieved_relevant = len([rid for rid in result_ids[:k] if rid in relevant_set])
    return retrieved_relevant / len(relevant_set) if relevant_ids else 0.0


def precision_at_k(result_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Calculate Precision@K metric.

    Args:
        result_ids: List of retrieved document IDs (top-k results)
        relevant_ids: List of ground-truth relevant document IDs
        k: Number of top results to consider

    Returns:
        Precision@K score (0.0 to 1.0)
    """
    relevant_set = set(relevant_ids)
    retrieved_relevant = len([rid for rid in result_ids[:k] if rid in relevant_set])
    return retrieved_relevant / k if k > 0 else 0.0


# 50-query evaluation set — must be constructed from annotated diplomatic corpus
# TODO: Populate with actual queries and relevant IDs from the corpus
EVAL_QUERIES = [
    {
        "query": "pozisyon değişimi Suriye krizi",
        "relevant_ids": ["segment:1042", "segment:2871"],
    },
    # ... 49 more annotated queries to be added
]


@pytest.mark.skip(
    reason="TODO: Populate with actual queries and relevant IDs from the corpus"
)
@pytest.mark.parametrize("variant", ["baseline_bm25", "baseline_sbert", "colbert"])
@pytest.mark.asyncio
async def test_recall_at_10(variant: str, retriever_factory) -> None:
    """
    Test Recall@10 across retrieval variants.

    Success criterion: ColBERT Recall@10 ≥ SBERT Recall@10 × 1.20
    """
    retriever = retriever_factory(variant)
    recalls = []

    for item in EVAL_QUERIES:
        request = RAGQueryRequest(query=item["query"], top_k_dense=10)
        results = await retriever.search(request)
        result_ids = [r.sentence_id for r in results]
        recalls.append(recall_at_k(result_ids, item["relevant_ids"], k=10))

    mean_recall = sum(recalls) / len(recalls) if recalls else 0.0

    # Store baseline SBERT recall for comparison
    if variant == "baseline_sbert":
        pytest.baseline_sbert_recall = mean_recall

    # Check success criterion for ColBERT
    if variant == "colbert":
        baseline_sbert_recall = getattr(pytest, "baseline_sbert_recall", 0.0)
        assert mean_recall >= baseline_sbert_recall * 1.20, (
            f"ColBERT Recall@10 ({mean_recall:.3f}) must be ≥ "
            f"SBERT Recall@10 × 1.20 ({baseline_sbert_recall * 1.20:.3f})"
        )


@pytest.mark.skip(
    reason="TODO: Populate with actual queries and relevant IDs from the corpus"
)
@pytest.mark.parametrize("variant", ["baseline_bm25", "baseline_sbert", "colbert"])
@pytest.mark.asyncio
async def test_precision_at_5(variant: str, retriever_factory) -> None:
    """
    Test Precision@5 across retrieval variants.

    Acceptability threshold: ColBERT P@5 ≥ Baseline-B (SBERT) P@5 × 0.98
    (allow 2% noise margin)
    """
    retriever = retriever_factory(variant)
    precisions = []

    for item in EVAL_QUERIES:
        request = RAGQueryRequest(query=item["query"], top_k_dense=5)
        results = await retriever.search(request)
        result_ids = [r.sentence_id for r in results]
        precisions.append(precision_at_k(result_ids, item["relevant_ids"], k=5))

    mean_precision = sum(precisions) / len(precisions) if precisions else 0.0

    # Store baseline SBERT precision for comparison
    if variant == "baseline_sbert":
        pytest.baseline_sbert_precision = mean_precision

    # Check acceptability threshold for ColBERT
    if variant == "colbert":
        baseline_sbert_precision = getattr(pytest, "baseline_sbert_precision", 0.0)
        assert mean_precision >= baseline_sbert_precision * 0.98, (
            f"ColBERT P@5 ({mean_precision:.3f}) must be ≥ "
            f"SBERT P@5 × 0.98 ({baseline_sbert_precision * 0.98:.3f})"
        )


@pytest.fixture
def retriever_factory():
    """
    Factory fixture for creating retrievers based on variant.

    This fixture should be overridden in conftest.py to provide actual
    retriever instances configured for the test environment.
    """

    def _factory(variant: str):
        # TODO: Implement actual retriever instantiation
        # For now, return a mock retriever
        class MockRetriever:
            async def search(self, request: RAGQueryRequest) -> list[RetrievedContext]:
                return [
                    RetrievedContext(
                        sentence_id=f"segment:{i}",
                        text=f"Mock text {i}",
                        speaker_name="mock",
                        country="mock",
                        panel_id="mock",
                        similarity_score=0.9 - (i * 0.1),
                        retrieval_source=variant,
                    )
                    for i in range(request.top_k_dense)
                ]

        return MockRetriever()

    return _factory
