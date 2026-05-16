from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bb_paxdata.infrastructure.db.base import Base


class TopicAssignmentORM(Base):
    __tablename__ = "topic_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    segment_id: Mapped[str] = mapped_column(String(64), index=True)
    analysis_id: Mapped[str] = mapped_column(String(64), index=True)
    primary_topic: Mapped[str] = mapped_column(String(64))
    topic_scores: Mapped[dict[str, float]] = mapped_column(
        JSON
    )  # {topic_id: probability}
    topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ctfidf_keywords: Mapped[dict[str, float]] = mapped_column(JSON)  # {word: score}

    # Audit
    model_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON
    )  # SBERT model, UMAP params, etc.
