from sqlalchemy import Column, Text, DateTime, ForeignKey, text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=text('NOW()'))
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")

    __table_args__ = (
        Index('ix_comments_post_id', 'post_id'),
        Index('ix_comments_author_id', 'author_id'),
        Index('ix_comments_created_at', 'created_at'),
    )