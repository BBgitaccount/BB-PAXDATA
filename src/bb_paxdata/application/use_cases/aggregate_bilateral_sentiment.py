# src/bb_paxdata/application/use_cases/aggregate_bilateral_sentiment.py
"""
Use Case: Bir paneldeki tüm CountryReference'lardan BilateralSentiment aggregate'lerini üretir.
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog
from bb_paxdata.domain.models.bilateral_sentiment import BilateralSentiment
from bb_paxdata.domain.models.country_reference import CountryReference
from bb_paxdata.domain.services.country_repositories import (
    IBilateralSentimentRepository,
    ICountryReferenceRepository,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AggregateBilateralSentimentInput:
    panel_id: str


@dataclass(frozen=True)
class AggregateBilateralSentimentOutput:
    panel_id: str
    created_count: int
    updated_count: int
    total_pairs: int
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return len(self.errors) == 0


class AggregateBilateralSentimentUseCase:
    """
    Panel içindeki tüm atıfları (CountryReference) okuyarak
    ülke çiftleri arasındaki BilateralSentiment kayıtlarını upsert eder.
    """

    def __init__(
        self,
        ref_repo: ICountryReferenceRepository,
        sentiment_repo: IBilateralSentimentRepository,
    ) -> None:
        self._ref_repo = ref_repo
        self._sentiment_repo = sentiment_repo

    async def execute(
        self, input_data: AggregateBilateralSentimentInput
    ) -> AggregateBilateralSentimentOutput:
        panel_id = input_data.panel_id
        errors: list[str] = []
        created = 0
        updated = 0

        try:
            references = await self._ref_repo.get_by_panel(panel_id)
        except Exception as exc:
            logger.error(
                "aggregate_bilateral.read_failed", panel_id=panel_id, error=str(exc)
            )
            return AggregateBilateralSentimentOutput(
                panel_id=panel_id,
                created_count=0,
                updated_count=0,
                total_pairs=0,
                errors=(str(exc),),
            )

        # (from, to) çiftlerine göre grupla
        pair_map: dict[tuple[str, str], list[CountryReference]] = {}
        for ref in references:
            key = (ref.speaker_country, ref.referenced_country)
            pair_map.setdefault(key, []).append(ref)

        for (from_c, to_c), refs in pair_map.items():
            try:
                existing = await self._sentiment_repo.get_by_pair(
                    from_c, to_c, panel_id
                )
                is_new = existing is None

                # Sıfır noktası: mevcut yoksa taze model oluştur
                sentiment = existing or BilateralSentiment(
                    panel_id=panel_id,
                    from_country=from_c,
                    to_country=to_c,
                )

                # Her atıfı sırayla uygula (R2: with_new_reference immutable güncelleme yapar)
                for ref in refs:
                    sentiment = sentiment.with_new_reference(
                        sentiment=ref.raw_sentiment_score,
                        power_level=ref.speaker_power_level,
                    )

                await self._sentiment_repo.upsert(sentiment)
                if is_new:
                    created += 1
                else:
                    updated += 1

            except Exception as exc:
                error_msg = f"{from_c}->{to_c}: {exc}"
                logger.warning("aggregate_bilateral.pair_failed", error=error_msg)
                errors.append(error_msg)

        logger.info(
            "aggregate_bilateral.completed",
            panel_id=panel_id,
            created=created,
            updated=updated,
            errors=len(errors),
        )
        return AggregateBilateralSentimentOutput(
            panel_id=panel_id,
            created_count=created,
            updated_count=updated,
            total_pairs=len(pair_map),
            errors=tuple(errors),
        )
