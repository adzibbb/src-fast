import uuid

from sqlalchemy import Column, String, DateTime, text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ReactionType:
    SMILE = "smile"
    LAUGH = "laugh"
    LOVE = "love"
    INSIGHTFUL = "insightful"
    SUPPORTIVE = "supportive"

class Reaction(Base):
    __tablename__ = "reactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reaction_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, server_default=text('NOW()'))
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Ensure one reaction per user per post
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='unique_user_post_reaction'),)

    # Relationships
    post = relationship("Post", back_populates="reactions")
    user = relationship("User", back_populates="reactions")
