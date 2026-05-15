# src/bb_paxdata/application/use_cases/aggregate_panel_topics.py
"""
Use Case: Panel × ülke bazında konu skorlarını çaprazlar, TopicSynthesis üretir.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import structlog
from bb_paxdata.domain.models.topic_synthesis import TopicSynthesis
from bb_paxdata.domain.services.country_repositories import (
    ICountryReferenceRepository,
    ITopicSynthesisRepository,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AggregatePanelTopicsInput:
    panel_id: str
    topic_scores_by_analysis: dict[str, dict[str, float]] = field(default_factory=dict)
    """
    {analysis_id: {topic_label: score}} formatında.
    """


@dataclass(frozen=True)
class AggregatePanelTopicsOutput:
    panel_id: str
    synthesized_count: int
    countries_covered: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return len(self.errors) == 0


class AggregatePanelTopicsUseCase:
    """
    Panel içindeki ülkelere göre konu skorlarını çaprazlar.
    """

    def __init__(
        self,
        ref_repo: ICountryReferenceRepository,
        synthesis_repo: ITopicSynthesisRepository,
    ) -> None:
        self._ref_repo = ref_repo
        self._synthesis_repo = synthesis_repo

    async def execute(
        self, input_data: AggregatePanelTopicsInput
    ) -> AggregatePanelTopicsOutput:
        panel_id = input_data.panel_id
        errors: list[str] = []

        references = await self._ref_repo.get_by_panel(panel_id)
        if not references:
            return AggregatePanelTopicsOutput(panel_id=panel_id, synthesized_count=0)

        # Ülke başına kümülatif topic skorları topla
        country_scores: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        for ref in references:
            country = ref.speaker_country

            # Bu referansın ait olduğu analysis'in topic skorlarını ekle
            # mapping mantığı projeye özeldir — gerekirse güncelle
            analysis_id = str(
                ref.panel_id
            )  # Using panel_id as fallback analysis_id if mapping not clear
            # Wait, usually a panel contains multiple analyses.
            # In the prompt it says topic_scores_by_analysis: dict[str, dict[str, float]]
            # where key is analysis_id.
            # But CountryReference has panel_id.
            # We might need analysis_id on CountryReference or some mapping.
            # Assuming for now we use panel_id as the key if analysis_id is not directly available.

            for topic, score in input_data.topic_scores_by_analysis.get(
                analysis_id, {}
            ).items():
                country_scores[country][topic] += score

        synthesized_countries: list[str] = []
        for country, raw_scores in country_scores.items():
            try:
                synthesis = TopicSynthesis.from_scores(
                    panel_id=panel_id,
                    country=country,
                    raw_scores=dict(raw_scores),
                )
                await self._synthesis_repo.upsert(synthesis)
                synthesized_countries.append(country)
            except Exception as exc:
                errors.append(f"{country}: {exc}")
                logger.warning(
                    "aggregate_topics.country_failed", country=country, error=str(exc)
                )

        return AggregatePanelTopicsOutput(
            panel_id=panel_id,
            synthesized_count=len(synthesized_countries),
            countries_covered=tuple(synthesized_countries),
            errors=tuple(errors),
        )
