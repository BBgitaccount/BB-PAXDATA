# src/bb_paxdata/application/services/notification_service.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.notification_table import (
    Notification,
    NotificationPriority,
    NotificationType,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class NotificationService:
    """Service for managing notifications with real-time broadcasting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        user_id: str | None,
        title: str,
        message: str,
        notification_type: str = NotificationType.INFO.value,
        priority: str = NotificationPriority.MEDIUM.value,
        action_url: str | None = None,
        metadata: dict | None = None,
        expires_at: datetime | None = None,
    ) -> Notification:
        """Create a new notification."""
        import uuid

        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            is_read=False,
            action_url=action_url,
            metadata=json.dumps(metadata) if metadata else None,
            expires_at=expires_at.replace(tzinfo=None) if expires_at else None,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        logger.info(
            "Notification created",
            notification_id=notification.id,
            user_id=user_id,
            title=title,
            type=notification_type,
        )

        return notification

    async def mark_as_read(self, notification_id: str) -> None:
        """Mark a notification as read."""
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

        logger.info("Notification marked as read", notification_id=notification_id)

    async def mark_all_as_read(self, user_id: str | None = None) -> int:
        """Mark all notifications as read for a user or globally."""
        stmt = (
            update(Notification)
            .where(not Notification.is_read)
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        if user_id:
            stmt = stmt.where(Notification.user_id == user_id)

        result = await self.db.execute(stmt)
        await self.db.commit()
        count = result.rowcount

        logger.info(
            "Notifications marked as read",
            user_id=user_id,
            count=count,
        )

        return count

    async def delete_notification(self, notification_id: str) -> None:
        """Delete a notification."""
        stmt = select(Notification).where(Notification.id == notification_id)
        notification = await self.db.scalar(stmt)

        if notification:
            await self.db.delete(notification)
            await self.db.commit()
            logger.info("Notification deleted", notification_id=notification_id)

    async def delete_all_read(self, user_id: str | None = None) -> int:
        """Delete all read notifications for a user or globally."""
        stmt = select(Notification).where(Notification.is_read)
        if user_id:
            stmt = stmt.where(Notification.user_id == user_id)

        notifications = await self.db.scalars(stmt)
        count = 0
        for notification in notifications:
            await self.db.delete(notification)
            count += 1

        await self.db.commit()

        logger.info(
            "Read notifications deleted",
            user_id=user_id,
            count=count,
        )

        return count

    async def get_unread_count(self, user_id: str | None = None) -> int:
        """Get count of unread notifications."""
        stmt = select(Notification).where(not Notification.is_read)
        if user_id:
            stmt = stmt.where(Notification.user_id == user_id)

        result = await self.db.scalars(stmt)
        return len(result.all())

    async def get_notifications(
        self,
        user_id: str | None = None,
        is_read: bool | None = None,
        notification_type: str | None = None,
        priority: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications with optional filters."""
        stmt = select(Notification)

        if user_id:
            stmt = stmt.where(Notification.user_id == user_id)
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
        if notification_type:
            stmt = stmt.where(Notification.notification_type == notification_type)
        if priority:
            stmt = stmt.where(Notification.priority == priority)

        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.scalars(stmt)
        return result.all()

    async def cleanup_expired_notifications(self) -> int:
        """Delete expired notifications."""
        stmt = select(Notification).where(
            Notification.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
        )

        notifications = await self.db.scalars(stmt)
        count = 0
        for notification in notifications:
            await self.db.delete(notification)
            count += 1

        await self.db.commit()

        logger.info("Expired notifications cleaned up", count=count)

        return count


# Helper functions for common notification types
async def notify_export_completed(
    db: AsyncSession,
    user_id: str | None,
    file_id: str,
    export_type: str,
    download_url: str,
) -> Notification:
    """Create a notification for export completion."""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=user_id,
        title=f"{export_type.upper()} Export Completed",
        message=f"Your {export_type} export for file {file_id} is ready for download.",
        notification_type=NotificationType.EXPORT_COMPLETED.value,
        priority=NotificationPriority.MEDIUM.value,
        action_url=download_url,
        metadata={"file_id": file_id, "export_type": export_type},
    )


async def notify_export_failed(
    db: AsyncSession,
    user_id: str | None,
    file_id: str,
    export_type: str,
    error_message: str,
) -> Notification:
    """Create a notification for export failure."""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=user_id,
        title=f"{export_type.upper()} Export Failed",
        message=f"Your {export_type} export for file {file_id} failed: {error_message}",
        notification_type=NotificationType.EXPORT_FAILED.value,
        priority=NotificationPriority.HIGH.value,
        metadata={
            "file_id": file_id,
            "export_type": export_type,
            "error": error_message,
        },
    )


async def notify_analysis_completed(
    db: AsyncSession,
    user_id: str | None,
    file_id: str,
    file_name: str,
) -> Notification:
    """Create a notification for analysis completion."""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=user_id,
        title="Analysis Completed",
        message=f"Analysis for '{file_name}' ({file_id}) has been completed successfully.",
        notification_type=NotificationType.ANALYSIS_COMPLETED.value,
        priority=NotificationPriority.MEDIUM.value,
        action_url=f"/files/{file_id}",
        metadata={"file_id": file_id, "file_name": file_name},
    )


async def notify_system_alert(
    db: AsyncSession,
    user_id: str | None,
    title: str,
    message: str,
    priority: str = NotificationPriority.HIGH.value,
) -> Notification:
    """Create a system alert notification."""
    service = NotificationService(db)
    return await service.create_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=NotificationType.SYSTEM.value,
        priority=priority,
    )
