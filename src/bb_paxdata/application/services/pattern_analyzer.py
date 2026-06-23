"""Pattern Analyzer service for detecting systematic errors in corrections."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

import structlog

from bb_paxdata.application.domain.models.correction_event import CorrectionEvent
from bb_paxdata.infrastructure.db.repositories.correction_event_repository import (
    CorrectionEventRepository,
)

logger = structlog.get_logger(__name__)


class PatternReport:
    """Report containing pattern analysis results."""

    def __init__(
        self,
        analysis_timestamp: datetime,
        total_events_analyzed: int,
        systematic_errors: list[dict[str, Any]],
        threshold_anomalies: list[dict[str, Any]],
        prompt_regressions: list[dict[str, Any]],
        field_distributions: dict[str, Any],
    ):
        self.analysis_timestamp = analysis_timestamp
        self.total_events_analyzed = total_events_analyzed
        self.systematic_errors = systematic_errors
        self.threshold_anomalies = threshold_anomalies
        self.prompt_regressions = prompt_regressions
        self.field_distributions = field_distributions

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "total_events_analyzed": self.total_events_analyzed,
            "systematic_errors": self.systematic_errors,
            "threshold_anomalies": self.threshold_anomalies,
            "prompt_regressions": self.prompt_regressions,
            "field_distributions": self.field_distributions,
        }


class PatternAnalyzer:
    """
    Analyzes correction events to detect systematic error patterns.

    Performs:
    - Batch analysis of recent N correction events
    - Field-based correction delta distribution
    - Prompt version comparison
    - Systematic error detection
    - Threshold anomaly detection
    - Prompt regression detection
    """

    def __init__(self, repository: CorrectionEventRepository) -> None:
        self._repository = repository

    async def analyze_recent_events(self, limit: int = 1000) -> PatternReport:
        """
        Perform batch analysis on the most recent correction events.

        Args:
            limit: Number of recent events to analyze (default: 1000)

        Returns:
            PatternReport with detected patterns and anomalies
        """
        logger.info("pattern_analysis_started", limit=limit)

        events = await self._repository.get_recent(limit=limit)

        if not events:
            logger.warning("pattern_analysis_no_events")
            return PatternReport(
                analysis_timestamp=datetime.utcnow(),
                total_events_analyzed=0,
                systematic_errors=[],
                threshold_anomalies=[],
                prompt_regressions=[],
                field_distributions={},
            )

        # Analyze field distributions
        field_distributions = await self._analyze_field_distribution(events)

        # Detect systematic errors
        systematic_errors = await self._detect_systematic_errors(events)

        # Detect threshold anomalies
        threshold_anomalies = await self._detect_threshold_anomalies(events)

        # Detect prompt regressions
        prompt_regressions = await self._detect_prompt_regressions(events)

        report = PatternReport(
            analysis_timestamp=datetime.utcnow(),
            total_events_analyzed=len(events),
            systematic_errors=systematic_errors,
            threshold_anomalies=threshold_anomalies,
            prompt_regressions=prompt_regressions,
            field_distributions=field_distributions,
        )

        logger.info(
            "pattern_analysis_completed",
            total_events=len(events),
            systematic_errors=len(systematic_errors),
            threshold_anomalies=len(threshold_anomalies),
            prompt_regressions=len(prompt_regressions),
        )

        return report

    async def _analyze_field_distribution(
        self, events: list[CorrectionEvent]
    ) -> dict[str, Any]:
        """
        Analyze correction distribution by field.

        Returns statistics about which fields are being corrected most frequently.
        """
        field_counts = Counter(event.field_corrected for event in events)

        # Calculate correction rate per field
        field_stats = {}
        for field, count in field_counts.items():
            field_events = [e for e in events if e.field_corrected == field]
            avg_confidence = sum(e.ai_confidence for e in field_events) / len(
                field_events
            )
            high_conf_errors = sum(
                1 for e in field_events if e.is_high_confidence_error()
            )

            field_stats[field] = {
                "correction_count": count,
                "average_confidence": avg_confidence,
                "high_confidence_errors": high_conf_errors,
                "high_confidence_error_rate": high_conf_errors / len(field_events),
            }

        return {
            "field_counts": dict(field_counts),
            "field_stats": field_stats,
        }

    async def _detect_systematic_errors(
        self, events: list[CorrectionEvent]
    ) -> list[dict[str, Any]]:
        """
        Detect systematic error patterns.

        Examples:
        - "topic=X olan cumlelerde risk_score dusuk"
        - "speaker=Y tarafindan frame hatalari sik"
        """
        systematic_errors = []

        # Group by field to find patterns
        field_groups: dict[str, list[CorrectionEvent]] = {}
        for event in events:
            if event.field_corrected not in field_groups:
                field_groups[event.field_corrected] = []
            field_groups[event.field_corrected].append(event)

        # Analyze each field for patterns
        for field, field_events in field_groups.items():
            # Check if high confidence errors are concentrated
            high_conf_events = [e for e in field_events if e.is_high_confidence_error()]
            if len(high_conf_events) > len(field_events) * 0.3:
                systematic_errors.append(
                    {
                        "type": "high_confidence_concentration",
                        "field": field,
                        "description": f"{len(high_conf_events)} high-confidence errors in {field} ({len(high_conf_events)/len(field_events)*100:.1f}%)",
                        "severity": (
                            "high"
                            if len(high_conf_events) / len(field_events) > 0.5
                            else "medium"
                        ),
                        "affected_count": len(high_conf_events),
                    }
                )

            # Check context patterns if available
            events_with_context = [e for e in field_events if e.context_snapshot]
            if events_with_context:
                # Look for common context attributes
                context_patterns = self._analyze_context_patterns(events_with_context)
                for pattern in context_patterns:
                    systematic_errors.append(
                        {
                            "type": "context_pattern",
                            "field": field,
                            "description": pattern["description"],
                            "severity": pattern["severity"],
                            "affected_count": pattern["count"],
                        }
                    )

        return systematic_errors

    def _analyze_context_patterns(
        self, events: list[CorrectionEvent]
    ) -> list[dict[str, Any]]:
        """
        Analyze context snapshots for common patterns.

        Looks for recurring context attributes that correlate with corrections.
        """
        patterns = []

        # Extract context attributes
        context_attrs: dict[str, list[Any]] = {}
        for event in events:
            if event.context_snapshot:
                for key, value in event.context_snapshot.items():
                    if key not in context_attrs:
                        context_attrs[key] = []
                    context_attrs[key].append(value)

        # Find patterns (simplified - in production would use more sophisticated analysis)
        for attr, values in context_attrs.items():
            if len(values) > 5:  # Only consider attributes with enough data
                value_counts = Counter(str(v) for v in values)
                most_common = value_counts.most_common(1)

                if most_common:
                    common_value, count = most_common[0]
                    if count / len(values) > 0.4:  # >40% concentration
                        patterns.append(
                            {
                                "description": f"Context attribute '{attr}'='{common_value}' correlates with corrections ({count}/{len(values)} events)",
                                "severity": "medium",
                                "count": count,
                            }
                        )

        return patterns

    async def _detect_threshold_anomalies(
        self, events: list[CorrectionEvent]
    ) -> list[dict[str, Any]]:
        """
        Detect threshold anomalies.

        Examples:
        - "confidence 0.72 ama correction rate %38"
        - "risk_score > 0.8 iken correction rate yuksek"
        """
        anomalies = []

        # Analyze confidence vs correction patterns
        confidence_buckets: dict[str, tuple[int, int]] = (
            {}
        )  # (range) -> (total, corrections)
        for event in events:
            conf = event.ai_confidence
            bucket = self._get_confidence_bucket(conf)
            if bucket not in confidence_buckets:
                confidence_buckets[bucket] = (0, 0)
            total, corrections = confidence_buckets[bucket]
            confidence_buckets[bucket] = (total + 1, corrections + 1)

        # Check for anomalies in confidence buckets
        for bucket, (total, corrections) in confidence_buckets.items():
            if total > 10:  # Only analyze buckets with sufficient data
                correction_rate = corrections / total
                # High correction rate in high confidence bucket is anomalous
                if "0.7-0.9" in bucket or "0.9-1.0" in bucket:
                    if correction_rate > 0.3:  # >30% correction rate in high confidence
                        anomalies.append(
                            {
                                "type": "confidence_anomaly",
                                "description": f"Confidence bucket {bucket} has {correction_rate*100:.1f}% correction rate (expected <10%)",
                                "severity": "high",
                                "bucket": bucket,
                                "correction_rate": correction_rate,
                                "total_events": total,
                            }
                        )

        return anomalies

    def _get_confidence_bucket(self, confidence: float) -> str:
        """Bucket confidence values into ranges."""
        if confidence < 0.3:
            return "0.0-0.3"
        elif confidence < 0.5:
            return "0.3-0.5"
        elif confidence < 0.7:
            return "0.5-0.7"
        elif confidence < 0.9:
            return "0.7-0.9"
        else:
            return "0.9-1.0"

    async def _detect_prompt_regressions(
        self, events: list[CorrectionEvent]
    ) -> list[dict[str, Any]]:
        """
        Detect prompt version regressions.

        Examples:
        - "v2.1'de hedging %42 correction, v2.0'da %18"
        """
        regressions = []

        # Group by prompt version
        version_groups: dict[str, list[CorrectionEvent]] = {}
        for event in events:
            if event.prompt_version not in version_groups:
                version_groups[event.prompt_version] = []
            version_groups[event.prompt_version].append(event)

        # Compare versions
        versions = sorted(version_groups.keys())
        if len(versions) >= 2:
            for i in range(len(versions) - 1):
                v1 = versions[i]
                v2 = versions[i + 1]

                v1_events = version_groups[v1]
                v2_events = version_groups[v2]

                # Compare correction rates by field
                v1_field_counts = Counter(e.field_corrected for e in v1_events)
                v2_field_counts = Counter(e.field_corrected for e in v2_events)

                for field in set(v1_field_counts.keys()) | set(v2_field_counts.keys()):
                    v1_count = v1_field_counts.get(field, 0)
                    v2_count = v2_field_counts.get(field, 0)

                    if v1_count > 0 and v2_count > 0:
                        v1_rate = v1_count / len(v1_events)
                        v2_rate = v2_count / len(v2_events)

                        # Check for regression (significant increase in correction rate)
                        if v2_rate > v1_rate * 1.5:  # >50% increase
                            regressions.append(
                                {
                                    "type": "prompt_regression",
                                    "field": field,
                                    "old_version": v1,
                                    "new_version": v2,
                                    "old_rate": v1_rate,
                                    "new_rate": v2_rate,
                                    "percent_increase": (v2_rate - v1_rate)
                                    / v1_rate
                                    * 100,
                                    "description": f"{field} correction rate increased from {v1_rate*100:.1f}% in {v1} to {v2_rate*100:.1f}% in {v2}",
                                    "severity": (
                                        "high" if v2_rate > v1_rate * 2 else "medium"
                                    ),
                                }
                            )

        return regressions
