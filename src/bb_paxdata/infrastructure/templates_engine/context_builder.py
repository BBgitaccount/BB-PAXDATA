# src/bb_paxdata/infrastructure/templates_engine/context_builder.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from bb_paxdata.infrastructure.db.models import File
from bb_paxdata.infrastructure.db.session import get_db_session


class TemplateContextBuilder:
    """Build template context from database for template rendering."""

    @staticmethod
    def build_context(file_id: str) -> dict[str, Any]:
        """
        Build template context from file data.

        Args:
            file_id: File ID to build context for

        Returns:
            Dictionary with all template variables
        """
        with get_db_session() as session:
            stmt = select(File).where(File.file_id == file_id)
            file_obj = session.scalars(stmt).first()

            if not file_obj:
                raise ValueError(f"File not found: {file_id}")

            # Build speakers data
            speakers_data = []
            speaker_stats = {}

            for segment in file_obj.segments:
                speaker_name = segment.speaker_name
                if speaker_name not in speaker_stats:
                    speaker_stats[speaker_name] = {
                        "name": speaker_name,
                        "country": segment.country or "Unknown",
                        "statement_count": 0,
                        "total_risk": 0,
                        "total_sbi": 0,
                    }
                speaker_stats[speaker_name]["statement_count"] += 1
                speaker_stats[speaker_name]["total_risk"] += segment.risk_score
                speaker_stats[speaker_name]["total_sbi"] += segment.sbi_score

            for name, stats in speaker_stats.items():
                count = stats["statement_count"]
                speakers_data.append(
                    {
                        "name": name,
                        "country": stats["country"],
                        "statement_count": count,
                        "avg_risk_score": (
                            stats["total_risk"] / count if count > 0 else 0
                        ),
                        "dominant_sbi": (
                            "B" if stats["total_sbi"] / count > 0.5 else "S"
                        ),
                    }
                )

            # Build analysis data
            total_segments = len(file_obj.segments)
            high_risk_count = sum(1 for s in file_obj.segments if s.risk_score >= 7)
            medium_risk_count = sum(
                1 for s in file_obj.segments if 4 <= s.risk_score < 7
            )
            low_risk_count = total_segments - high_risk_count - medium_risk_count

            # Extract top themes
            theme_counts = {}
            for segment in file_obj.segments:
                topic = segment.dominant_topic
                if topic:
                    theme_counts[topic] = theme_counts.get(topic, 0) + 1

            top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]

            # Build risks data
            risks_data = []
            for segment in file_obj.segments:
                if segment.risk_score >= 5:
                    risks_data.append(
                        {
                            "level": "HIGH" if segment.risk_score >= 7 else "MEDIUM",
                            "description": segment.text[:200],
                            "speaker": segment.speaker_name,
                            "timestamp": segment.ts_start_sec,
                            "score": segment.risk_score,
                        }
                    )

            # Build SBI distribution
            sum(s.sbi_score for s in file_obj.segments)
            sbi_dist = {"S": 0, "B": 0, "I": 0}
            for segment in file_obj.segments:
                if segment.sbi_score > 0.6:
                    sbi_dist["S"] += 1
                elif segment.sbi_score > 0.3:
                    sbi_dist["B"] += 1
                else:
                    sbi_dist["I"] += 1

            context = {
                "session": {
                    "title": file_obj.title or file_obj.file_name,
                    "date": (
                        file_obj.imported_at.isoformat()
                        if file_obj.imported_at
                        else None
                    ),
                    "duration_minutes": (
                        file_obj.total_duration_sec // 60
                        if file_obj.total_duration_sec
                        else 0
                    ),
                    "location": "Unknown",
                    "classification": "CONFIDENTIAL",
                    "participant_count": file_obj.n_speakers,
                },
                "speakers": speakers_data,
                "analysis": {
                    "summary": f"Analysis of {total_segments} segments from {file_obj.n_speakers} speakers.",
                    "sbi": sbi_dist,
                    "top_themes": [t[0] for t in top_themes],
                    "risk_distribution": {
                        "LOW": low_risk_count,
                        "MEDIUM": medium_risk_count,
                        "HIGH": high_risk_count,
                    },
                    "key_quotes": [r["description"] for r in risks_data[:3]],
                },
                "risks": risks_data[:20],  # Limit to top 20
                "report": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "generated_by": "system",
                    "version": "1.0",
                },
            }

            return context
