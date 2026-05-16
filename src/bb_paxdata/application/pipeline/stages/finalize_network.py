# src/bb_paxdata/application/pipeline/stages/finalize_network.py
from __future__ import annotations

from bb_paxdata.application.pipeline.stages.base import FinalizeStage
from bb_paxdata.domain.models.analysis import Analysis
from bb_paxdata.infrastructure.repositories.country_repository import (
    BilateralSentimentRepository,
)
from bb_paxdata.infrastructure.repositories.discourse_network_repository import (
    DiscourseNetworkRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession


class NetworkFinalizeStage(FinalizeStage):
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
        for sentiment in analysis.bilateral_metrics or []:
            if sentiment.dyadic_metrics:
                await self.bilateral_repo.save_dyadic(session, sentiment.dyadic_metrics)

        return analysis
