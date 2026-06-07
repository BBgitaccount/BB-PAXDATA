# src/bb_paxdata/application/services/phase5_event_publisher.py
from __future__ import annotations

from bb_paxdata.application.domain.ports.event_bus import EventBusPort
from bb_paxdata.application.domain.services.protocols.judge_protocols import (
    JudgeVerdict,
)
from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RAGQueryResponse,
)


class Phase5EventPublisher:
    """Publishes specialized events for RAG queries and Judge evaluations."""

    def __init__(self, event_bus: EventBusPort) -> None:
        self._event_bus = event_bus

    async def publish_rag_query_completed(
        self, query_id: str, response: RAGQueryResponse
    ) -> None:
        payload = {
            "query_id": query_id,
            "query": response.query,
            "answer": response.answer,
            "sources": [
                {
                    "sentence_id": src.sentence_id,
                    "text": src.text,
                    "speaker_name": src.speaker_name,
                    "country": src.country,
                    "panel_id": src.panel_id,
                    "similarity_score": src.similarity_score,
                    "retrieval_source": src.retrieval_source,
                }
                for src in response.sources
            ],
            "latency_ms": response.latency_ms,
            "total_tokens": response.total_tokens,
        }
        await self._event_bus.publish(
            channel="rag_events",
            event_type="RAGQueryCompleted",
            payload=payload,
        )

    async def publish_judge_verdict_rendered(
        self, sentence_id: str, verdict: JudgeVerdict
    ) -> None:
        payload = {
            "sentence_id": sentence_id,
            "semantic_shift_score": verdict.semantic_shift_score,
            "is_consistent": verdict.is_consistent,
            "calibration_drift": verdict.calibration_drift,
            "reasoning": verdict.reasoning,
            "prompt_hash": verdict.prompt_hash,
            "response_hash": verdict.response_hash,
            "model_used": verdict.model_used,
            "inference_time_ms": verdict.inference_time_ms,
        }
        await self._event_bus.publish(
            channel="judge_events",
            event_type="JudgeVerdictRendered",
            payload=payload,
        )
