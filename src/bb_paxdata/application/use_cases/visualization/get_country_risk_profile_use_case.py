# src/bb_paxdata/application/use_cases/visualization/get_country_risk_profile_use_case.py

from collections import Counter

from bb_paxdata.application.domain.dtos.visualization_dtos import CountryRiskProfileDTO
from bb_paxdata.application.domain.ports.i_visualization_repository import (
    IVisualizationRepository,
)
from bb_paxdata.infrastructure.mappings.country_iso_map import is_unknown_country


class GetCountryRiskProfileUseCase:
    def __init__(self, repository: IVisualizationRepository) -> None:
        self.repository = repository

    async def execute(self, country: str) -> CountryRiskProfileDTO:
        # 1. Query all relevant datasets for the target country in bulk
        pair_sentiments = await self.repository.get_pair_sentiments_for_country(country)
        stats = await self.repository.get_country_stats_for_country(country)
        speaker_summary = await self.repository.get_speaker_references_summary(country)
        target_summary = await self.repository.get_target_references_summary(country)

        # Filter out unknown countries
        pair_sentiments = [
            p
            for p in pair_sentiments
            if not is_unknown_country(p["from_country"])
            and not is_unknown_country(p["to_country"])
        ]
        target_summary = [
            t for t in target_summary if not is_unknown_country(t["speaker_country"])
        ]

        # 2. Process relationship metrics
        total_mentions = sum(p["total_mentions"] for p in pair_sentiments)
        ally_count = sum(1 for p in pair_sentiments if p["relationship_type"] == "ALLY")
        adversary_count = sum(
            1 for p in pair_sentiments if p["relationship_type"] == "ADVERSARY"
        )

        breakdown = Counter()
        for p in pair_sentiments:
            if p["relationship_type"]:
                breakdown[p["relationship_type"]] += 1

        # 3. Process session active statistics
        sessions_active = sorted(list(set(s["file_id"] for s in stats)))

        if stats:
            avg_sent = sum(s["avg_sentiment"] for s in stats) / len(stats)
            emotions = [s["dominant_emotion"] for s in stats if s["dominant_emotion"]]
            dominant_emotion = (
                Counter(emotions).most_common(1)[0][0] if emotions else "NEUTRAL"
            )
        else:
            avg_sent = 0.0
            dominant_emotion = "NEUTRAL"

        # 4. Process speaker metrics
        sentiment_as_speaker = speaker_summary.get("avg_sentiment", 0.0)

        # 5. Process target metrics (references where this country is the target)
        total_target_refs = sum(t["count"] for t in target_summary)
        accusation_cnt = sum(
            t["count"] for t in target_summary if t["reference_context"] == "ACCUSATION"
        )
        sum(t["count"] for t in target_summary if t["reference_context"] == "PRAISE")

        if total_target_refs > 0:
            weighted_target_sent = sum(
                t["avg_sentiment"] * t["count"] for t in target_summary
            )
            sentiment_as_target = weighted_target_sent / total_target_refs
            accusation_ratio = accusation_cnt / total_target_refs
        else:
            sentiment_as_target = 0.0
            accusation_ratio = 0.0

        # 6. Group top accusers and praise givers
        accusers_cnt = Counter()
        praise_givers_cnt = Counter()
        for t in target_summary:
            if t["reference_context"] == "ACCUSATION":
                accusers_cnt[t["speaker_country"]] += t["count"]
            elif t["reference_context"] == "PRAISE":
                praise_givers_cnt[t["speaker_country"]] += t["count"]

        top_accusers = [
            {"country": k, "count": v}
            for k, v in sorted(accusers_cnt.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]
        ]
        top_praise_givers = [
            {"country": k, "count": v}
            for k, v in sorted(
                praise_givers_cnt.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

        return CountryRiskProfileDTO(
            country=country,
            total_mentions=total_mentions,
            avg_sentiment=round(avg_sent, 4),
            sentiment_as_speaker=round(sentiment_as_speaker, 4),
            sentiment_as_target=round(sentiment_as_target, 4),
            ally_count=ally_count,
            adversary_count=adversary_count,
            accusation_ratio=round(accusation_ratio, 4),
            dominant_emotion=dominant_emotion,
            sessions_active=sessions_active,
            top_accusers=top_accusers,
            top_praise_givers=top_praise_givers,
            relationship_breakdown=dict(breakdown),
        )
