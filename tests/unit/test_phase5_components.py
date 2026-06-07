# tests/unit/test_phase5_components.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from bb_paxdata.application.domain.models.forecast import TimeSlice
from bb_paxdata.application.domain.services.forecasting import RiskForecaster
from bb_paxdata.application.domain.services.prompt_registry import (
    build_default_registry,
)
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RAGQueryRequest,
    RetrievedContext,
)
from bb_paxdata.application.services.baseline_fetcher import (
    RollingWindowBaselineFetcher,
)
from bb_paxdata.application.services.dki_evaluator import DKIEvaluator
from bb_paxdata.application.services.dynamic_few_shot_optimizer import (
    DbExampleStore,
    RedisEmbeddingCache,
    VectorSimilaritySelector,
)
from bb_paxdata.application.services.model_evaluation_engine import (
    ModelEvaluationEngine,
)
from bb_paxdata.application.services.rag_service import RAGService
from bb_paxdata.infrastructure.db import models as m
from bb_paxdata.infrastructure.db.base import Base
from bb_paxdata.infrastructure.db.model_evaluation import (
    AuditEntry,
    ModelEvaluationMetric,
)
from bb_paxdata.infrastructure.retrieval.local_reranker import LocalCrossEncoderReranker
from bb_paxdata.infrastructure.retrieval.meilisearch_keyword_retriever import (
    MeilisearchKeywordRetriever,
)
from bb_paxdata.infrastructure.retrieval.pgvector_dense_retriever import (
    PgvectorDenseRetriever,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def test_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine, autocommit=False, autoflush=False, class_=AsyncSession
    )
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    service = MagicMock()

    # Mock return value for SBERT get_embeddings
    async def get_embeddings(texts):
        return [np.random.rand(384) for _ in texts]

    service.get_embeddings = get_embeddings
    return service


@pytest.mark.asyncio
async def test_risk_forecaster_logic():
    from datetime import datetime, timezone

    forecaster = RiskForecaster(monte_carlo_sims=100)
    historical = [
        TimeSlice(
            panel_id=f"p{i}",
            timestamp=datetime.now(timezone.utc),
            computed_risk=float(i) * 0.5,
            sentiment_delta=0.1,
            sentiment_volatility=0.2,
            keyness_index_deviation=0.05,
            escalation_multiplier=1.2,
        )
        for i in range(10)
    ]
    res = forecaster.forecast_next_panel_risk(historical, min_history=5)
    assert res.predicted_risk >= 0.0
    assert res.predicted_risk <= 10.0
    assert res.confidence_lower <= res.predicted_risk
    assert res.confidence_upper >= res.predicted_risk


@pytest.mark.asyncio
async def test_dense_retriever_sqlite_fallback(
    test_session_factory, mock_embedding_service
):
    # Seed database
    async with test_session_factory() as session:
        session.add(
            m.Sentence(
                sent_id="s1",
                seg_id="seg1",
                file_id="p1",
                speaker_name="Speaker A",
                country="USA",
                text="Peace talks stalled.",
            )
        )
        session.add(
            m.Sentence(
                sent_id="s2",
                seg_id="seg1",
                file_id="p1",
                speaker_name="Speaker B",
                country="Turkey",
                text="Tension escalates.",
            )
        )
        await session.commit()

    retriever = PgvectorDenseRetriever(
        session_factory=test_session_factory,
        embedding_service=mock_embedding_service,
    )
    req = RAGQueryRequest(query="Peace talks", top_k_dense=2)
    results = await retriever.search(req)
    assert len(results) == 2
    assert results[0].retrieval_source == "pgvector_fallback"


@pytest.mark.asyncio
async def test_keyword_retriever_fallback(test_session_factory):
    async with test_session_factory() as session:
        session.add(
            m.Sentence(
                sent_id="s1",
                seg_id="seg1",
                file_id="p1",
                speaker_name="Speaker A",
                country="USA",
                text="Diplomatic efforts continue.",
            )
        )
        await session.commit()

    retriever = MeilisearchKeywordRetriever(session_factory=test_session_factory)
    req = RAGQueryRequest(query="Diplomatic", top_k_keyword=1)
    results = await retriever.search(req)
    assert len(results) == 1
    assert results[0].text == "Diplomatic efforts continue."


