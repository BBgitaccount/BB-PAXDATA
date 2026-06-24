# src/bb_paxdata/interfaces/api/routers/v1/notifications.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.infrastructure.db.notification_table import (
    Notification,
    NotificationPriority,
    NotificationType,
)
from bb_paxdata.interfaces.api.dependencies import get_db

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# Request/Response Schemas
class NotificationCreateRequest(BaseModel):
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    notification_type: str = Field(
        NotificationType.INFO.value, description="Notification type"
    )
    priority: str = Field(
        NotificationPriority.MEDIUM.value, description="Notification priority"
    )
    action_url: str | None = Field(None, description="Action URL for the notification")
    metadata: dict | None = Field(None, description="Additional metadata")
    expires_at: str | None = Field(None, description="Expiration timestamp")


class NotificationResponse(BaseModel):
    id: str
    user_id: str | None
    title: str
    message: str
    notification_type: str
    priority: str
    is_read: bool
    read_at: str | None
    action_url: str | None
    metadata: dict | None
    created_at: str
    expires_at: str | None


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class MarkReadRequest(BaseModel):
    notification_ids: list[str] = Field(
        ..., description="List of notification IDs to mark as read"
    )
    mark_all: bool = Field(False, description="Mark all notifications as read")


class BulkDeleteRequest(BaseModel):
    notification_ids: list[str] = Field(
        ..., description="List of notification IDs to delete"
    )
    delete_all_read: bool = Field(False, description="Delete all read notifications")


@router.post(
    "", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("100/hour")
async def create_notification(
    request: Request,
    notification_req: NotificationCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Create a new notification."""
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=request.headers.get("X-User-ID"),
        title=notification_req.title,
        message=notification_req.message,
        notification_type=notification_req.notification_type,
        priority=notification_req.priority,
        is_read=False,
        action_url=notification_req.action_url,
        metadata=notification_req.metadata,
        expires_at=(
            datetime.fromisoformat(notification_req.expires_at).replace(tzinfo=None)
            if notification_req.expires_at
            else None
        ),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type,
        priority=notification.priority,
        is_read=notification.is_read,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
        action_url=notification.action_url,
        metadata=notification.metadata,
        created_at=(
            notification.created_at.isoformat() if notification.created_at else ""
        ),
        expires_at=(
            notification.expires_at.isoformat() if notification.expires_at else None
        ),
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    user_id: str | None = None,
    is_read: bool | None = None,
    notification_type: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """List notifications with optional filters."""
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

    result = await db.scalars(stmt)
    notifications = result.all()

    # Count unread
    unread_stmt = select(Notification).where(not Notification.is_read)
    if user_id:
        unread_stmt = unread_stmt.where(Notification.user_id == user_id)
    unread_result = await db.scalars(unread_stmt)
    unread_count = len(unread_result.all())

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=notif.id,
                user_id=notif.user_id,
                title=notif.title,
                message=notif.message,
                notification_type=notif.notification_type,
                priority=notif.priority,
                is_read=notif.is_read,
                read_at=notif.read_at.isoformat() if notif.read_at else None,
                action_url=notif.action_url,
                metadata=notif.metadata,
                created_at=notif.created_at.isoformat() if notif.created_at else "",
                expires_at=notif.expires_at.isoformat() if notif.expires_at else None,
            )
            for notif in notifications
        ],
        total=len(notifications),
        unread_count=unread_count,
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Get a specific notification by ID."""
    stmt = select(Notification).where(Notification.id == notification_id)
    notification = await db.scalar(stmt)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification not found: {notification_id}",
        )

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type,
        priority=notification.priority,
        is_read=notification.is_read,
        read_at=notification.read_at.isoformat() if notification.read_at else None,
        action_url=notification.action_url,
        metadata=notification.metadata,
        created_at=(
            notification.created_at.isoformat() if notification.created_at else ""
        ),
        expires_at=(
            notification.expires_at.isoformat() if notification.expires_at else None
        ),
    )


@router.post("/mark-read")
async def mark_notifications_read(
    mark_req: MarkReadRequest,
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark notifications as read."""
    if mark_req.mark_all:
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
    else:
        stmt = (
            update(Notification)
            .where(Notification.id.in_(mark_req.notification_ids))
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )

    await db.execute(stmt)
    await db.commit()

    return {"status": "success", "message": "Notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a specific notification."""
    stmt = select(Notification).where(Notification.id == notification_id)
    notification = await db.scalar(stmt)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification not found: {notification_id}",
        )

    await db.delete(notification)
    await db.commit()

    return {"status": "success", "message": "Notification deleted"}


@router.post("/bulk-delete")
async def bulk_delete_notifications(
    delete_req: BulkDeleteRequest,
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk delete notifications."""
    if delete_req.delete_all_read:
        stmt = select(Notification).where(Notification.is_read)
        if user_id:
            stmt = stmt.where(Notification.user_id == user_id)
        notifications = await db.scalars(stmt)
        for notif in notifications:
            await db.delete(notif)
    else:
        stmt = select(Notification).where(
            Notification.id.in_(delete_req.notification_ids)
        )
        notifications = await db.scalars(stmt)
        for notif in notifications:
            await db.delete(notif)

    await db.commit()

    return {"status": "success", "message": "Notifications deleted"}


@router.get("/stats/summary")
async def get_notification_stats(
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get notification statistics summary."""
    # Total count
    total_stmt = select(Notification)
    if user_id:
        total_stmt = total_stmt.where(Notification.user_id == user_id)
    total_result = await db.scalars(total_stmt)
    total_count = len(total_result.all())

    # Unread count
    unread_stmt = select(Notification).where(not Notification.is_read)
    if user_id:
        unread_stmt = unread_stmt.where(Notification.user_id == user_id)
    unread_result = await db.scalars(unread_stmt)
    unread_count = len(unread_result.all())

    # By type
    type_counts = {}
    for notif_type in NotificationType:
        type_stmt = select(Notification).where(
            Notification.notification_type == notif_type.value
        )
        if user_id:
            type_stmt = type_stmt.where(Notification.user_id == user_id)
        type_result = await db.scalars(type_stmt)
        type_counts[notif_type.value] = len(type_result.all())

    # By priority
    priority_counts = {}
    for priority in NotificationPriority:
        priority_stmt = select(Notification).where(
            Notification.priority == priority.value
        )
        if user_id:
            priority_stmt = priority_stmt.where(Notification.user_id == user_id)
        priority_result = await db.scalars(priority_stmt)
        priority_counts[priority.value] = len(priority_result.all())

    return {
        "total": total_count,
        "unread": unread_count,
        "by_type": type_counts,
        "by_priority": priority_counts,
    }
