from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from bb_paxdata.application.domain.models.topic_synthesis import TopicSynthesis


@runtime_checkable
class ITopicAssignmentRepository(Protocol):
    """Port for persisting BERTopic topic-assignment results per sentence.

    Each record maps one sentence analysis (analysis_id = sent_id) to its
    BERTopic topic, probability distribution, and c-TF-IDF keywords.

    Concrete implementation: TopicAssignmentRepository (infrastructure layer).

    References:
        - Community 924: TopicAssignmentORM / TopicAssignment types.
        - GAT design (TASK-E02): concept node features derived from
          TopicAssignment objects; build_pyg_data must use this port.
    """

    async def upsert(
        self,
        segment_id: str,
        analysis_id: str,
        synthesis: TopicSynthesis,
        model_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update a topic-assignment record.

        Args:
            segment_id:      ORM segment primary key (format: "seg_{file_id}_{n}").
            analysis_id:     Sentence sent_id used as the unique lookup key.
            synthesis:       TopicSynthesis value object from BERTopic output.
            model_metadata:  SBERT model name, UMAP/HDBSCAN params, etc.
        """
        ...

    async def get_by_analysis_id(self, analysis_id: str) -> dict[str, Any] | None:
        """Return raw field dict for a given analysis_id, or None if absent."""
        ...

    async def delete_by_segment_prefix(self, file_id: str) -> int:
        """Delete all assignments for segments belonging to file_id.

        Matches segment_id LIKE 'seg_{file_id}_%'.

        Returns:
            Number of rows deleted.
        """
        ...
