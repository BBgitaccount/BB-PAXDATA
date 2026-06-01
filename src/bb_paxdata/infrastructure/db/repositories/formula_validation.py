from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, case, func, select, update

from bb_paxdata.infrastructure.db.human_review_queue import HumanReviewQueue
from bb_paxdata.infrastructure.db.models import (
    AISentenceAnalysis,
    FormulaValidationAudit,
    FormulaValidationLog,
    Sentence,
)
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository

# Priority formula weights
_FORMULA_WEIGHT = {
    "risk_score": 2.0,
    "emotion_category_alignment": 2.0,
    "sbi_score": 1.5,
    "dki_score": 1.5,
    "vader_compound": 1.0,
    "negation_aware_diplo": 1.0,
    "hedging_score": 1.0,
    "politeness_ratio": 1.0,
}


class FormulaValidationRepository(BaseRepository[FormulaValidationLog]):
    """Async repository for FormulaValidationLog ORM model with HITL support."""

    model_class = FormulaValidationLog

    # ── Existing methods (unchanged) ─────────────────────────────────

    async def get_by_run(self, run_id: str) -> list[FormulaValidationLog]:
        """Get all formula validation logs for a specific run."""
        stmt = select(FormulaValidationLog).where(FormulaValidationLog.run_id == run_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_failed_logs(
        self, limit: int | None = None
    ) -> list[FormulaValidationLog]:
        """Get all failed validation logs."""
        stmt = select(FormulaValidationLog).where(FormulaValidationLog.status == "FAIL")
        if limit:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_run_summary(self, run_id: str) -> dict[str, Any]:
        """Get a summary of PASS/FAIL counts grouped by formula name for a run."""
        stmt = (
            select(
                FormulaValidationLog.formula_name,
                FormulaValidationLog.status,
                func.count(FormulaValidationLog.log_id),
            )
            .where(FormulaValidationLog.run_id == run_id)
            .group_by(FormulaValidationLog.formula_name, FormulaValidationLog.status)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        summary: dict[str, dict[str, int]] = {}
        total_pass = 0
        total_fail = 0

        for formula, status, count in rows:
            summary.setdefault(formula, {"PASS": 0, "FAIL": 0})
            summary[formula][status] = count
            if status == "PASS":
                total_pass += count
            else:
                total_fail += count

        total = total_pass + total_fail
        pass_ratio = total_pass / total if total > 0 else 1.0

        return {
            "run_id": run_id,
            "metrics": summary,
            "total_count": total,
            "pass_count": total_pass,
            "fail_count": total_fail,
            "accuracy_percentage": round(pass_ratio * 100, 2),
        }

    async def get_overall_summary(self) -> dict[str, Any]:
        """Get a global summary of PASS/FAIL counts grouped by formula name."""
        stmt = select(
            FormulaValidationLog.formula_name,
            FormulaValidationLog.status,
            func.count(FormulaValidationLog.log_id),
        ).group_by(FormulaValidationLog.formula_name, FormulaValidationLog.status)
        result = await self._session.execute(stmt)
        rows = result.all()

        summary: dict[str, dict[str, int]] = {}
        total_pass = 0
        total_fail = 0

        for formula, status, count in rows:
            summary.setdefault(formula, {"PASS": 0, "FAIL": 0})
            summary[formula][status] = count
            if status == "PASS":
                total_pass += count
            else:
                total_fail += count

        total = total_pass + total_fail
        pass_ratio = total_pass / total if total > 0 else 1.0

        return {
            "metrics": summary,
            "total_count": total,
            "pass_count": total_pass,
            "fail_count": total_fail,
            "accuracy_percentage": round(pass_ratio * 100, 2),
        }

    # ── HITL Methods (v2) ────────────────────────────────────────────

    async def get_fail_queue_with_context(
        self,
        *,
        formula_name: str | None = None,
        panel_id: str | None = None,
        status_filter: str = "unreviewed",  # unreviewed | reviewed | all
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get FAIL queue with full sentence context, AI analysis, and speaker info.

        Returns enriched records suitable for the HITL dashboard.
        """
        # Build base query with JOINs
        stmt = (
            select(
                FormulaValidationLog,
                Sentence.text.label("sentence_text"),
                Sentence.sent_id,
                Sentence.seg_id,
                Sentence.file_id,
                Sentence.speaker_name,
                Sentence.country,
                Sentence.power_level,
                Sentence.sent_order,
                # AI analysis fields (nullable via outerjoin)
                AISentenceAnalysis.risk_score.label("ai_risk_score"),
                AISentenceAnalysis.ai_emotion.label("ai_emotion_category"),
                AISentenceAnalysis.diplomatic_tone.label("ai_diplomatic_tone"),
                # Human review queue (nullable via outerjoin)
                HumanReviewQueue.review_id,
                HumanReviewQueue.status.label("review_status"),
                HumanReviewQueue.trigger_type,
            )
            .outerjoin(
                Sentence,
                and_(
                    FormulaValidationLog.entity_id == Sentence.sent_id,
                    FormulaValidationLog.entity_type == "sentence",
                ),
            )
            .outerjoin(
                AISentenceAnalysis,
                Sentence.sent_id == AISentenceAnalysis.sent_id,
            )
            .outerjoin(
                HumanReviewQueue,
                Sentence.sent_id == HumanReviewQueue.sent_id,
            )
            .where(
                FormulaValidationLog.status == "FAIL",
                FormulaValidationLog.is_current == True,  # noqa: E712
            )
        )

        # Apply filters
        if formula_name:
            stmt = stmt.where(FormulaValidationLog.formula_name == formula_name)
        if panel_id:
            stmt = stmt.where(Sentence.file_id == panel_id)
        if status_filter == "unreviewed":
            stmt = stmt.where(FormulaValidationLog.human_verdict.is_(None))
        elif status_filter == "reviewed":
            stmt = stmt.where(FormulaValidationLog.human_verdict.isnot(None))

        stmt = stmt.order_by(FormulaValidationLog.created_at.desc()).limit(limit)

        result = await self._session.execute(stmt)
        rows = result.all()

        items: list[dict[str, Any]] = []
        for row in rows:
            log: FormulaValidationLog = row[0]
            has_review = row.review_id is not None
            power = row.power_level or 0

            # Calculate priority score
            formula_weight = _FORMULA_WEIGHT.get(log.formula_name, 1.0)
            priority_score = (
                formula_weight * 3.0
                + (5.0 if has_review else 0.0)
                + (power / 10.0) * 2.0
            )

            items.append(
                {
                    "log_id": log.log_id,
                    "run_id": log.run_id,
                    "formula_name": log.formula_name,
                    "status": log.status,
                    "actual_value": log.actual_value,
                    "expected_constraint": log.expected_constraint,
                    "details": log.details,
                    "human_verdict": log.human_verdict,
                    "human_note": log.human_note,
                    "log_version": log.log_version,
                    "reviewer_id": log.reviewer_id,
                    # Sentence context
                    "sentence_text": row.sentence_text,
                    "sent_id": row.sent_id,
                    "seg_id": row.seg_id,
                    "file_id": row.file_id,
                    "speaker_name": row.speaker_name,
                    "country": row.country,
                    "power_level": power,
                    # AI analysis
                    "ai_risk_score": row.ai_risk_score,
                    "ai_emotion_category": row.ai_emotion_category,
                    "ai_diplomatic_tone": row.ai_diplomatic_tone,
                    # Review queue
                    "review_id": row.review_id,
                    "review_status": row.review_status,
                    "trigger_type": row.trigger_type,
                    # Calculated
                    "priority_score": round(priority_score, 2),
                    "created_at": (
                        log.created_at.isoformat() if log.created_at else None
                    ),
                }
            )

        # Sort by priority descending
        items.sort(key=lambda x: x["priority_score"], reverse=True)
        return items

    async def get_triplet_context(self, sent_id: str) -> dict[str, str | None]:
        """Get previous, current, and next sentence text for a given sent_id."""
        # Get current sentence with order info
        current_stmt = select(Sentence).where(Sentence.sent_id == sent_id)
        current_result = await self._session.execute(current_stmt)
        current = current_result.scalar_one_or_none()

        if not current:
            return {"prev": None, "current": None, "next": None}

        result: dict[str, str | None] = {
            "prev": None,
            "current": current.text,
            "next": None,
        }

        if current.sent_order is not None:
            # Get previous sentence
            prev_stmt = (
                select(Sentence.text)
                .where(
                    Sentence.seg_id == current.seg_id,
                    Sentence.sent_order == current.sent_order - 1,
                )
                .limit(1)
            )
            prev_result = await self._session.execute(prev_stmt)
            prev_text = prev_result.scalar_one_or_none()
            result["prev"] = prev_text

            # Get next sentence
            next_stmt = (
                select(Sentence.text)
                .where(
                    Sentence.seg_id == current.seg_id,
                    Sentence.sent_order == current.sent_order + 1,
                )
                .limit(1)
            )
            next_result = await self._session.execute(next_stmt)
            next_text = next_result.scalar_one_or_none()
            result["next"] = next_text

        return result

    async def start_review(
        self,
        log_id: int,
        reviewer_id: str,
    ) -> FormulaValidationLog:
        """Optimistic lock: assign a reviewer to a log entry.

        Raises ValueError if the log is already being reviewed.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(FormulaValidationLog)
            .where(
                FormulaValidationLog.log_id == log_id,
                FormulaValidationLog.reviewer_id.is_(None),
                FormulaValidationLog.is_current == True,  # noqa: E712
            )
            .values(reviewer_id=reviewer_id, locked_at=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        res_any: Any = result

        if res_any.rowcount == 0:
            raise ValueError(
                f"Log {log_id} is already in review by another reviewer or not current"
            )

        # Create audit entry
        audit = FormulaValidationAudit(
            log_id=log_id,
            action_type="REVIEW_STARTED",
            performed_by=reviewer_id,
            performed_at=now,
        )
        self._session.add(audit)
        await self._session.flush()

        # Return the updated log
        log = await self.get_by_id(log_id)
        if log is None:
            raise ValueError(f"Log {log_id} not found after update")
        return log

    async def submit_verdict_atomic(
        self,
        *,
        log_id: int,
        verdict: str,
        corrected_value: float | None = None,
        note: str | None = None,
        confidence: str | None = None,
        justification: str | None = None,
        reviewer_id: str,
        reviewer_role: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Submit a HITL verdict atomically with versioning and audit trail.

        1. Mark current log as superseded (is_current=False)
        2. Create new log version with verdict
        3. Create audit entry
        4. Sync HumanReviewQueue if applicable

        Returns dict with new_log_id and audit_id.
        """
        now = datetime.now(timezone.utc)

        # 1. Get and validate current log
        current_log = await self.get_by_id(log_id)
        if current_log is None:
            raise ValueError(f"Log {log_id} not found")
        if not current_log.is_current:
            raise ValueError(f"Log {log_id} is not the current version")

        previous_verdict = current_log.human_verdict
        previous_value = current_log.actual_value

        # 2. Mark current as superseded
        current_log.is_current = False
        await self._session.flush()

        # 3. Create new version
        new_log = FormulaValidationLog(
            run_id=current_log.run_id,
            sentence_code=current_log.sentence_code,
            entity_type=current_log.entity_type,
            entity_id=current_log.entity_id,
            formula_name=current_log.formula_name,
            expected_constraint=current_log.expected_constraint,
            actual_value=(
                corrected_value
                if corrected_value is not None
                else current_log.actual_value
            ),
            status=current_log.status,
            details=current_log.details,
            # HITL fields
            human_review_id=current_log.human_review_id,
            human_verdict=verdict,
            human_corrected_value=corrected_value,
            human_note=note,
            human_reviewed_at=now,
            human_reviewed_by=reviewer_id,
            human_reviewer_role=reviewer_role,
            # Versioning
            log_version=current_log.log_version + 1,
            is_current=True,
            # Triage
            auto_triage_reason=current_log.auto_triage_reason,
            confidence_at_review=confidence,
        )
        self._session.add(new_log)
        await self._session.flush()

        # Update superseded_by pointer on old log
        current_log.superseded_by = new_log.log_id
        await self._session.flush()

        # 4. Create audit entry
        action_type = "CORRECTED" if verdict == "CORRECTED" else "VERDICT_SUBMITTED"
        audit = FormulaValidationAudit(
            log_id=new_log.log_id,
            action_type=action_type,
            previous_verdict=previous_verdict,
            new_verdict=verdict,
            previous_value=previous_value,
            new_value=corrected_value,
            performed_by=reviewer_id,
            performed_at=now,
            ip_address=ip_address,
            justification=justification,
            review_status="PENDING" if verdict == "CORRECTED" else None,
        )
        self._session.add(audit)
        await self._session.flush()

        # 5. Sync HumanReviewQueue if entry exists for this sent_id
        if current_log.entity_type == "sentence":
            review_stmt = select(HumanReviewQueue).where(
                HumanReviewQueue.sent_id == current_log.entity_id
            )
            review_result = await self._session.execute(review_stmt)
            review_entry = review_result.scalar_one_or_none()
            if review_entry:
                status_map = {
                    "CONFIRMED_PASS": "APPROVED",
                    "CONFIRMED_FAIL": "REJECTED",
                    "CORRECTED": "MODIFIED",
                }
                review_entry.status = status_map.get(verdict, review_entry.status)
                review_entry.reviewed_at = now.isoformat()
                review_entry.reviewer_notes = note
                await self._session.flush()

        return {
            "new_log_id": new_log.log_id,
            "audit_id": audit.audit_id,
            "log_version": new_log.log_version,
        }

    async def rollback_verdict(
        self,
        *,
        audit_id: int,
        rollback_by: str,
        ip_address: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Rollback a HITL verdict. Restores previous version.

        Only allowed for admins or within 1 hour of the original action.
        """
        now = datetime.now(timezone.utc)

        # 1. Get the audit entry
        audit_stmt = select(FormulaValidationAudit).where(
            FormulaValidationAudit.audit_id == audit_id
        )
        audit_result = await self._session.execute(audit_stmt)
        audit_entry = audit_result.scalar_one_or_none()

        if audit_entry is None:
            raise ValueError(f"Audit entry {audit_id} not found")

        # 2. Time check (1 hour window)
        if audit_entry.performed_at:
            elapsed = now - audit_entry.performed_at
            if elapsed > timedelta(hours=1):
                raise ValueError(
                    f"Rollback window expired ({elapsed.total_seconds():.0f}s > 3600s). "
                    "Contact an admin for manual rollback."
                )

        # 3. Get current log and find the superseded one
        current_log_stmt = select(FormulaValidationLog).where(
            FormulaValidationLog.log_id == audit_entry.log_id,
            FormulaValidationLog.is_current == True,  # noqa: E712
        )
        current_result = await self._session.execute(current_log_stmt)
        current_log = current_result.scalar_one_or_none()

        if current_log is None:
            raise ValueError(f"Current log for audit {audit_id} not found")

        # 4. Find previous version
        prev_stmt = select(FormulaValidationLog).where(
            FormulaValidationLog.superseded_by == current_log.log_id,
        )
        prev_result = await self._session.execute(prev_stmt)
        prev_log = prev_result.scalar_one_or_none()

        if prev_log is None:
            raise ValueError("No previous version found to restore")

        # 5. Swap: current → not current, previous → current
        current_log.is_current = False
        prev_log.is_current = True
        prev_log.superseded_by = None
        await self._session.flush()

        # 6. Create rollback audit entry
        rollback_audit = FormulaValidationAudit(
            log_id=prev_log.log_id,
            action_type="ROLLED_BACK",
            previous_verdict=current_log.human_verdict,
            new_verdict=prev_log.human_verdict,
            previous_value=current_log.actual_value,
            new_value=prev_log.actual_value,
            performed_by=rollback_by,
            performed_at=now,
            ip_address=ip_address,
            justification=reason or f"Rollback of audit #{audit_id}",
        )
        self._session.add(rollback_audit)
        await self._session.flush()

        return {
            "restored_log_id": prev_log.log_id,
            "rollback_audit_id": rollback_audit.audit_id,
        }

    async def get_similar_cases(
        self,
        *,
        sent_id: str,
        formula_name: str,
        country: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Get similar FAIL cases for the same formula, optionally filtered by country."""
        stmt = (
            select(
                FormulaValidationLog.log_id,
                FormulaValidationLog.entity_id,
                FormulaValidationLog.actual_value,
                FormulaValidationLog.human_verdict,
                FormulaValidationLog.human_note,
                Sentence.text.label("sentence_text"),
                Sentence.country,
                Sentence.speaker_name,
            )
            .outerjoin(
                Sentence,
                and_(
                    FormulaValidationLog.entity_id == Sentence.sent_id,
                    FormulaValidationLog.entity_type == "sentence",
                ),
            )
            .where(
                FormulaValidationLog.formula_name == formula_name,
                FormulaValidationLog.status == "FAIL",
                FormulaValidationLog.is_current == True,  # noqa: E712
                FormulaValidationLog.entity_id != sent_id,
            )
        )

        if country:
            stmt = stmt.where(Sentence.country == country)

        # Prioritize resolved cases (human_verdict IS NOT NULL first)
        stmt = stmt.order_by(
            case(
                (FormulaValidationLog.human_verdict.isnot(None), 0),
                else_=1,
            ),
            FormulaValidationLog.created_at.desc(),
        ).limit(limit)

        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            {
                "log_id": row.log_id,
                "entity_id": row.entity_id,
                "actual_value": row.actual_value,
                "human_verdict": row.human_verdict,
                "human_note": row.human_note,
                "sentence_text": row.sentence_text,
                "country": row.country,
                "speaker_name": row.speaker_name,
            }
            for row in rows
        ]

    async def get_kpi_stats(self) -> dict[str, Any]:
        """Get KPI statistics for the HITL dashboard header."""
        # Total counts by status and verdict
        stmt = select(
            func.count(FormulaValidationLog.log_id).label("total"),
            func.sum(case((FormulaValidationLog.status == "PASS", 1), else_=0)).label(
                "total_pass"
            ),
            func.sum(case((FormulaValidationLog.status == "FAIL", 1), else_=0)).label(
                "total_fail"
            ),
            func.sum(
                case(
                    (
                        and_(
                            FormulaValidationLog.status == "FAIL",
                            FormulaValidationLog.human_verdict.is_(None),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("pending_review"),
            func.sum(
                case(
                    (FormulaValidationLog.human_verdict == "CONFIRMED_FAIL", 1),
                    else_=0,
                )
            ).label("confirmed_fail"),
            func.sum(
                case(
                    (FormulaValidationLog.human_verdict == "CONFIRMED_PASS", 1),
                    else_=0,
                )
            ).label("confirmed_pass"),
            func.sum(
                case((FormulaValidationLog.human_verdict == "CORRECTED", 1), else_=0)
            ).label("corrected"),
        ).where(FormulaValidationLog.is_current)

        result = await self._session.execute(stmt)
        row = result.one()

        total = row.total or 0
        total_pass = row.total_pass or 0
        total_fail = row.total_fail or 0
        pending = row.pending_review or 0
        confirmed_pass = row.confirmed_pass or 0
        corrected = row.corrected or 0

        # Accuracy: (PASS + CONFIRMED_PASS + CORRECTED) / total
        effective_pass = total_pass + confirmed_pass + corrected
        accuracy = round((effective_pass / total * 100) if total > 0 else 100.0, 2)

        return {
            "total_logs": total,
            "total_pass": total_pass,
            "total_fail": total_fail,
            "pending_review": pending,
            "confirmed_fail": row.confirmed_fail or 0,
            "confirmed_pass": confirmed_pass,
            "corrected": corrected,
            "accuracy_percentage": accuracy,
        }

    async def get_formula_health(self) -> list[dict[str, Any]]:
        """Get health metrics per formula: false_positive_rate, correction_rate."""
        stmt = (
            select(
                FormulaValidationLog.formula_name,
                func.count(FormulaValidationLog.log_id).label("total_fail"),
                func.sum(
                    case(
                        (FormulaValidationLog.human_verdict == "CONFIRMED_PASS", 1),
                        else_=0,
                    )
                ).label("false_positive_count"),
                func.sum(
                    case(
                        (FormulaValidationLog.human_verdict == "CORRECTED", 1),
                        else_=0,
                    )
                ).label("correction_count"),
                func.sum(
                    case(
                        (FormulaValidationLog.human_verdict == "CONFIRMED_FAIL", 1),
                        else_=0,
                    )
                ).label("confirmed_fail_count"),
            )
            .where(
                FormulaValidationLog.status == "FAIL",
                FormulaValidationLog.is_current == True,  # noqa: E712
            )
            .group_by(FormulaValidationLog.formula_name)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        health: list[dict[str, Any]] = []
        for row in rows:
            total = row.total_fail or 1
            fp = row.false_positive_count or 0
            corr = row.correction_count or 0
            cf = row.confirmed_fail_count or 0
            health.append(
                {
                    "formula_name": row.formula_name,
                    "total_fail": total,
                    "false_positive_rate": round(fp / total, 4),
                    "correction_rate": round(corr / total, 4),
                    "confirmed_fail_count": cf,
                    "false_positive_count": fp,
                    "correction_count": corr,
                }
            )
        return health

    async def get_audit_trail(
        self,
        *,
        limit: int = 20,
        log_id: int | None = None,
        reviewer_id: str | None = None,
        action_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent audit trail entries with optional filters."""
        stmt = select(FormulaValidationAudit).order_by(
            FormulaValidationAudit.performed_at.desc()
        )
        if log_id:
            stmt = stmt.where(FormulaValidationAudit.log_id == log_id)
        if reviewer_id:
            stmt = stmt.where(FormulaValidationAudit.performed_by == reviewer_id)
        if action_type:
            stmt = stmt.where(FormulaValidationAudit.action_type == action_type)
        stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "audit_id": a.audit_id,
                "log_id": a.log_id,
                "action_type": a.action_type,
                "previous_verdict": a.previous_verdict,
                "new_verdict": a.new_verdict,
                "previous_value": a.previous_value,
                "new_value": a.new_value,
                "performed_by": a.performed_by,
                "performed_at": a.performed_at.isoformat() if a.performed_at else None,
                "justification": a.justification,
                "review_status": a.review_status,
            }
            for a in rows
        ]

    async def get_reviewer_performance(
        self, reviewer_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get reviewer performance metrics."""
        stmt = select(
            FormulaValidationAudit.performed_by,
            func.count(FormulaValidationAudit.audit_id).label("total_actions"),
            func.sum(
                case(
                    (FormulaValidationAudit.action_type == "VERDICT_SUBMITTED", 1),
                    else_=0,
                )
            ).label("verdict_count"),
            func.sum(
                case(
                    (FormulaValidationAudit.action_type == "CORRECTED", 1),
                    else_=0,
                )
            ).label("correction_count"),
        ).group_by(FormulaValidationAudit.performed_by)
        if reviewer_id:
            stmt = stmt.where(FormulaValidationAudit.performed_by == reviewer_id)

        result = await self._session.execute(stmt)
        rows = result.all()

        perf: list[dict[str, Any]] = []
        for row in rows:
            total = row.total_actions or 1
            corrections = row.correction_count or 0
            perf.append(
                {
                    "reviewer_id": row.performed_by,
                    "total_actions": total,
                    "verdict_count": row.verdict_count or 0,
                    "correction_count": corrections,
                    "correction_rate": round(corrections / total, 4),
                }
            )
        return perf
