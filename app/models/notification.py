from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class NotificationType:
    VOTE = "vote"
    COMMENT = "comment"
    REPLY = "reply"
    SYSTEM = "system"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(20), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=text('NOW()'))

    # Foreign keys with explicit naming
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    related_post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=True)
    related_comment_id = Column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True)
    triggered_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships with EXPLICIT foreign_keys
    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="notifications"
    )

    triggered_by_user = relationship(
        "User",
        foreign_keys=[triggered_by_user_id],
        back_populates="triggered_notifications"
    )

    related_post = relationship("Post")
    related_comment = relationship("Comment")

    __table_args__ = (
        Index('ix_notifications_user_id', 'user_id'),
        Index('ix_notifications_is_read', 'is_read'),
        Index('ix_notifications_created_at', 'created_at'),
        Index('ix_notifications_type', 'type'),
    )