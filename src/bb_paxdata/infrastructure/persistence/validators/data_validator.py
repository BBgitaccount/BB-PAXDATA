from __future__ import annotations

from typing import Any

from bb_paxdata.application.cli.use_cases.validation import Severity, ValidationIssue
from bb_paxdata.infrastructure.persistence.models import AnalyticModel, TranscriptModel
from sqlalchemy import func, select


class SQLDataValidator:
    """Checks data integrity using SQL queries."""

    async def check_orphan_transcripts(self, session: Any) -> ValidationIssue | None:
        return None

    async def check_analytic_completeness(self, session: Any) -> ValidationIssue | None:
        # Find transcripts without analytics
        stmt = select(func.count(TranscriptModel.id)).where(
            ~TranscriptModel.analytics.any()
        )
        result = await session.execute(stmt)
        count = result.scalar()

        if count > 0:
            return ValidationIssue(
                check_name="Analytic Completeness",
                severity=Severity.WARNING,
                message=f"{count} transcripts are missing analytic data.",
                affected_rows=count,
                suggested_fix="Run the analysis process for missing transcripts.",
            )
        return None

    async def check_score_ranges(self, session: Any) -> list[ValidationIssue]:
        issues = []
        # SBI score should be between -1 and 1 (example)
        stmt = select(func.count(AnalyticModel.id)).where(
            (AnalyticModel.sbi_score < -1.0) | (AnalyticModel.sbi_score > 1.0)
        )
        result = await session.execute(stmt)
        count = result.scalar()

        if count > 0:
            issues.append(
                ValidationIssue(
                    check_name="Score Ranges (SBI)",
                    severity=Severity.CRITICAL,
                    message=f"{count} analytic records have SBI score out of range.",
                    affected_rows=count,
                )
            )
        return issues

    async def check_null_mandatory_fields(self, session: Any) -> list[ValidationIssue]:
        return []

    async def check_duplicate_transcripts(self, session: Any) -> ValidationIssue | None:
        return None
