from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid
from enum import Enum

class VoteType(str, Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"

class VoteBase(BaseModel):
    vote_type: VoteType

class VoteCreate(VoteBase):
    post_id: uuid.UUID

class Vote(VoteBase):
    id: uuid.UUID
    created_at: datetime
    post_id: uuid.UUID
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)