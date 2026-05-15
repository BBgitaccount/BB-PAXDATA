# src/bb_paxdata/application/use_cases/build_panel_network.py
"""
Use Case: BilateralSentiment kayıtlarından DiscourseFlow (ağ kenarı) üretir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog
from bb_paxdata.domain.enums.country_enums import EdgeType, RelationshipType
from bb_paxdata.domain.models.discourse_flow import DiscourseFlow
from bb_paxdata.domain.services.country_repositories import (
    IBilateralSentimentRepository,
    IDiscourseFlowRepository,
)

if TYPE_CHECKING:
    import networkx as nx
    from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class BuildPanelNetworkInput:
    panel_id: str
    weight_threshold: float = 0.0  # Bu eşiğin altındaki edge'ler ağa dahil edilmez


@dataclass(frozen=True)
class BuildPanelNetworkOutput:
    panel_id: str
    edges_created: int
    node_count: int
    centrality: dict[str, float] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return len(self.errors) == 0


class BuildPanelNetworkUseCase:
    """
    BilateralSentiment kayıtlarından DiscourseFlow edge'leri üretir.
    networkx SADECE bellek içi analiz için kullanılır.
    """

    def __init__(
        self,
        sentiment_repo: IBilateralSentimentRepository,
        flow_repo: IDiscourseFlowRepository,
    ) -> None:
        self._sentiment_repo = sentiment_repo
        self._flow_repo = flow_repo

    async def execute(
        self, input_data: BuildPanelNetworkInput
    ) -> BuildPanelNetworkOutput:
        panel_id = input_data.panel_id
        errors: list[str] = []

        try:
            sentiments = await self._sentiment_repo.get_all_for_panel(panel_id)
        except Exception as exc:
            return BuildPanelNetworkOutput(
                panel_id=panel_id,
                edges_created=0,
                node_count=0,
                errors=(str(exc),),
            )

        flows: list[DiscourseFlow] = []
        for s in sentiments:
            if abs(s.affinity_score) <= input_data.weight_threshold:
                continue

            edge_type = self._classify_edge_type(s.effective_relationship)
            weight = self._calculate_weight(s)

            flows.append(
                DiscourseFlow(
                    from_country=s.from_country,
                    to_country=s.to_country,
                    panel_id=panel_id,
                    edge_type=edge_type,
                    weight=weight,
                    sentiment_toward=s.avg_sentiment,
                    confrontational_count=self._count_confrontational(s),
                    cooperative_count=self._count_cooperative(s),
                )
            )

        try:
            await self._flow_repo.save_batch(flows)
        except Exception as exc:
            errors.append(f"persistence_failed: {exc}")

        centrality = self._compute_centrality(flows)
        nodes = {f.from_country for f in flows} | {f.to_country for f in flows}

        logger.info(
            "build_panel_network.completed",
            panel_id=panel_id,
            edges=len(flows),
            nodes=len(nodes),
        )
        return BuildPanelNetworkOutput(
            panel_id=panel_id,
            edges_created=len(flows),
            node_count=len(nodes),
            centrality=centrality,
            errors=tuple(errors),
        )

    def _classify_edge_type(self, relationship: RelationshipType) -> EdgeType:
        if relationship in {RelationshipType.ADVERSARY, RelationshipType.CAUTIOUS}:
            return EdgeType.CONFRONTATIONAL
        if relationship in {RelationshipType.ALLY, RelationshipType.PARTNER}:
            return EdgeType.COOPERATIVE
        return EdgeType.DIPLOMATIC_REFERENCE

    def _calculate_weight(self, sentiment: BilateralSentiment) -> float:
        """
        Kenar ağırlığı = toplam atıf × |affinity_score|
        """
        val = float(sentiment.total_mentions * abs(sentiment.affinity_score) + 1e-6)
        return round(val, 6)

    def _count_confrontational(self, sentiment: BilateralSentiment) -> int:
        """avg_sentiment < -0.2 olan atıfların tahmini sayısı."""
        if sentiment.avg_sentiment < -0.2:
            return int(sentiment.total_mentions * 0.7)
        return int(sentiment.total_mentions * 0.1)

    def _count_cooperative(self, sentiment: BilateralSentiment) -> int:
        if sentiment.avg_sentiment > 0.2:
            return int(sentiment.total_mentions * 0.7)
        return int(sentiment.total_mentions * 0.1)

    def _compute_centrality(self, flows: list[DiscourseFlow]) -> dict[str, float]:
        """
        networkx ile betweenness centrality hesabı.
        """
        try:
            import networkx as nx

            G: nx.DiGraph = nx.DiGraph()
            for flow in flows:
                G.add_edge(
                    flow.from_country,
                    flow.to_country,
                    weight=flow.weight,
                )
            if G.number_of_nodes() < 2:
                return {}
            raw: dict[str, float] = nx.betweenness_centrality(G, weight="weight")
            return {k: round(v, 6) for k, v in raw.items()}

        except ImportError:
            logger.warning("build_panel_network.networkx_not_installed")
            return {}
        except Exception as exc:
            logger.warning("build_panel_network.centrality_failed", error=str(exc))
            return {}
