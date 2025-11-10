from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid
from enum import Enum

class ReactionType(str, Enum):
    SMILE = "smile"
    LAUGH = "laugh"
    LOVE = "love"
    INSIGHTFUL = "insightful"
    SUPPORTIVE = "supportive"

class ReactionBase(BaseModel):
    reaction_type: ReactionType

class ReactionCreate(ReactionBase):
    post_id: uuid.UUID

class Reaction(ReactionBase):
    id: uuid.UUID
    created_at: datetime
    post_id: uuid.UUID
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)