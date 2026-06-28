# src/bb_paxdata/application/use_cases/visualization/get_reference_flows_use_case.py

from collections import defaultdict

from bb_paxdata.application.domain.dtos.visualization_dtos import ReferenceFlowDTO
from bb_paxdata.application.domain.ports.i_visualization_repository import (
    IVisualizationRepository,
)


class GetReferenceFlowsUseCase:
    def __init__(self, repository: IVisualizationRepository) -> None:
        self.repository = repository

    async def execute(
        self, session_id: str | None = None, context_type: str | None = None
    ) -> list[ReferenceFlowDTO]:
        # 1. Fetch grouped flows from DB
        raw_flows = await self.repository.get_reference_flows(session_id, context_type)

        # 2. Group by (speaker_country, referenced_country, reference_context) in Python
        grouped = defaultdict(list)
        for f in raw_flows:
            key = (
                f["speaker_country"],
                f["referenced_country"],
                f["reference_context"],
            )
            grouped[key].append(f)

        flows: list[ReferenceFlowDTO] = []
        for (spk, ref, ctx), records in grouped.items():
            total_count = sum(r["cnt"] for r in records)
            if total_count == 0:
                continue

            # Weighted average sentiment
            weighted_sent_sum = sum(r["avg_sent"] * r["cnt"] for r in records)
            avg_sent = weighted_sent_sum / total_count

            # Distinct session IDs
            sessions = sorted(list(set(r["file_id"] for r in records)))

            flows.append(
                ReferenceFlowDTO(
                    speaker_country=spk,
                    referenced_country=ref,
                    context=ctx,
                    count=total_count,
                    avg_sentiment=round(avg_sent, 4),
                    sessions=sessions,
                )
            )

        return flows
