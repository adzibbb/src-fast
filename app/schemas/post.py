from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional, Generic, TypeVar
import uuid
from .user import User
from .comment import Comment


class PostBase(BaseModel):
    title: str
    content: str
    category: str = "daily-joy"

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=102)
    content: str = Field(..., min_length=1)
    category: str = Field(default="daily-joy", max_length=50)

class Post(PostBase):
    id: uuid.UUID
    created_at: datetime
    author_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

class PostWithDetails(Post):
    upvote_count: int
    downvote_count: int
    score: int
    current_user_vote: Optional[str] = None
    author: User
    comments: List[Comment] = []
    
    
T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool
