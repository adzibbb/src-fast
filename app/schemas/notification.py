from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, Dict
import uuid
from enum import Enum
from .user import User

class NotificationType(str, Enum):
    VOTE = "vote"
    COMMENT = "comment"
    REPLY = "reply"
    SYSTEM = "system"

class NotificationBase(BaseModel):
    title: str = Field(..., max_length=100)
    message: str = Field(..., max_length=500)
    type: NotificationType
    related_post_id: Optional[uuid.UUID] = None
    related_comment_id: Optional[uuid.UUID] = None
    triggered_by_user_id: Optional[uuid.UUID] = None

class NotificationCreate(NotificationBase):
    user_id: uuid.UUID

class Notification(NotificationBase):
    id: uuid.UUID
    is_read: bool
    created_at: datetime
    user_id: uuid.UUID
    triggered_by_user: Optional[User] = None

    model_config = ConfigDict(from_attributes=True)

class UnreadCount(BaseModel):
    total: int
    by_type: Dict[str, int]