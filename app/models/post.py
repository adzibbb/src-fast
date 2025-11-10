from sqlalchemy import Column, String, Text, DateTime, ForeignKey, text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(102), nullable=False)
    content = Column(Text(1010), nullable=False)
    category = Column(String(50), default="daily-joy")
    created_at = Column(DateTime, server_default=text('NOW()'))
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    is_published = Column(Boolean, default=True)
    updated_at = Column(DateTime, server_default=text('NOW()'))

    # Relationships
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="post", cascade="all, delete-orphan")

    # Add these indexes
    __table_args__ = (
        Index('ix_posts_author_id', 'author_id'),
        Index('ix_posts_category', 'category'),
        Index('ix_posts_created_at', 'created_at'),
    )