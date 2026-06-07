# src/bb_paxdata/application/services/model_evaluation_engine.py
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Sequence

import numpy as np
import structlog
from bb_paxdata.application.domain.services.protocols import AIAnalystProtocol
from bb_paxdata.infrastructure.db.model_evaluation import (
    ModelEvaluationMetric,
    ModelEvaluationRun,
)
from bb_paxdata.infrastructure.nlp.sbert_embedding_service import SBERTEmbeddingService
from sqlalchemy import select

logger = structlog.get_logger()


@dataclass(frozen=True)
class TestSample:
    sentence_id: str
    text: str
    gold_summary: str
    gold_sentiment: str
    gold_risk: float
    gold_frame: str
    gold_sbi: float | None = None


class DatasetVersioner:
    @staticmethod
    def compute_hash(samples: Sequence[TestSample]) -> str:
        payload = json.dumps(
            [
                {
                    "id": s.sentence_id,
                    "text": s.text,
                    "gold": s.gold_summary,
                    "sentiment": s.gold_sentiment,
                    "risk": s.gold_risk,
                    "frame": s.gold_frame,
                }
                for s in samples
            ],
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class BootstrapSignificanceTester:
    @staticmethod
    def confidence_interval(
        values: np.ndarray, confidence: float = 0.95, n_bootstrap: int = 10000
    ) -> tuple[float, float]:
        if len(values) < 2:
            return (float(values[0]), float(values[0])) if len(values) else (0.0, 0.0)

        boot_means = []
        rng = np.random.default_rng(42)
        for _ in range(n_bootstrap):
            sample = rng.choice(values, size=len(values), replace=True)
            boot_means.append(np.mean(sample))

        lower = np.percentile(boot_means, ((1 - confidence) / 2) * 100)
        upper = np.percentile(boot_means, (1 - (1 - confidence) / 2) * 100)
        return float(lower), float(upper)


class ModelEvaluationEngine:
    def __init__(
        self,
        ai_client_factory: Callable[[str], AIAnalystProtocol],
        embedding_service: SBERTEmbeddingService,
        session_factory: Callable[[], Any],
        cost_per_1k_input: Decimal = Decimal("0.0015"),
        cost_per_1k_output: Decimal = Decimal("0.0020"),
    ) -> None:
        self._client_factory = ai_client_factory
        self._embed = embedding_service
        self._session_factory = session_factory
        self._cost_in = cost_per_1k_input
        self._cost_out = cost_per_1k_output

    async def evaluate(
        self,
        model_name: str,
        prompt_version_hash: str,
        test_dataset: Sequence[TestSample],
    ) -> ModelEvaluationRun:
        dataset_hash = DatasetVersioner.compute_hash(test_dataset)
        run = ModelEvaluationRun(
            model_name=model_name,
            prompt_version_hash=prompt_version_hash,
            dataset_version_hash=dataset_hash,
            status="running",
        )

        async with self._session_factory() as session:
            session.expire_on_commit = False
            session.add(run)
            await session.commit()
            # Reload to get the run_id
            stmt = (
                select(ModelEvaluationRun)
                .where(
                    ModelEvaluationRun.dataset_version_hash == dataset_hash,
                    ModelEvaluationRun.model_name == model_name,
                )
                .order_by(ModelEvaluationRun.timestamp.desc())
            )
            res = await session.execute(stmt)
            run = res.scalars().first()
            run_id = run.run_id

        client = self._client_factory(model_name)
        latencies: list[float] = []
        similarities: list[float] = []
        input_tokens = 0
        output_tokens = 0

        # Process with bounded concurrency to avoid rate limits
        semaphore = asyncio.Semaphore(5)

        async def _process_one(sample: TestSample) -> ModelEvaluationMetric:
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    response = await client.analyze(sample.text)
                except Exception as e:
                    logger.error(
                        "eval_sentence_failed",
                        sentence_id=sample.sentence_id,
                        error=str(e),
                    )
                    raise
                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000
                latencies.append(latency_ms)

                # Semantic similarity between response and gold summary
                pred_text = response.raw_output or response.summary or ""
                pred_emb = await self._embed.get_embeddings([pred_text])
                gold_emb = await self._embed.get_embeddings([sample.gold_summary])
                pred_vec = pred_emb[0]
                gold_vec = gold_emb[0]

                pred_norm = np.linalg.norm(pred_vec)
                gold_norm = np.linalg.norm(gold_vec)
                if pred_norm > 0 and gold_norm > 0:
                    sim = float(np.dot(pred_vec, gold_vec) / (pred_norm * gold_norm))
                else:
                    sim = 0.0
                similarities.append(sim)

                # Token estimation
                itok = getattr(response, "input_tokens", 0) or 0
                otok = getattr(response, "output_tokens", 0) or 0
                nonlocal input_tokens, output_tokens
                input_tokens += itok
                output_tokens += otok

                # Calculate match & errors
                sentiment_match = False
                if response.sentiment_label and sample.gold_sentiment:
                    sentiment_match = (
                        response.sentiment_label.lower()
                        == sample.gold_sentiment.lower()
                    )

                risk_score_10 = (response.risk_score or 0.0) * 10.0
                risk_match = abs(risk_score_10 - sample.gold_risk) <= 1.0
                risk_mae = abs(risk_score_10 - sample.gold_risk)

                sbi_mae = None
                if sample.gold_sbi is not None:
                    sbi_mae = abs(risk_score_10 - sample.gold_sbi)

                # Frame match
                frame_match = False
                # If frame is present in key claims or summary (simplified check)
                if sample.gold_frame:
                    frame_match = sample.gold_frame.lower() in pred_text.lower()

                return ModelEvaluationMetric(
                    run_id=run_id,
                    sentence_id=sample.sentence_id,
                    cosine_similarity=sim,
                    sentiment_match=sentiment_match,
                    risk_match=risk_match,
                    frame_match=frame_match,
                    risk_mae=risk_mae,
                    sbi_mae=sbi_mae,
                    predicted_summary=pred_text,
                    gold_summary=sample.gold_summary,
                )

        try:
            metrics = await asyncio.gather(*[_process_one(s) for s in test_dataset])

            # Aggregate
            lat_arr = np.array(latencies)
            sim_arr = np.array(similarities)
            ci_lower, ci_upper = BootstrapSignificanceTester.confidence_interval(
                sim_arr
            )

            total_cost = (
                Decimal(input_tokens) / 1000 * self._cost_in
                + Decimal(output_tokens) / 1000 * self._cost_out
            )

            avg_lat = float(np.mean(lat_arr)) if len(lat_arr) > 0 else 0.0
            p95_lat = float(np.percentile(lat_arr, 95)) if len(lat_arr) > 0 else 0.0
            p99_lat = float(np.percentile(lat_arr, 99)) if len(lat_arr) > 0 else 0.0

            async with self._session_factory() as session:
                session.expire_on_commit = False
                # Reload run inside session
                db_run = await session.get(ModelEvaluationRun, run_id)
                if db_run:
                    db_run.status = "completed"
                    db_run.avg_latency_ms = avg_lat
                    db_run.p95_latency_ms = p95_lat
                    db_run.p99_latency_ms = p99_lat
                    db_run.total_cost_usd = total_cost
                    for metric in metrics:
                        session.add(metric)
                    await session.commit()
                    # Create transient copy to avoid DetachedInstanceError and MissingGreenlet
                    run = ModelEvaluationRun(
                        run_id=run_id,
                        model_name=model_name,
                        prompt_version_hash=prompt_version_hash,
                        dataset_version_hash=dataset_hash,
                        avg_latency_ms=avg_lat,
                        p95_latency_ms=p95_lat,
                        p99_latency_ms=p99_lat,
                        total_cost_usd=total_cost,
                        status="completed",
                    )

            logger.info(
                "evaluation_complete",
                run_id=run_id,
                model=model_name,
                avg_similarity=float(np.mean(sim_arr)) if len(sim_arr) > 0 else 0.0,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                avg_latency_ms=avg_lat,
                total_cost_usd=str(total_cost),
            )

        except Exception as exc:
            logger.error("evaluation_failed", model=model_name, error=str(exc))
            async with self._session_factory() as session:
                session.expire_on_commit = False
                db_run = await session.get(ModelEvaluationRun, run_id)
                if db_run:
                    db_run.status = "failed"
                    await session.commit()
            raise

        return run
