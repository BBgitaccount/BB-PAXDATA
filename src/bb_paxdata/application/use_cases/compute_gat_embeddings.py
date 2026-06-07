"""Use Case: Fischer DNA DiscourseFlow'dan GAT embeddings üretir.

(GAP-04) Full GAT pipeline integration:
- Fischer DNA DiscourseFlow (actor_ids, concept_ids, edges) kullanır
- GATFeatureExtractionService ile actor/concept features çıkarır
- GATEmbeddingService ile embeddings hesaplar
- IGATEmbeddingRepository ile DB'ye kaydeder
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from bb_paxdata.application.domain.models.discourse_network import DiscourseFlow
from bb_paxdata.application.domain.ports.i_gat_embedding_repository import (
    IGATEmbeddingRepository,
)

if TYPE_CHECKING:
    from bb_paxdata.application.domain.services.gat_embedding_service import (
        GATEmbeddingService,
    )
    from bb_paxdata.application.domain.services.gat_feature_extraction import (
        GATFeatureExtractionService,
    )

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ComputeGATEmbeddingsInput:
    """GAT embedding computation için input."""

    flow: DiscourseFlow
    actor_sentences: dict[str, list[str]]  # {actor_id: [sentence1, sentence2, ...]}
    concept_descriptions: dict[str, str]  # {concept_id: "topic description"}


@dataclass(frozen=True)
class ComputeGATEmbeddingsOutput:
    """GAT embedding computation sonucu."""

    session_id: str
    embeddings_count: int
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return len(self.errors) == 0


class ComputeGATEmbeddingsUseCase:
    """Fischer DNA DiscourseFlow'dan GAT embeddings üretir."""

    def __init__(
        self,
        gat_service: GATEmbeddingService,
        feature_service: GATFeatureExtractionService,
        gat_repo: IGATEmbeddingRepository,
    ) -> None:
        self._gat_service = gat_service
        self._feature_service = feature_service
        self._gat_repo = gat_repo

    async def execute(
        self, input_data: ComputeGATEmbeddingsInput
    ) -> ComputeGATEmbeddingsOutput:
        """GAT embedding computation pipeline'ı çalıştırır."""
        flow = input_data.flow
        errors: list[str] = []

        try:
            # 1. Extract actor and concept features
            actor_features, concept_features = (
                await self._feature_service.extract_all_features(
                    actor_sentences=input_data.actor_sentences,
                    concept_descriptions=input_data.concept_descriptions,
                )
            )

            # 2. Compute GAT embeddings
            embeddings = await self._gat_service.compute_embeddings(
                flow=flow,
                actor_features=actor_features,
                concept_features=concept_features,
            )

            # 3. Save embeddings to DB
            if embeddings:
                await self._gat_repo.save_batch(embeddings)
            else:
                logger.warning(
                    "compute_gat_embeddings.no_embeddings_produced",
                    session_id=flow.session_id,
                )

            logger.info(
                "compute_gat_embeddings.completed",
                session_id=flow.session_id,
                embeddings_count=len(embeddings),
            )

            return ComputeGATEmbeddingsOutput(
                session_id=flow.session_id,
                embeddings_count=len(embeddings),
                errors=tuple(errors),
            )

        except Exception as exc:
            logger.error(
                "compute_gat_embeddings.failed",
                session_id=flow.session_id,
                error=str(exc),
            )
            return ComputeGATEmbeddingsOutput(
                session_id=flow.session_id,
                embeddings_count=0,
                errors=(str(exc),),
            )
