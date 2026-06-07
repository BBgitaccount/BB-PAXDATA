# src/bb_paxdata/infrastructure/retrieval/local_reranker.py
from __future__ import annotations

import logging
from typing import Any, Sequence

from bb_paxdata.application.domain.services.protocols.rag_protocols import (
    RerankerProtocol,
    RetrievedContext,
)

logger = logging.getLogger(__name__)


class LocalCrossEncoderReranker(RerankerProtocol):
    def __init__(
        self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ) -> None:
        self.model_name = model_name
        self._model: Any = None
        self._model_loaded = False

    def _load_model(self) -> None:
        if not self._model_loaded:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name, max_length=512)
            except Exception as e:
                logger.warning(
                    f"Could not load CrossEncoder model {self.model_name}: {e}. "
                    "Reranker will use pass-through fallback."
                )
            self._model_loaded = True

    async def rerank(
        self, query: str, candidates: Sequence[RetrievedContext], top_n: int
    ) -> Sequence[RetrievedContext]:
        if not candidates:
            return []

        self._load_model()

        if self._model is not None:
            pairs = [(query, c.text) for c in candidates]
            import asyncio

            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None, lambda: self._model.predict(pairs, show_progress_bar=False)
            )

            scored = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)[
                :top_n
            ]

            results: list[RetrievedContext] = []
            for ctx, score in scored:
                results.append(
                    ctx.model_copy(
                        update={
                            "similarity_score": float(score),
                            "retrieval_source": f"{ctx.retrieval_source}+reranker",
                        }
                    )
                )
            return results
        else:
            sorted_candidates = sorted(
                candidates, key=lambda x: x.similarity_score, reverse=True
            )[:top_n]
            return [
                c.model_copy(
                    update={
                        "retrieval_source": f"{c.retrieval_source}+reranker_fallback"
                    }
                )
                for c in sorted_candidates
            ]
