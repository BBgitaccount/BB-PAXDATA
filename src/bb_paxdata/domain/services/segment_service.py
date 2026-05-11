"""Segment analysis service for aggregating sentence results.

This service coordinates the aggregation of sentence-level analysis results
into segment-level metrics, including SBI, DKI, trajectory, and mode logic.
Mirrors DatabaseBuilder_v5_8.py segment enrichment logic.
"""

from collections import Counter
from typing import Any

from ...application.protocols import BaseService, RiskServiceProtocol
from ..models.segment import Segment
from ..models.sentence import Sentence


class SegmentService(BaseService):
    """Service for segment-level analysis and aggregation."""

    def __init__(self, risk_service: RiskServiceProtocol) -> None:
        """Initialize segment service.

        Args:
            risk_service: Risk assessment service
        """
        super().__init__()
        self.risk_service = risk_service

    def analyze(self, segment: Segment, **kwargs: Any) -> Any:
        """Satisfy BaseService requirement."""
        sentences = kwargs.get("sentences", [])
        return self.enrich_segment(segment, sentences)

    def enrich_segment(self, segment: Segment, sentences: list[Sentence]) -> Segment:
        """Enrich segment with aggregated sentence metrics.

        Args:
            segment: Segment to enrich
            sentences: List of sentences belonging to the segment

        Returns:
            Enriched segment
        """
        if not sentences:
            return segment

        # 1. SBI & DKI Aggregation (Delegated to RiskService)
        risk_assessment = self.risk_service.assess_risk(segment, sentences=sentences)
        segment.sbi_score = risk_assessment.sbi_score
        segment.dki_score = risk_assessment.dki_score
        segment.risk_score = int(risk_assessment.risk_score)
        segment.risk_signals = risk_assessment.risk_signals

        # 2. Mode Logic for Categorical Fields
        segment.dominant_frame = self._get_mode(
            [s.dominant_frame for s in sentences if s.dominant_frame]
        )
        segment.dominant_audience = self._get_mode(
            [s.audience_type for s in sentences if s.audience_type]
        )

        # evidence_types is a list in Sentence, pick first for aggregation
        flat_evidence = []
        for s in sentences:
            if s.evidence_types:
                flat_evidence.extend(s.evidence_types)
        segment.dominant_evidence = self._get_mode(flat_evidence)

        segment.dominant_topic = self._get_mode(
            [s.dominant_topic for s in sentences if s.dominant_topic]
        )

        # sentiment maps to emotion_category
        emotions = [
            s.sentiment.value if hasattr(s.sentiment, "value") else str(s.sentiment)
            for s in sentences
            if s.sentiment
        ]
        segment.emotion_category = self._get_mode(emotions)

        # 3. Numeric Averages
        segment.vader_compound = sum(s.sentiment_score or 0.0 for s in sentences) / len(
            sentences
        )
        segment.avg_hedging_score = sum(
            s.hedging_score or 0.0 for s in sentences
        ) / len(sentences)
        segment.formula_manip_score = sum(
            s.manipulation_score or 0.0 for s in sentences
        ) / len(sentences)

        # 4. Risk Trajectory
        segment.risk_trajectory = self._calculate_risk_trajectory(sentences)

        # 5. Demand Concentration (Intro/Develop/Concl)
        segment.demand_concentration = self._calculate_demand_concentration(sentences)
        segment.demand_count = sum(1 for s in sentences if s.is_demand)

        return segment

    def _get_mode(self, items: list[Any]) -> Any | None:
        """Calculate the mode (most frequent item) of a list."""
        if not items:
            return None
        return Counter(items).most_common(1)[0][0]

    def _calculate_risk_trajectory(self, sentences: list[Sentence]) -> str:
        """Calculate risk trajectory across sentences.

        Logic:
        - Compare first 25% avg risk vs last 25% avg risk.
        - Difference > 1.5 -> ESCALATING
        - Difference < -1.5 -> DE-ESCALATING
        - Else -> STABLE
        """
        if len(sentences) < 3:
            return "STABLE"

        n = len(sentences)
        idx_25 = max(1, n // 4)

        start_risk = sum(s.risk_score or 0.0 for s in sentences[:idx_25]) / idx_25
        end_risk = sum(s.risk_score or 0.0 for s in sentences[-idx_25:]) / idx_25

        diff = end_risk - start_risk
        if diff > 1.5:
            return "ESCALATING"
        elif diff < -1.5:
            return "DE-ESCALATING"
        return "STABLE"

    def _calculate_demand_concentration(
        self, sentences: list[Sentence]
    ) -> dict[str, int]:
        """Calculate demand distribution across segment sections.

        Sections:
        - Intro: First 20%
        - Develop: Middle 60%
        - Conclusion: Last 20%
        """
        n = len(sentences)
        if n == 0:
            return {"intro": 0, "develop": 0, "concl": 0}

        intro_end = max(1, n // 5)
        concl_start = max(n - intro_end, intro_end + 1)

        intro_demands = sum(1 for s in sentences[:intro_end] if s.is_demand)
        concl_demands = sum(1 for s in sentences[concl_start:] if s.is_demand)
        develop_demands = sum(
            1 for s in sentences[intro_end:concl_start] if s.is_demand
        )

        return {
            "intro": intro_demands,
            "develop": develop_demands,
            "concl": concl_demands,
        }
