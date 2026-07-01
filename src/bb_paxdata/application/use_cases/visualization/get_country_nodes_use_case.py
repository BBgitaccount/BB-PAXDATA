# src/bb_paxdata/application/use_cases/visualization/get_country_nodes_use_case.py

from collections import Counter, defaultdict

from bb_paxdata.application.domain.dtos.visualization_dtos import CountryNodeDTO
from bb_paxdata.application.domain.ports.i_visualization_repository import (
    IVisualizationRepository,
)
from bb_paxdata.infrastructure.mappings.country_iso_map import (
    get_iso_alpha3,
    is_unknown_country,
)


class GetCountryNodesUseCase:
    def __init__(self, repository: IVisualizationRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        session_ids: list[str] | None = None,
        relationship_types: list[str] | None = None,
    ) -> list[CountryNodeDTO]:
        # 1. Fetch aggregates from DB (avoiding N+1 by using optimized repository methods)
        ref_aggregates = await self.repository.get_country_reference_aggregates(
            session_ids
        )
        stats = await self.repository.get_country_stats(session_ids)
        bilateral_sentiments = await self.repository.get_bilateral_sentiment_aggregates(
            session_ids, relationship_types
        )

        # 2. Get distinct sessions per country to compile the session list accurately
        country_sessions = defaultdict(set)
        for stat in stats:
            country_sessions[stat["country"]].add(stat["file_id"])
        for bilat in bilateral_sentiments:
            country_sessions[bilat["from_country"]].add(bilat["file_id"])
            country_sessions[bilat["to_country"]].add(bilat["file_id"])

        # 3. Create helper dicts for fast merging
        # Reference aggregates by country
        ref_map = {}
        for ref in ref_aggregates:
            ref_map[ref["speaker_country"]] = ref

        # Stats by country: list of stats to compute average and dominant emotion
        stats_map = defaultdict(list)
        for stat in stats:
            stats_map[stat["country"]].append(stat)

        # Bilateral sentiment relationships by country
        bilat_relations = defaultdict(list)
        for bilat in bilateral_sentiments:
            bilat_relations[bilat["from_country"]].append(bilat)
            bilat_relations[bilat["to_country"]].append(bilat)

        # 4. Compile the list of all unique countries
        all_countries = {
            c
            for c in (
                set(ref_map.keys())
                | set(stats_map.keys())
                | set(bilat_relations.keys())
            )
            if not is_unknown_country(c)
        }

        nodes: list[CountryNodeDTO] = []
        for country in all_countries:
            # Power level & reference counts
            ref_data = ref_map.get(country)
            power_level = ref_data["avg_power"] if ref_data else 0.5
            praise_cnt = ref_data["praise_cnt"] if ref_data else 0
            accusation_cnt = ref_data["accusation_cnt"] if ref_data else 0
            neutral_cnt = ref_data["neutral_cnt"] if ref_data else 0

            # Interactions count & relationship categories
            total_interactions = 0
            categories = Counter()
            for b in bilat_relations[country]:
                total_interactions += b["interaction_count"]
                if b["relationship_type"]:
                    categories[b["relationship_type"]] += 1

            # Average sentiment and dominant emotion from CountryStats
            country_stats_list = stats_map.get(country, [])
            if country_stats_list:
                avg_sent = sum(s["avg_sentiment"] for s in country_stats_list) / len(
                    country_stats_list
                )
                emotions = [
                    s["dominant_emotion"]
                    for s in country_stats_list
                    if s["dominant_emotion"]
                ]
                dom_emotion = (
                    Counter(emotions).most_common(1)[0][0] if emotions else "NEUTRAL"
                )
            else:
                # Fallback to bilateral average sentiment
                bilat_sentiments_list = [
                    b["avg_sentiment"]
                    for b in bilat_relations[country]
                    if b["from_country"] == country
                ]
                avg_sent = (
                    sum(bilat_sentiments_list) / len(bilat_sentiments_list)
                    if bilat_sentiments_list
                    else 0.0
                )
                dom_emotion = "NEUTRAL"

            nodes.append(
                CountryNodeDTO(
                    country=country,
                    iso_alpha3=get_iso_alpha3(country),
                    total_interactions=total_interactions,
                    avg_sentiment=round(avg_sent, 4),
                    dominant_emotion=dom_emotion,
                    relationship_categories=dict(categories),
                    praise_count=praise_cnt,
                    accusation_count=accusation_cnt,
                    neutral_count=neutral_cnt,
                    power_level=round(power_level, 4),
                    sessions=sorted(list(country_sessions[country])),
                )
            )

        return nodes
