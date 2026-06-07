# src/bb_paxdata/application/services/baseline_fetcher.py
from __future__ import annotations

from collections import Counter
from typing import Any, Callable

import numpy as np
from bb_paxdata.application.domain.services.protocols.judge_protocols import (
    BaselineMetrics,
)
from sqlalchemy import select


class RollingWindowBaselineFetcher:
    def __init__(
        self, session_factory: Callable[[], Any], window_size: int = 10
    ) -> None:
        self._session_factory = session_factory
        self._window_size = window_size

    async def fetch(
        self, speaker_name: str, country: str, exclude_panel_id: str | None = None
    ) -> BaselineMetrics:
        from bb_paxdata.infrastructure.db.models import AISentenceAnalysis, Sentence

        async with self._session_factory() as session:
            # Subquery: last W panels for this speaker/country
            subq = (
                select(Sentence.file_id)
                .where(
                    Sentence.speaker_name == speaker_name,
                    Sentence.country == country,
                )
                .distinct()
                .order_by(Sentence.file_id.desc())
                .limit(self._window_size)
            )
            panel_ids = (await session.execute(subq)).scalars().all()

            if exclude_panel_id and exclude_panel_id in panel_ids:
                panel_ids = [p for p in panel_ids if p != exclude_panel_id]

            if not panel_ids:
                return BaselineMetrics(
                    historical_sentiment_avg=0.0,
                    historical_risk_avg=5.0,
                    historical_frame_mode="neutral",
                    window_size=0,
                    panel_ids_in_window=[],
                )

            # Retrieve scores in the window to calculate averages and mode in Python (SQLite compatible)
            stmt = (
                select(
                    AISentenceAnalysis.sentiment_score,
                    AISentenceAnalysis.risk_score,
                    Sentence.dominant_frame,
                )
                .join(Sentence, AISentenceAnalysis.sent_id == Sentence.sent_id)
                .where(
                    Sentence.speaker_name == speaker_name,
                    Sentence.country == country,
                    Sentence.file_id.in_(panel_ids),
                )
            )
            rows = (await session.execute(stmt)).all()

            if not rows:
                return BaselineMetrics(
                    historical_sentiment_avg=0.0,
                    historical_risk_avg=5.0,
                    historical_frame_mode="neutral",
                    window_size=len(panel_ids),
                    panel_ids_in_window=list(panel_ids),
                )

            sentiments = [r[0] for r in rows if r[0] is not None]
            risks = [r[1] for r in rows if r[1] is not None]
            frames = [r[2] for r in rows if r[2] is not None and r[2] != ""]

            avg_sentiment = float(np.mean(sentiments)) if sentiments else 0.0
            avg_risk = float(np.mean(risks)) * 10.0 if risks else 5.0

            frame_counts = Counter(frames)
            mode_frame = frame_counts.most_common(1)[0][0] if frames else "neutral"

            return BaselineMetrics(
                historical_sentiment_avg=avg_sentiment,
                historical_risk_avg=avg_risk,
                historical_frame_mode=str(mode_frame),
                window_size=len(panel_ids),
                panel_ids_in_window=list(panel_ids),
            )
