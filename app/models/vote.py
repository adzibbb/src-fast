from sqlalchemy import Column, String, DateTime, ForeignKey, text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class VoteType:
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class Vote(Base):
    __tablename__ = "votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vote_type = Column(String(20), nullable=False)  # Use String instead of Enum
    created_at = Column(DateTime, server_default=text('NOW()'))
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)


    # Relationships
    post = relationship("Post", back_populates="votes")
    user = relationship("User", back_populates="votes")

    __table_args__ = (
            UniqueConstraint('user_id', 'post_id', name='unique_user_post_vote'),
            Index('ix_votes_user_id', 'user_id'),
            Index('ix_votes_post_id', 'post_id'),
        )