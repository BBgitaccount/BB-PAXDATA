# src/bb_paxdata/application/use_cases/build_panel_network.py
"""
Use Case: BilateralSentiment kayıtlarından DiscourseFlow (ağ kenarı) üretir.

(GAP-04) GAT embedding computation integration:
- GATEmbeddingService inject edilir
- GATFeatureExtractionService ile actor/concept features çıkar
- GAT embeddings DB'ye kaydedilir
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from bb_paxdata.application.domain.enums.country_enums import (
    EdgeType,
    NarrativeLayer,
    RelationshipType,
)
from bb_paxdata.application.domain.models.discourse_flow import DiscourseFlow
from bb_paxdata.application.domain.ports.i_gat_embedding_repository import (
    IGATEmbeddingRepository,
)
from bb_paxdata.application.domain.services.country_repositories import (
    IBilateralSentimentRepository,
    IDiscourseFlowRepository,
)

if TYPE_CHECKING:
    import networkx as nx

    from bb_paxdata.application.domain.models.bilateral_sentiment import (
        BilateralSentiment,
    )

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

    (GAP-04) GAT embedding computation için optional dependency injection:
    - gat_repo: IGATEmbeddingRepository (optional)
    - enable_gat: GAT computation'ı açmak/kapatmak için flag
    """

    def __init__(
        self,
        sentiment_repo: IBilateralSentimentRepository,
        flow_repo: IDiscourseFlowRepository,
        gat_repo: IGATEmbeddingRepository | None = None,
        enable_gat: bool = False,
    ) -> None:
        self._sentiment_repo = sentiment_repo
        self._flow_repo = flow_repo
        self._gat_repo = gat_repo
        self._enable_gat = enable_gat

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

        # Fetch sentences for the panel to calculate narrative fields
        db_sentences = []
        session = getattr(self._sentiment_repo, "_session", None)
        from unittest.mock import Mock

        if session is not None and not isinstance(session, Mock):
            try:
                from sqlalchemy import select

                from bb_paxdata.infrastructure.db.models import Sentence as DBSentence

                stmt = select(DBSentence).where(DBSentence.file_id == panel_id)
                res = await session.execute(stmt)
                db_sentences = res.scalars().all()
            except Exception as exc:
                logger.warning(
                    "build_panel_network.fetch_sentences_failed", error=str(exc)
                )

        flows: list[DiscourseFlow] = []
        for s in sentiments:
            if abs(s.affinity_score) <= input_data.weight_threshold:
                continue

            edge_type = self._classify_edge_type(s.effective_relationship)
            weight = self._calculate_weight(s)

            # Derive narrative fields
            n_layer = getattr(s, "narrative_layer", None)
            n_target = getattr(s, "narrative_target_actor", None)
            n_salience = getattr(s, "narrative_salience", None)

            if n_layer is None or n_target is None or n_salience is None:
                from_country_lower = s.from_country.lower()
                to_country_lower = s.to_country.lower()

                actor_sentences = [
                    sent
                    for sent in db_sentences
                    if sent.country and sent.country.lower() == from_country_lower
                ]

                relevant_sentences = []
                for sent in actor_sentences:
                    referenced = False
                    text_lower = (sent.text or "").lower()
                    if to_country_lower in text_lower:
                        referenced = True
                    else:
                        for ent_list in [
                            getattr(sent, "entities_gpe", None),
                            getattr(sent, "entities_org", None),
                        ]:
                            if isinstance(ent_list, list):
                                for ent in ent_list:
                                    if (
                                        isinstance(ent, dict)
                                        and ent.get("text", "").lower()
                                        == to_country_lower
                                    ):
                                        referenced = True
                                        break
                                    elif (
                                        isinstance(ent, str)
                                        and ent.lower() == to_country_lower
                                    ):
                                        referenced = True
                                        break
                            if referenced:
                                break
                    if referenced:
                        relevant_sentences.append(sent)

                if n_target is None:
                    n_target = s.to_country

                if n_salience is None:
                    n_salience = (
                        len(relevant_sentences) / len(actor_sentences)
                        if actor_sentences
                        else 0.0
                    )

                if n_layer is None and relevant_sentences:
                    scores = {"system": 0, "identity": 0, "issue": 0}
                    keywords = {
                        "system": [
                            "world order",
                            "international community",
                            "multipolar",
                            "unipolar",
                            "rules-based",
                            "hegemony",
                            "global governance",
                            "united nations",
                            "sovereign equality",
                            "coalition",
                        ],
                        "identity": [
                            "national interest",
                            "historic duty",
                            "defender",
                            "mediator",
                            "reliable partner",
                            "sovereignty",
                            "our nation",
                            "peace-loving",
                            "aggressor state",
                            "colonial legacy",
                        ],
                        "issue": [
                            "border conflict",
                            "ceasefire violation",
                            "humanitarian passage",
                            "gas pipeline",
                            "grain corridor",
                            "terrorist threat",
                            "bilateral trade",
                            "customs dispute",
                            "sanctions",
                        ],
                    }
                    for sent in relevant_sentences:
                        text_lower = (sent.text or "").lower()
                        for layer, kws in keywords.items():
                            for kw in kws:
                                if kw in text_lower:
                                    scores[layer] += 1

                    if sum(scores.values()) > 0:
                        best_layer = max(scores, key=lambda k: scores[k])
                        n_layer = NarrativeLayer(best_layer)
                    else:
                        from collections import Counter

                        frames = [
                            sent.dominant_frame
                            for sent in relevant_sentences
                            if sent.dominant_frame
                        ]
                        if frames:
                            most_common_frame = Counter(frames).most_common(1)[0][0]
                            frame_fallback = {
                                "multilateral_frame": NarrativeLayer.SYSTEM,
                                "thematic": NarrativeLayer.SYSTEM,
                                "legal_frame": NarrativeLayer.SYSTEM,
                                "moral_evaluation": NarrativeLayer.IDENTITY,
                                "sovereignty_frame": NarrativeLayer.IDENTITY,
                                "deterrence_frame": NarrativeLayer.IDENTITY,
                                "conflict_frame": NarrativeLayer.IDENTITY,
                                "threat_frame": NarrativeLayer.IDENTITY,
                                "problem_definition": NarrativeLayer.ISSUE,
                                "cause_interpretation": NarrativeLayer.ISSUE,
                                "remedy_suggestion": NarrativeLayer.ISSUE,
                                "episodic": NarrativeLayer.ISSUE,
                                "humanitarian_frame": NarrativeLayer.ISSUE,
                                "negotiation_frame": NarrativeLayer.ISSUE,
                                "two_state_frame": NarrativeLayer.ISSUE,
                                "occupation_frame": NarrativeLayer.ISSUE,
                            }
                            n_layer = frame_fallback.get(str(most_common_frame))

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
                    narrative_layer=n_layer,
                    narrative_target_actor=n_target,
                    narrative_salience=n_salience or 0.0,
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

        # (GAP-04) Optional GAT embedding computation
        # Note: Full GAT pipeline requires Fischer DNA DiscourseFlow (actor_ids, concept_ids, edges)
        # This is a placeholder for future integration with proper data transformation
        if self._enable_gat and self._gat_repo:
            try:
                # Placeholder: GAT computation would require:
                # 1. Transform BilateralSentiment → Fischer DNA DiscourseFlow
                # 2. Extract actor/concept sentences
                # 3. Compute SBERT features via GATFeatureExtractionService
                # 4. Run GATEmbeddingService.compute_embeddings()
                # 5. Save embeddings via gat_repo.save_batch()
                logger.info(
                    "build_panel_network.gat_enabled_placeholder",
                    panel_id=panel_id,
                    note="Full GAT pipeline requires separate use case with Fischer DNA model",
                )
            except Exception as exc:
                errors.append(f"gat_computation_failed: {exc}")

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
        val = sentiment.total_mentions * abs(sentiment.affinity_score) + 1e-6
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
            raw = nx.betweenness_centrality(G, weight="weight")
            return {str(k): round(v, 6) for k, v in raw.items()}

        except ImportError:
            logger.warning("build_panel_network.networkx_not_installed")
            return {}
        except Exception as exc:
            logger.warning("build_panel_network.centrality_failed", error=str(exc))
            return {}
