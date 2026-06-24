# src/bb_paxdata/infrastructure/scheduled_reports/scheduler.py
from __future__ import annotations

from celery.schedules import crontab
from sqlalchemy import select

from bb_paxdata.infrastructure.db.scheduled_reports_table import (
    ReportFrequency,
    ScheduledReport,
)
from bb_paxdata.infrastructure.db.session import async_session_maker


def setup_beat_schedule(app) -> None:
    """
    Configure Celery Beat schedule from database.

    This function reads active scheduled reports from the database
    and creates corresponding Celery Beat schedule entries.

    Args:
        app: Celery application instance
    """
    import asyncio

    async def _fetch_schedules():
        async with async_session_maker() as session:
            stmt = select(ScheduledReport).where(ScheduledReport.is_active)
            result = await session.scalars(stmt)
            return list(result.all())

    scheduled_reports = asyncio.run(_fetch_schedules())

    schedule = {}

    for report in scheduled_reports:
        cron = build_crontab(
            report.frequency,
            report.day_of_week,
            report.day_of_month,
            report.time_of_day,
            report.timezone,
        )

        schedule[f"scheduled_report_{report.id}"] = {
            "task": "scheduled_reports.generate_report",
            "schedule": cron,
            "args": [str(report.id)],
        }

    app.conf.beat_schedule = schedule


def build_crontab(
    frequency: str,
    day_of_week: int | None,
    day_of_month: int | None,
    time_of_day: str,
    tz: str,
) -> crontab:
    """
    Build Celery crontab schedule from report configuration.

    Args:
        frequency: Report frequency (daily, weekly, monthly, quarterly)
        day_of_week: Day of week (0-6, Monday=0) for weekly reports
        day_of_month: Day of month (1-28) for monthly reports
        time_of_day: Time string (HH:MM:SS)
        tz: Timezone string

    Returns:
        Celery crontab schedule
    """
    hour, minute, _ = map(int, time_of_day.split(":"))

    if frequency == ReportFrequency.WEEKLY.value:
        return crontab(hour=hour, minute=minute, day_of_week=day_of_week)
    elif frequency == ReportFrequency.MONTHLY.value:
        return crontab(hour=hour, minute=minute, day_of_month=day_of_month)
    elif frequency == ReportFrequency.DAILY.value:
        return crontab(hour=hour, minute=minute)
    elif frequency == ReportFrequency.QUARTERLY.value:
        # Quarterly requires custom logic - approximate with monthly
        return crontab(hour=hour, minute=minute, day_of_month=1)

    return crontab(hour=hour, minute=minute)
