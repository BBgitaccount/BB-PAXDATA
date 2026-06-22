"""CalibrationRepository — simple CRUD for CalibrationReport ORM."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.application.domain.models.calibration import CalibrationReport
from bb_paxdata.infrastructure.db.human_review_table import CalibrationReportORM

logger = structlog.get_logger(__name__)


class CalibrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, report: CalibrationReport) -> None:
        orm = CalibrationReportORM(
            id=report.id,
            prompt_version=report.prompt_version,
            evaluation_period_start=report.evaluation_period_start,
            evaluation_period_end=report.evaluation_period_end,
            cohens_kappa_frame=report.cohens_kappa_frame,
            cohens_kappa_risk=report.cohens_kappa_risk,
            ai_human_f1_frame=report.ai_human_f1_frame,
            ai_human_f1_risk=report.ai_human_f1_risk,
            sbi_mae=report.sbi_mae,
            total_reviews=report.total_reviews,
            total_disagreements=report.total_disagreements,
            top_disagreement_patterns=report.top_disagreement_patterns,
            requires_prompt_update=report.requires_prompt_update,
            requires_weight_update=report.requires_weight_update,
            alert_message=report.alert_message,
            created_at=report.created_at,
        )
        self._session.add(orm)
        logger.info("Saved CalibrationReport", extra={"id": report.id})

    async def get_by_prompt(self, prompt_version: str) -> list[CalibrationReport]:
        stmt = select(CalibrationReportORM).where(
            CalibrationReportORM.prompt_version == prompt_version
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    @staticmethod
    def _to_domain(orm: CalibrationReportORM) -> CalibrationReport:
        return CalibrationReport(
            id=orm.id,
            prompt_version=orm.prompt_version,
            evaluation_period_start=orm.evaluation_period_start,
            evaluation_period_end=orm.evaluation_period_end,
            cohens_kappa_frame=orm.cohens_kappa_frame,
            cohens_kappa_risk=orm.cohens_kappa_risk,
            ai_human_f1_frame=orm.ai_human_f1_frame,
            ai_human_f1_risk=orm.ai_human_f1_risk,
            sbi_mae=orm.sbi_mae,
            total_reviews=orm.total_reviews,
            total_disagreements=orm.total_disagreements,
            top_disagreement_patterns=orm.top_disagreement_patterns or [],
            requires_prompt_update=orm.requires_prompt_update,
            requires_weight_update=orm.requires_weight_update,
            alert_message=orm.alert_message,
            created_at=orm.created_at,
        )
