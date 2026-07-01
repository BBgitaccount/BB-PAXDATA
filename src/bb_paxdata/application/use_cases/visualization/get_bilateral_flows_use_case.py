# src/bb_paxdata/application/use_cases/visualization/get_bilateral_flows_use_case.py

from collections import Counter, defaultdict

from bb_paxdata.application.domain.dtos.visualization_dtos import BilateralFlowDTO
from bb_paxdata.application.domain.ports.i_visualization_repository import (
    IVisualizationRepository,
)
from bb_paxdata.infrastructure.mappings.country_iso_map import (
    get_iso_alpha3,
    is_unknown_country,
)


class GetBilateralFlowsUseCase:
    def __init__(self, repository: IVisualizationRepository) -> None:
        self.repository = repository

    async def execute(
        self,
        session_ids: list[str] | None = None,
        min_interactions: int = 2,
        relationship_types: list[str] | None = None,
        min_affinity: float = -1.0,
    ) -> list[BilateralFlowDTO]:
        # 1. Fetch bilateral records
        bilaterals = await self.repository.get_bilateral_sentiment_aggregates(
            session_ids, relationship_types
        )

        # 2. Query references in bulk to calculate praise and accusation ratios
        # If session_ids is a single element list, pass it directly. If it's a list, we can filter in python or fetch all.
        # Since get_reference_flows has session_id parameter, we can fetch all or a specific one. Let's write a loop or fetch all and filter in Python.
        # Fetching all reference flows for grouping is efficient.
        ref_flows = await self.repository.get_reference_flows()

        # Filter ref_flows by session if session_ids is provided
        if session_ids:
            ref_flows = [r for r in ref_flows if r["file_id"] in session_ids]

        # Group references by (speaker_country, referenced_country)
        ref_counts = defaultdict(Counter)
        for ref in ref_flows:
            pair = (ref["speaker_country"], ref["referenced_country"])
            ref_counts[pair][ref["reference_context"]] += ref["cnt"]

        # 3. Group bilaterals by (from_country, to_country)
        grouped_flows = defaultdict(list)
        for b in bilaterals:
            pair = (b["from_country"], b["to_country"])
            grouped_flows[pair].append(b)

        flows: list[BilateralFlowDTO] = []
        for (from_c, to_c), records in grouped_flows.items():
            if is_unknown_country(from_c) or is_unknown_country(to_c):
                continue
            total_interactions = sum(r["interaction_count"] for r in records)
            if total_interactions < min_interactions:
                continue

            avg_affinity = sum(r["affinity_score"] for r in records) / len(records)
            if avg_affinity < min_affinity:
                continue

            avg_sent = sum(r["avg_sentiment"] for r in records) / len(records)
            avg_pw = sum(r["power_weighted_score"] for r in records) / len(records)

            # Most common relationship type
            rel_types = [
                r["relationship_type"] for r in records if r["relationship_type"]
            ]
            relationship_type = (
                Counter(rel_types).most_common(1)[0][0] if rel_types else "NEUTRAL"
            )

            # Sessions list
            sessions = sorted(list(set(r["file_id"] for r in records)))

            # Praise and accusation ratios
            pair_refs = ref_counts.get((from_c, to_c), Counter())
            praise = pair_refs["PRAISE"]
            accusation = pair_refs["ACCUSATION"]
            neutral = pair_refs["NEUTRAL_MENTION"]
            total_refs = praise + accusation + neutral

            praise_ratio = praise / total_refs if total_refs > 0 else 0.0
            accusation_ratio = accusation / total_refs if total_refs > 0 else 0.0

            flows.append(
                BilateralFlowDTO(
                    from_country=from_c,
                    to_country=to_c,
                    from_iso3=get_iso_alpha3(from_c),
                    to_iso3=get_iso_alpha3(to_c),
                    interaction_count=total_interactions,
                    avg_sentiment=round(avg_sent, 4),
                    affinity_score=round(avg_affinity, 4),
                    power_weighted_score=round(avg_pw, 4),
                    relationship_type=relationship_type,
                    praise_ratio=round(praise_ratio, 4),
                    accusation_ratio=round(accusation_ratio, 4),
                    sessions=sessions,
                )
            )

        return flows
