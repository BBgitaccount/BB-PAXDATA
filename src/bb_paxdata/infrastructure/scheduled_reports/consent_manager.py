# src/bb_paxdata/infrastructure/scheduled_reports/consent_manager.py
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select

from bb_paxdata.infrastructure.db.scheduled_reports_table import DistributionList
from bb_paxdata.infrastructure.db.session import async_session_maker


class ConsentManager:
    """GDPR/KVKK consent management for email distribution lists."""

    async def add_recipient_with_consent(
        self,
        scheduled_report_id: str,
        email: str,
        name: str | None = None,
        added_by: str | None = None,
    ) -> str:
        """
        Add recipient to distribution list with pending consent.

        Args:
            scheduled_report_id: ID of the scheduled report
            email: Recipient email address
            name: Recipient name (optional)
            added_by: User ID who added the recipient

        Returns:
            Consent token for verification
        """
        token = secrets.token_urlsafe(32)

        async with async_session_maker() as session:
            distribution = DistributionList(
                scheduled_report_id=scheduled_report_id,
                email=email,
                name=name,
                consent_token=token,
                consent_given_at=None,  # Pending consent
                added_by=added_by,
            )
            session.add(distribution)
            await session.commit()

        # In production, send consent email here
        # self._send_consent_email(email, name, token)

        return token

    async def confirm_consent(self, token: str) -> bool:
        """
        Confirm consent using token from email link.

        Args:
            token: Consent token from email

        Returns:
            True if consent confirmed successfully

        Raises:
            ValueError: Invalid or expired token
        """
        async with async_session_maker() as session:
            stmt = select(DistributionList).where(
                DistributionList.consent_token == token
            )
            dist = await session.scalar(stmt)

            if not dist:
                raise ValueError("Invalid consent token")

            if dist.unsubscribed_at:
                raise ValueError("Recipient has unsubscribed")

            if dist.consent_given_at:
                return True  # Already confirmed

            dist.consent_given_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

            return True

    async def unsubscribe(self, token: str) -> bool:
        """
        Unsubscribe recipient using token from email link.

        Args:
            token: Consent/unsubscribe token

        Returns:
            True if unsubscribed successfully
        """
        async with async_session_maker() as session:
            stmt = select(DistributionList).where(
                DistributionList.consent_token == token
            )
            dist = await session.scalar(stmt)

            if not dist:
                return False

            dist.unsubscribed_at = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

            return True

    async def get_active_recipients(
        self, scheduled_report_id: str
    ) -> list[DistributionList]:
        """
        Get list of recipients with valid consent who haven't unsubscribed.

        Args:
            scheduled_report_id: ID of the scheduled report

        Returns:
            List of active DistributionList objects
        """
        async with async_session_maker() as session:
            stmt = select(DistributionList).where(
                DistributionList.scheduled_report_id == scheduled_report_id,
                DistributionList.consent_given_at.isnot(None),
                DistributionList.unsubscribed_at.is_(None),
            )
            result = await session.scalars(stmt)
            return list(result.all())