@pytest.mark.asyncio
async def test_local_reranker_fallback():
    mock_encoder = MagicMock()
    mock_encoder.predict.return_value = np.array([0.1, 0.9])

    reranker = LocalCrossEncoderReranker()
    reranker._model = mock_encoder
    reranker._model_loaded = True

    candidates = [
        RetrievedContext(
            sentence_id="s1",
            text="A",
            speaker_name="S",
            country="C",
            panel_id="P",
            similarity_score=0.2,
            retrieval_source="kw",
        ),
        RetrievedContext(
            sentence_id="s2",
            text="B",
            speaker_name="S",
            country="C",
            panel_id="P",
            similarity_score=0.8,
            retrieval_source="kw",
        ),
    ]
    res = await reranker.rerank("query", candidates, top_n=1)
    assert len(res) == 1
    assert res[0].sentence_id == "s2"


@pytest.mark.asyncio
async def test_rag_service_orchestration(mock_embedding_service):
    kw_retriever = AsyncMock()
    dense_retriever = AsyncMock()
    reranker = AsyncMock()
    synthesis = AsyncMock()

    kw_retriever.search.return_return = []
    dense_retriever.search.return_value = []

    # Return mock results for fusion
    async def kw_search(*args):
        return [
            RetrievedContext(
                sentence_id="s1",
                text="KW hit",
                speaker_name="S",
                country="C",
                panel_id="P",
                similarity_score=1.0,
                retrieval_source="kw",
            )
        ]

    async def dense_search(*args):
        return [
            RetrievedContext(
                sentence_id="s1",
                text="KW hit",
                speaker_name="S",
                country="C",
                panel_id="P",
                similarity_score=0.9,
                retrieval_source="dense",
            )
        ]

    kw_retriever.search = kw_search
    dense_retriever.search = dense_search

    async def rerank_mock(q, cand, n):
        return cand

    reranker.rerank = rerank_mock

    async def synthesize_mock(q, ctx, stream):
        return "Synthesized result"

    synthesis.synthesize = synthesize_mock

    registry = build_default_registry()
    service = RAGService(
        keyword_retriever=kw_retriever,
        dense_retriever=dense_retriever,
        reranker=reranker,
        synthesis_client=synthesis,
        prompt_registry=registry,
    )

    req = RAGQueryRequest(query="test query")
    res = await service.query(req)
    assert res.answer == "Synthesized result"
    assert len(res.sources) == 1


@pytest.mark.asyncio
async def test_dynamic_few_shot_optimizer(test_session_factory, mock_embedding_service):
    # Seed DB with human review
    async with test_session_factory() as session:
        session.add(
            m.Sentence(
                sent_id="sent1",
                seg_id="seg1",
                file_id="p1",
                speaker_name="Spk",
                country="C",
                text="Target sentence text.",
            )
        )
        session.add(
            m.AISentenceAnalysis(
                sent_id="sent1",
                prompt_version="v1",
                framing="SECURITY",
                risk_level=m.RiskLevel.HIGH,
            )
        )
        # Add HumanReviewORM using text directly
        from sqlalchemy import text as sql_text

        await session.execute(
            sql_text(
                "INSERT INTO human_reviews (id, analysis_id, reviewer_id, human_dominant_frame, human_sentiment_score, human_sbi_score, agreement_status, created_at) "
                "VALUES ('r1', 'sent1', 'rev1', 'SECURITY', 0.5, 8.0, 'AGREED', CURRENT_TIMESTAMP)"
            )
        )
        await session.commit()

    cache = RedisEmbeddingCache(redis=None)
    store = DbExampleStore(session_factory=test_session_factory)
    selector = VectorSimilaritySelector(
        embedding_service=mock_embedding_service,
        example_store=store,
        cache=cache,
        default_min_similarity=0.1,  # low threshold for tests
    )

    examples = await selector.select(target_text="Target sentence", n_examples=2)
    assert len(examples) == 1
    assert examples[0].sentence_text == "Target sentence text."


