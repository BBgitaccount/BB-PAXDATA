from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from bb_paxdata.infrastructure.db.models import FormulaValidationLog
from bb_paxdata.infrastructure.db.repositories.base import BaseRepository


class FormulaValidationRepository(BaseRepository[FormulaValidationLog]):
    """Async repository for FormulaValidationLog ORM model."""

    model_class = FormulaValidationLog

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
