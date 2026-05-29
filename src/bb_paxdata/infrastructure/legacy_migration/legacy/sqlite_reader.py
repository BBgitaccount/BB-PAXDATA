from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from bb_paxdata.domain.entities.legacy import LegacyAnalyticIndex, LegacyTranscript


class LegacySQLiteReader:
    """Reads data from legacy monolithic SQLite database."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def count_transcripts(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM transcripts")
            return int(cursor.fetchone()[0])

    async def fetch_transcripts(
        self, batch_size: int, offset: int
    ) -> list[LegacyTranscript]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM transcripts LIMIT ? OFFSET ?",
                (batch_size, offset),
            )
            rows = cursor.fetchall()

            transcripts = []
            for row in rows:
                # Metadata might be stored as JSON
                meta = {}
                if "metadata" in row.keys() and row["metadata"]:
                    try:
                        meta = json.loads(row["metadata"])
                    except json.JSONDecodeError:
                        pass

                # TF-IDF keywords comma separated string olabilir
                keywords = []
                if "tfidf_keywords" in row.keys() and row["tfidf_keywords"]:
                    keywords = [k.strip() for k in row["tfidf_keywords"].split(",")]

                transcripts.append(
                    LegacyTranscript(
                        id=row["id"],
                        speaker_name=row["speaker_name"],
                        country_code=row.get("country_code"),
                        raw_text=row["raw_text"],
                        timestamp=(
                            datetime.fromisoformat(row["timestamp"])
                            if row.get("timestamp")
                            else None
                        ),
                        vader_compound=row.get("vader_compound"),
                        power_level=row.get("power_level"),
                        tfidf_keywords=keywords,
                        metadata=meta,
                    )
                )
            return transcripts

    async def fetch_analytics(
        self, transcript_ids: list[int]
    ) -> list[LegacyAnalyticIndex]:
        if not transcript_ids:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in transcript_ids)
            cursor.execute(
                f"SELECT * FROM analytics WHERE transcript_id IN ({placeholders})",
                transcript_ids,
            )
            rows = cursor.fetchall()

            analytics = []
            for row in rows:
                # Framing labels might be stored as JSON
                framing = {}
                if "framing_labels" in row.keys() and row["framing_labels"]:
                    try:
                        framing = json.loads(row["framing_labels"])
                    except json.JSONDecodeError:
                        pass

                # Hedging markers comma separated string olabilir
                hedging = []
                if "hedging_markers" in row.keys() and row["hedging_markers"]:
                    hedging = [h.strip() for h in row["hedging_markers"].split(",")]

                analytics.append(
                    LegacyAnalyticIndex(
                        transcript_id=row["transcript_id"],
                        sbi_score=row.get("sbi_score"),
                        dki_score=row.get("dki_score"),
                        hedging_markers=hedging,
                        framing_labels=framing,
                        raw_ai_output=row.get("raw_ai_output"),
                    )
                )
            return analytics

    async def close(self) -> None:
        pass
