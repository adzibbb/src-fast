from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Dict, Optional
import uuid
import logging
from app.models.notification import Notification as NotificationModel, NotificationType
from app.models.user import User
from app.schemas.notification import NotificationCreate, Notification as NotificationSchema, UnreadCount
from app.websocket.hub import manager

logger = logging.getLogger(__name__)


class NotificationService:
    async def create_notification(self, db: Session, request: NotificationCreate):
        """Create a new notification"""
        try:
            notification = NotificationModel(
                title=request.title,
                message=request.message,
                type=request.type,  # Remove NotificationType() wrapper
                user_id=request.user_id,
                related_post_id=request.related_post_id,
                related_comment_id=request.related_comment_id,
                triggered_by_user_id=request.triggered_by_user_id,
                is_read=False
            )

            db.add(notification)
            db.commit()
            db.refresh(notification)

            # Send real-time notification via WebSocket
            notification_dto = await self._get_notification_dto(db, notification.id)
            if notification_dto:
                await manager.send_to_user(str(request.user_id), {
                    "type": "receive_notification",
                    "notification": notification_dto.model_dump(mode='json')
                })

            logger.info(f"Created notification for user {request.user_id}")
            return notification

        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            db.rollback()
            raise

    async def get_user_notifications(
            self,
            db: Session,
            user_id: uuid.UUID,
            page: int = 1,
            page_size: int = 20
    ) -> List[NotificationSchema]:
        """Get paginated notifications for a user"""
        try:
            # Validate pagination parameters
            if page < 1:
                page = 1
            if page_size > 100:  # Prevent excessive queries
                page_size = 100
            if page_size < 1:
                page_size = 20

            offset = (page - 1) * page_size

            # Use selectinload for better performance
            from sqlalchemy.orm import selectinload

            notifications = db.query(NotificationModel) \
                .options(selectinload(NotificationModel.triggered_by_user)) \
                .filter(NotificationModel.user_id == user_id) \
                .order_by(NotificationModel.created_at.desc()) \
                .offset(offset) \
                .limit(page_size) \
                .all()

            return [
                NotificationSchema.model_validate(notification)  # Use Pydantic v2 method
                for notification in notifications
            ]

        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            raise


    async def _get_notification_dto(self, db: Session, notification_id: uuid.UUID) -> Optional[NotificationSchema]:
        """Get notification DTO for WebSocket"""
        notification = db.query(NotificationModel) \
            .outerjoin(User, NotificationModel.triggered_by_user_id == User.id) \
            .filter(NotificationModel.id == notification_id) \
            .first()

        if not notification:
            return None

        return NotificationSchema(
            id=notification.id,
            title=notification.title,
            message=notification.message,
            type=notification.type,  # Already the correct type
            is_read=notification.is_read,
            created_at=notification.created_at,
            user_id=notification.user_id,  # Add missing field
            related_post_id=notification.related_post_id,
            related_comment_id=notification.related_comment_id,
            triggered_by_user_id=notification.triggered_by_user_id,
            triggered_by_user=User(
                id=notification.triggered_by_user.id,
                username=notification.triggered_by_user.username,
                email=notification.triggered_by_user.email,
                display_name=notification.triggered_by_user.display_name,
                total_points=notification.triggered_by_user.total_points,
                created_at=notification.triggered_by_user.created_at
            ) if notification.triggered_by_user else None
        )


    async def get_unread_count(self, db: Session, user_id: uuid.UUID) -> UnreadCount:
        """Get unread notification counts by type"""
        try:
            unread_notifications = db.query(NotificationModel) \
                .filter(and_(NotificationModel.user_id == user_id, NotificationModel.is_read == False)) \
                .all()

            by_type: Dict[str, int] = {}
            for notification in unread_notifications:
                type_str = notification.type
                by_type[type_str] = by_type.get(type_str, 0) + 1

            return UnreadCount(
                total=len(unread_notifications),
                by_type=by_type
            )

        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            raise

    async def mark_as_read(self, db: Session, notification_id: uuid.UUID, user_id: uuid.UUID):
        """Mark a specific notification as read"""
        try:
            notification = db.query(NotificationModel) \
                .filter(and_(NotificationModel.id == notification_id, NotificationModel.user_id == user_id)) \
                .first()

            if notification and not notification.is_read:
                notification.is_read = True
                db.commit()
                logger.info(f"Marked notification {notification_id} as read")

        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            db.rollback()
            raise

    async def mark_all_as_read(self, db: Session, user_id: uuid.UUID):
        """Mark all user notifications as read"""
        try:
            # Add timeout for large operations
            import asyncpg  # or your async driver
            from sqlalchemy import text

            # More efficient bulk update
            result = db.execute(
                text("""
                    UPDATE notifications 
                    SET is_read = true 
                    WHERE user_id = :user_id 
                    AND is_read = false
                    AND created_at > NOW() - INTERVAL '90 days'  # Limit scope
                """),
                {"user_id": user_id}
            )
            db.commit()

            logger.info(f"Marked {result.rowcount} notifications as read for user {user_id}")

        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            db.rollback()
            raise
