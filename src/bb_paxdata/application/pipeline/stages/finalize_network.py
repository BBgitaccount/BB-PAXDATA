# src/bb_paxdata/application/pipeline/stages/finalize_network.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bb_paxdata.application.domain.models.analysis import Analysis
from bb_paxdata.application.pipeline.stages.base import BaseFinalizeStage
from bb_paxdata.infrastructure.db.repositories.country_repository import (
    BilateralSentimentRepository,
)
from bb_paxdata.infrastructure.db.repositories.discourse_network_repository import (
    DiscourseNetworkRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from bb_paxdata.application.pipeline.models.collect_result import CollectResult
    from bb_paxdata.application.pipeline.models.pipeline_result import PipelineResult


class NetworkFinalizeStage(BaseFinalizeStage):
    """
    Faz 4 FINALIZE step:
    Persist DiscourseFlow edges and BilateralSentiment dyadic metrics.
    """

    def __init__(
        self,
        network_repo: DiscourseNetworkRepository,
        bilateral_repo: BilateralSentimentRepository,
    ) -> None:
        self.network_repo = network_repo
        self.bilateral_repo = bilateral_repo

    async def process(self, session: AsyncSession, analysis: Analysis) -> Analysis:
        """Persist network and bilateral data."""
        if analysis.discourse_flow:
            await self.network_repo.save_flow(session, analysis.discourse_flow)

        # Persist dyadic metrics into bilateral_sentiments table
        import json
        from datetime import datetime, timezone

        from bb_paxdata.infrastructure.db.models import DiscourseNetworkEdge

        for sentiment in analysis.bilateral_metrics or []:
            if sentiment.dyadic_metrics:
                await self.bilateral_repo.save_dyadic(session, sentiment.dyadic_metrics)

            srl_frame_dict = None
            if sentiment.srl_predicate:
                srl_frame_dict = {
                    "predicate": sentiment.srl_predicate,
                    "arg0": sentiment.srl_arg0_entity,
                    "arg1": sentiment.srl_arg1_entity,
                    "is_negated": sentiment.srl_is_negated,
                    "confidence": sentiment.srl_confidence,
                    "modal": sentiment.srl_modal,
                }

            db_edge = DiscourseNetworkEdge(
                file_id=sentiment.panel_id,
                from_country=sentiment.from_country,
                to_country=sentiment.to_country,
                weight=float(sentiment.total_mentions),
                avg_sentiment=sentiment.avg_sentiment,
                edge_type=(
                    sentiment.relationship_type.value
                    if sentiment.relationship_type
                    else None
                ),
                power_source=0,
                # SRL Enrichments
                predicate=sentiment.srl_predicate,
                arg0_entity=sentiment.srl_arg0_entity,
                arg1_entity=sentiment.srl_arg1_entity,
                is_negated=sentiment.srl_is_negated,
                srl_confidence=sentiment.srl_confidence,
                srl_frame_json=(
                    json.dumps(srl_frame_dict, ensure_ascii=False)
                    if srl_frame_dict
                    else None
                ),
                srl_extracted_at=datetime.now(timezone.utc),
            )
            session.add(db_edge)

        return analysis

    async def run(
        self,
        analysis: Analysis,
        collect_result: CollectResult,
        success: bool,
        errors: list[str],
        session: Any = None,
    ) -> PipelineResult:
        """
        BaseFinalizeStage abstract method implementation.
        Not used by this concrete network finalize stage.
        """
        raise NotImplementedError("This stage uses process() instead of run()")
