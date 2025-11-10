from sqlalchemy import Column, String, Integer, DateTime, text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    hashed_password = Column(String, nullable=False)
    total_points = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=text('NOW()'))
    last_login_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)  # For soft deletion
    is_superuser = Column(Boolean, default=False)  # Admin flag
    email_verified = Column(Boolean, default=False)

    # Relationships with explicit foreign key specifications
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="author")
    votes = relationship("Vote", back_populates="user")

    # Notifications where this user is the recipient
    notifications = relationship(
        "Notification",
        foreign_keys="Notification.user_id",  # Explicit foreign key
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Notifications triggered by this user
    triggered_notifications = relationship(
        "Notification",
        foreign_keys="Notification.triggered_by_user_id",  # Explicit foreign key
        back_populates="triggered_by_user",
        cascade="all, delete-orphan"
    )