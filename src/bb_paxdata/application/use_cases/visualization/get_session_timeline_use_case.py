# src/bb_paxdata/application/use_cases/visualization/get_session_timeline_use_case.py

from collections import Counter, defaultdict

from bb_paxdata.application.domain.dtos.visualization_dtos import SessionTimelineDTO
from bb_paxdata.application.domain.ports.i_visualization_repository import (
    IVisualizationRepository,
)


class GetSessionTimelineUseCase:
    def __init__(self, repository: IVisualizationRepository) -> None:
        self.repository = repository

    async def execute(self) -> list[SessionTimelineDTO]:
        # 1. Fetch all datasets in bulk (prevents N+1 database roundtrips)
        sessions = await self.repository.get_sessions_list()
        all_stats = await self.repository.get_country_stats()
        all_bilaterals = await self.repository.get_bilateral_sentiment_aggregates()
        all_refs = await self.repository.get_all_reference_counts()

        # 2. Group datasets by file_id for quick indexing
        stats_by_session = defaultdict(list)
        for s in all_stats:
            stats_by_session[s["file_id"]].append(s)

        bilat_by_session = defaultdict(list)
        for b in all_bilaterals:
            bilat_by_session[b["file_id"]].append(b)

        refs_by_session = {r["file_id"]: r for r in all_refs}

        timeline: list[SessionTimelineDTO] = []
        for sess in sessions:
            file_id = sess["file_id"]

            # Formulate user-friendly label
            if sess["title"]:
                label = sess["title"]
            elif sess["file_name"]:
                label = sess["file_name"]
            else:
                label = file_id.replace("_", " ").replace("-", " ").title()

            # Get stats for this session
            sess_stats = stats_by_session.get(file_id, [])
            sess_bilat = bilat_by_session.get(file_id, [])
            sess_refs = refs_by_session.get(file_id, {})

            # Active countries list
            countries_set = (
                set(s["country"] for s in sess_stats)
                | set(b["from_country"] for b in sess_bilat)
                | set(b["to_country"] for b in sess_bilat)
            )
            countries = sorted(list(countries_set))

            # In-session average sentiment
            if sess_stats:
                avg_sent = sum(s["avg_sentiment"] for s in sess_stats) / len(sess_stats)
            else:
                avg_sent = 0.0

            # In-session dominant emotion (mode)
            emotions = [
                s["dominant_emotion"] for s in sess_stats if s["dominant_emotion"]
            ]
            dom_emotion = (
                Counter(emotions).most_common(1)[0][0] if emotions else "NEUTRAL"
            )

            # Top 5 relationships in this session by interaction count
            sorted_bilats = sorted(
                sess_bilat, key=lambda x: x["interaction_count"], reverse=True
            )
            top_relationships = [
                {
                    "from": b["from_country"],
                    "to": b["to_country"],
                    "type": b["relationship_type"],
                    "score": b["affinity_score"],
                }
                for b in sorted_bilats[:5]
            ]

            praise_cnt = sess_refs.get("praise_cnt", 0)
            accusation_cnt = sess_refs.get("accusation_cnt", 0)

            timeline.append(
                SessionTimelineDTO(
                    session_id=file_id,
                    session_label=label,
                    countries=countries,
                    avg_sentiment=round(avg_sent, 4),
                    dominant_emotion=dom_emotion,
                    top_relationships=top_relationships,
                    praise_count=praise_cnt,
                    accusation_count=accusation_cnt,
                    created_at=sess["imported_at"],
                )
            )

        return timeline