@pytest.mark.asyncio
async def test_dki_evaluator(test_session_factory):
    ai_client = AsyncMock()
    mock_res = MagicMock()
    mock_res.raw_output = '{"semantic_shift_score": 0.35, "is_consistent": true, "calibration_drift": 0.05, "reasoning": "Consistent statement"}'
    mock_res.model_name = "gpt-4o"
    ai_client.analyze.return_value = mock_res

    registry = build_default_registry()
    evaluator = DKIEvaluator(
        ai_client=ai_client,
        prompt_registry=registry,
        audit_session_factory=test_session_factory,
    )

    from bb_paxdata.application.domain.services.protocols.judge_protocols import (
        BaselineMetrics,
    )

    baseline = BaselineMetrics(
        historical_sentiment_avg=0.1,
        historical_risk_avg=2.0,
        historical_frame_mode="SECURITY",
        window_size=5,
        panel_ids_in_window=["p1"],
    )

    verdict = await evaluator.evaluate(
        speaker_name="Speaker A",
        country="Turkey",
        sentence_text="Some text",
        pipeline_sentiment="neutral",
        pipeline_risk_score=2.0,
        pipeline_frame="SECURITY",
        baseline=baseline,
    )

    assert verdict.is_consistent is True
    assert verdict.semantic_shift_score == 0.35

    # Check audit entry exists in DB
    async with test_session_factory() as session:
        from sqlalchemy import select

        res = await session.execute(select(AuditEntry))
        rows = res.scalars().all()
        assert len(rows) == 1
        assert rows[0].action_type == "LLM_JUDGE"


@pytest.mark.asyncio
async def test_rolling_window_baseline_fetcher(test_session_factory):
    async with test_session_factory() as session:
        session.add(
            m.Sentence(
                sent_id="s1",
                seg_id="seg1",
                file_id="p1",
                speaker_name="Speaker A",
                country="Turkey",
                text="Text 1",
                dominant_frame="SECURITY",
            )
        )
        session.add(
            m.Sentence(
                sent_id="s2",
                seg_id="seg1",
                file_id="p2",
                speaker_name="Speaker A",
                country="Turkey",
                text="Text 2",
                dominant_frame="COOPERATION",
            )
        )
        session.add(
            m.AISentenceAnalysis(
                sent_id="s1",
                prompt_version="v1",
                risk_score=0.4,
                sentiment_score=0.2,
                framing="SECURITY",
            )
        )
        session.add(
            m.AISentenceAnalysis(
                sent_id="s2",
                prompt_version="v1",
                risk_score=0.6,
                sentiment_score=-0.2,
                framing="COOPERATION",
            )
        )
        await session.commit()

    fetcher = RollingWindowBaselineFetcher(
        session_factory=test_session_factory, window_size=5
    )
    baseline = await fetcher.fetch(speaker_name="Speaker A", country="Turkey")
    assert baseline.window_size == 2
    assert baseline.historical_sentiment_avg == pytest.approx(0.0)
    assert baseline.historical_risk_avg == pytest.approx(5.0)  # (0.4+0.6)/2 * 10
    assert baseline.historical_frame_mode in ["SECURITY", "COOPERATION"]


@pytest.mark.asyncio
async def test_model_evaluation_engine(test_session_factory, mock_embedding_service):
    from decimal import Decimal

    from bb_paxdata.application.services.model_evaluation_engine import TestSample

    ai_client = AsyncMock()
    mock_res = MagicMock()
    mock_res.raw_output = "Model output summary content"
    mock_res.sentiment_label = "positive"
    mock_res.risk_score = 0.3
    mock_res.input_tokens = 100
    mock_res.output_tokens = 50
    ai_client.analyze.return_value = mock_res

    def client_factory(model_name: str):
        return ai_client

    engine = ModelEvaluationEngine(
        ai_client_factory=client_factory,
        embedding_service=mock_embedding_service,
        session_factory=test_session_factory,
    )

    samples = [
        TestSample(
            sentence_id="sent1",
            text="Input sentence text",
            gold_summary="Gold summary content",
            gold_sentiment="positive",
            gold_risk=3.0,
            gold_frame="SECURITY",
        )
    ]

    run = await engine.evaluate(
        model_name="test-llm",
        prompt_version_hash="prompt_hash_val",
        test_dataset=samples,
    )

    assert run.status == "completed"
    assert run.model_name == "test-llm"
    assert run.total_cost_usd > Decimal("0")

    # Check metrics in DB
    async with test_session_factory() as session:
        from sqlalchemy import select

        res = await session.execute(select(ModelEvaluationMetric))
        metrics = res.scalars().all()
        assert len(metrics) == 1
        assert metrics[0].sentence_id == "sent1"
        assert metrics[0].sentiment_match is True
