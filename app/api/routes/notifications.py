from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import uuid
from typing import List
from app.database import get_db
from app.api.dependencies import get_current_user
from app.services.notification_service import NotificationService
from app.schemas.notification import Notification, UnreadCount
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[Notification])
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends()
):
    return await notification_service.get_user_notifications(
        db, current_user.id, page, page_size
    )

@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends()
):
    return await notification_service.get_unread_count(db, current_user.id)

@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends()
):
    await notification_service.mark_as_read(db, notification_id, current_user.id)
    return {"message": "Notification marked as read"}

@router.patch("/mark-all-read")
async def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends()
):
    await notification_service.mark_all_as_read(db, current_user.id)
    return {"message": "All notifications marked as read"}