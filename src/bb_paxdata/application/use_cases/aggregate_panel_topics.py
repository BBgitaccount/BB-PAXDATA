# src/bb_paxdata/application/use_cases/aggregate_panel_topics.py
"""
Use Case: Panel × ülke bazında konu skorlarını çaprazlar, TopicSynthesis üretir.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import structlog
from bb_paxdata.application.domain.models.topic_synthesis import TopicSynthesis
from bb_paxdata.application.domain.services.country_repositories import (
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

        # Get session from ref_repo
        session = self._ref_repo.session
        from bb_paxdata.infrastructure.db.models import Sentence as SentenceORM
        from sqlalchemy import select

        # Retrieve all sentences for this panel to get their country & topic scores
        stmt = select(SentenceORM).where(SentenceORM.file_id == panel_id)
        res = await session.execute(stmt)
        sentences = res.scalars().all()

        # Ülke başına kümülatif topic skorları topla
        country_scores: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        for sent in sentences:
            country = sent.country
            if not country or country.lower() == "unknown":
                continue
            if sent.topic_scores:
                for topic, score in sent.topic_scores.items():
                    country_scores[country][topic] += score

        # If country_scores is empty, fall back to referencing active countries and input dictionary
        if not country_scores:
            references = await self._ref_repo.get_by_panel(panel_id)
            if not references:
                return AggregatePanelTopicsOutput(
                    panel_id=panel_id, synthesized_count=0
                )
            for ref in references:
                country = ref.speaker_country
                if country and country.lower() != "unknown":
                    analysis_id = ref.panel_id
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
