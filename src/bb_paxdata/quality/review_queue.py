"""Human review queue management for HIGH/CRITICAL risk sentences."""

import json
from datetime import datetime, timedelta
from typing import Any, Literal, cast

import structlog
from sqlalchemy.orm import Session

from ..infrastructure.db.human_review_queue import HumanReviewQueue
from ..infrastructure.db.models import AISentenceAnalysis

logger = structlog.get_logger(__name__)


class ReviewFlagger:
    """Flags sentences for human review based on quality criteria."""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = structlog.get_logger(__name__)

    def should_flag_for_review(
        self,
        ai_output: dict[str, Any],
        uncertainty_score: float | None = None,
        quality_result: Any | None = None,
    ) -> tuple[bool, str, Any]:
        """
        Determine if a sentence should be flagged for human review.

        Args:
            ai_output: AI analysis output
            uncertainty_score: Uncertainty score from UncertaintyScorer
            quality_result: Quality evaluation result

        Returns:
            Tuple of (should_flag, trigger_type, trigger_details)
        """
        triggers = []

        # Check 1: High risk score
        risk_score = ai_output.get("AI_Risk_Skoru")
        if risk_score is not None and risk_score >= 7:
            triggers.append(
                {"type": "HIGH_RISK", "details": f"Risk score {risk_score} >= 7"}
            )

        # Check 2: Critical potential risk
        potential_risk = ai_output.get("AI_Potansiyel_Risk")
        if potential_risk in ["high", "critical"]:
            triggers.append(
                {
                    "type": "CRITICAL_RISK",
                    "details": f"Potential risk level: {potential_risk}",
                }
            )

        # Check 3: Low uncertainty
        if uncertainty_score is not None and uncertainty_score < 0.50:
            triggers.append(
                {
                    "type": "LOW_UNCERTAINTY",
                    "details": f"Uncertainty score {uncertainty_score:.3f} < 0.50",
                }
            )

        # Check 4: Quality evaluation failure
        if quality_result is not None and not quality_result.passed:
            triggers.append(
                {
                    "type": "QUALITY_FAILURE",
                    "details": (
                        f"Quality evaluation failed "
                        f"(score: {quality_result.overall_score:.3f})"
                    ),
                }
            )

        # Check 5: Cross-anomaly severity (placeholder)
        anomaly_types = ai_output.get("anomaly_types")
        if anomaly_types and any(
            sev in ["HIGH", "CRITICAL"] for sev in str(anomaly_types).split(",")
        ):
            triggers.append(
                {
                    "type": "CRITICAL_ANOMALY",
                    "details": f"Critical anomaly detected: {anomaly_types}",
                }
            )

        # Return highest priority trigger
        if triggers:
            # Priority order:
            # CRITICAL_RISK > CRITICAL_ANOMALY > HIGH_RISK >
            # QUALITY_FAILURE > LOW_UNCERTAINTY
            priority_order = [
                "CRITICAL_RISK",
                "CRITICAL_ANOMALY",
                "HIGH_RISK",
                "QUALITY_FAILURE",
                "LOW_UNCERTAINTY",
            ]

            for priority_type in priority_order:
                for trigger in triggers:
                    if trigger["type"] == priority_type:
                        return (
                            True,
                            trigger["type"],
                            cast(dict[str, Any], trigger["details"]),
                        )

            # Fallback to first trigger
            return (
                True,
                triggers[0]["type"],
                cast(dict[str, Any], triggers[0]["details"]),
            )

        return False, "", ""

    def flag_sentence(
        self,
        sent_id: str,
        ai_output: dict[str, Any],
        trigger_type: str,
        trigger_details: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> HumanReviewQueue | None:
        """
        Flag a sentence for human review.

        Args:
            sent_id: Sentence ID
            ai_output: AI analysis output
            trigger_type: Type of trigger
            trigger_details: Details about the trigger
            context: Additional context (speaker, panel, etc.)

        Returns:
            HumanReviewQueue object or None if failed
        """
        try:
            # Check if already flagged
            existing = (
                self.db_session.query(HumanReviewQueue)
                .filter(
                    HumanReviewQueue.sent_id == sent_id,
                    HumanReviewQueue.status.in_(["PENDING", "ASSIGNED", "IN_REVIEW"]),
                )
                .first()
            )

            if existing:
                self.logger.info(f"Sentence {sent_id} already in review queue")
                return existing

            # Create new review entry
            review_entry = HumanReviewQueue(
                sent_id=sent_id,
                seg_id=context.get("seg_id") if context else None,
                panel_id=context.get("panel_id") if context else None,
                speaker_name=context.get("speaker_name") if context else None,
                country=context.get("country") if context else None,
                trigger_type=trigger_type,
                ai_risk_score=ai_output.get("AI_Risk_Skoru"),
                anomaly_types=ai_output.get("anomaly_types"),
                uncertainty_score=trigger_details.get("uncertainty_score"),
                status="PENDING",
                original_ai_json=json.dumps(ai_output, ensure_ascii=False),
            )

            self.db_session.add(review_entry)
            self.db_session.commit()

            self.logger.info(
                f"Flagged sentence {sent_id} for review",
                trigger_type=trigger_type,
                review_id=review_entry.review_id,
            )

            return review_entry

        except Exception as e:
            self.logger.error(f"Error flagging sentence {sent_id}: {e}")
            self.db_session.rollback()
            return None


class ReviewQueueManager:
    """Manages the human review queue workflow."""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = structlog.get_logger(__name__)

    def get_pending_reviews(
        self, limit: int = 50, panel_id: str | None = None
    ) -> list[HumanReviewQueue]:
        """Get pending reviews for human processing."""
        query = (
            self.db_session.query(HumanReviewQueue)
            .filter(HumanReviewQueue.status == "PENDING")
            .order_by(HumanReviewQueue.flagged_at.desc())
        )

        if panel_id:
            query = query.filter(HumanReviewQueue.panel_id == panel_id)

        return query.limit(limit).all()

    def get_review_by_id(self, review_id: int) -> HumanReviewQueue | None:
        """Get review entry by ID."""
        return (
            self.db_session.query(HumanReviewQueue)
            .filter(HumanReviewQueue.review_id == review_id)
            .first()
        )

    def assign_review(self, review_id: int, assigned_to: str) -> bool:
        """Assign a review to a human reviewer."""
        try:
            review = self.get_review_by_id(review_id)
            if not review:
                return False

            review.status = "ASSIGNED"
            review.assigned_to = assigned_to
            self.db_session.commit()

            self.logger.info(f"Assigned review {review_id} to {assigned_to}")
            return True

        except Exception as e:
            self.logger.error(f"Error assigning review {review_id}: {e}")
            self.db_session.rollback()
            return False

    def start_review(self, review_id: int) -> bool:
        """Mark review as in progress."""
        try:
            review = self.get_review_by_id(review_id)
            if not review:
                return False

            review.status = "IN_REVIEW"
            self.db_session.commit()

            self.logger.info(f"Started review {review_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error starting review {review_id}: {e}")
            self.db_session.rollback()
            return False

    def complete_review(
        self,
        review_id: int,
        action: Literal["APPROVED", "REJECTED", "MODIFIED"],
        reviewer_notes: str | None = None,
        corrected_json: str | None = None,
    ) -> bool:
        """Complete a review with final action."""
        try:
            review = self.get_review_by_id(review_id)
            if not review:
                return False

            # Calculate review duration
            if review.flagged_at:
                flagged_time = datetime.fromisoformat(
                    review.flagged_at.replace("Z", "+00:00")
                )
                review_duration = int(
                    (datetime.utcnow() - flagged_time).total_seconds()
                )
                review.review_duration_sec = review_duration

            review.status = action
            review.reviewed_at = datetime.utcnow().isoformat()
            review.reviewer_notes = reviewer_notes

            if action == "MODIFIED" and corrected_json:
                review.corrected_json = corrected_json

            self.db_session.commit()

            self.logger.info(
                f"Completed review {review_id} with action {action}",
                duration=review.review_duration_sec,
            )

            # If approved or modified, update the original AI analysis
            if action in ["APPROVED", "MODIFIED"]:
                self._update_ai_analysis(review, action)

            return True

        except Exception as e:
            self.logger.error(f"Error completing review {review_id}: {e}")
            self.db_session.rollback()
            return False

    def _update_ai_analysis(self, review: HumanReviewQueue, action: str) -> None:
        """Update AI analysis based on review outcome."""
        try:
            ai_analysis = (
                self.db_session.query(AISentenceAnalysis)
                .filter(AISentenceAnalysis.sent_id == review.sent_id)
                .first()
            )

            if not ai_analysis:
                return

            if action == "MODIFIED" and review.corrected_json:
                # Update with corrected values
                corrected_data = json.loads(review.corrected_json)

                # Update relevant fields
                for field in [
                    "AI_Duygu_Skoru",
                    "AI_Risk_Skoru",
                    "AI_Potansiyel_Risk",
                    "AI_Diplomatik_Ton",
                    "AI_Manipulasyon_Skoru",
                    "AI_Talep_Var",
                ]:
                    if field in corrected_data:
                        setattr(ai_analysis, field, corrected_data[field])

                self.logger.info(
                    f"Updated AI analysis for {review.sent_id} with corrected values"
                )

            # Mark as human-reviewed
            if hasattr(ai_analysis, "human_reviewed"):
                ai_analysis.human_reviewed = 1
            if hasattr(ai_analysis, "human_review_status"):
                ai_analysis.human_review_status = action

            self.db_session.commit()

        except Exception as e:
            self.logger.error(f"Error updating AI analysis for {review.sent_id}: {e}")

    def get_queue_statistics(self) -> dict[str, Any]:
        """Get statistics about the review queue."""
        try:
            stats: dict[str, Any] = {}

            # Count by status
            for status in [
                "PENDING",
                "ASSIGNED",
                "IN_REVIEW",
                "APPROVED",
                "REJECTED",
                "MODIFIED",
                "ESCALATED",
            ]:
                count = (
                    self.db_session.query(HumanReviewQueue)
                    .filter(HumanReviewQueue.status == status)
                    .count()
                )
                stats[f"count_{status.lower()}"] = count

            # Count by trigger type
            trigger_counts = {}
            for trigger_type in [
                "HIGH_RISK",
                "CRITICAL_ANOMALY",
                "LOW_UNCERTAINTY",
                "QUALITY_FAILURE",
                "MANUAL_FLAG",
            ]:
                count = (
                    self.db_session.query(HumanReviewQueue)
                    .filter(HumanReviewQueue.trigger_type == trigger_type)
                    .count()
                )
                trigger_counts[trigger_type] = count

            stats["trigger_counts"] = trigger_counts

            # Average review time
            completed_reviews = (
                self.db_session.query(HumanReviewQueue)
                .filter(
                    HumanReviewQueue.review_duration_sec.isnot(None),
                    HumanReviewQueue.status.in_(["APPROVED", "REJECTED", "MODIFIED"]),
                )
                .all()
            )

            if completed_reviews:
                avg_duration = sum(
                    float(r.review_duration_sec or 0) for r in completed_reviews
                ) / len(completed_reviews)
                stats["avg_review_duration_sec"] = int(avg_duration)
            else:
                stats["avg_review_duration_sec"] = 0

            # Escalated reviews (older than 72 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=72)
            escalated_count = (
                self.db_session.query(HumanReviewQueue)
                .filter(
                    HumanReviewQueue.status.in_(["PENDING", "ASSIGNED", "IN_REVIEW"]),
                    HumanReviewQueue.flagged_at < cutoff_time.isoformat(),
                )
                .count()
            )

            stats["escalated_count"] = escalated_count

            return stats

        except Exception as e:
            self.logger.error(f"Error getting queue statistics: {e}")
            return {}

    def escalate_stale_reviews(self) -> int:
        """Escalate reviews older than 72 hours."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=72)

            stale_reviews = (
                self.db_session.query(HumanReviewQueue)
                .filter(
                    HumanReviewQueue.status.in_(["PENDING", "ASSIGNED", "IN_REVIEW"]),
                    HumanReviewQueue.flagged_at < cutoff_time.isoformat(),
                )
                .all()
            )

            escalated_count = 0
            for review in stale_reviews:
                review.status = "ESCALATED"
                escalated_count += 1

            self.db_session.commit()

            self.logger.info(f"Escalated {escalated_count} stale reviews")
            return escalated_count

        except Exception as e:
            self.logger.error(f"Error escalating stale reviews: {e}")
            self.db_session.rollback()
            return 0
