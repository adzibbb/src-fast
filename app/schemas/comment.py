from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid
from .user import User

class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: uuid.UUID
    created_at: datetime
    post_id: uuid.UUID
    author_id: uuid.UUID
    author: User

    model_config = ConfigDict(from_attributes=True)