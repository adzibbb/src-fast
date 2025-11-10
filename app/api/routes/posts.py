import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.crud import post as post_crud
from app.database import get_db
from app.schemas.post import Post, PostCreate, PostUpdate, PostWithDetails, PaginatedResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=PaginatedResponse[PostWithDetails])
def read_posts(
        page: int = 1,
        page_size: int = 10,
        category: Optional[str] = None,
        sort_by: Optional[str] = None,
        search: Optional[str] = None,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    try:
        if page < 1:
            raise HTTPException(status_code=400, detail="Page must be greater than 0")
        if page_size < 1 or page_size > 100:
            raise HTTPException(status_code=400, detail="Page size must be between 1 and 100")

        skip = (page - 1) * page_size

        posts = post_crud.get_posts_with_details(
            db,
            skip=skip,
            limit=page_size,
            category=category,
            sort_by=sort_by,
            search=search,
            current_user_id=current_user.id if current_user else None
        )

        total_count = post_crud.get_posts_count(db, category=category, search=search)
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1

        return {
            "items": posts,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
            "has_previous_page": page > 1
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching posts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching posts"
        )


@router.post("/", response_model=Post)
def create_post(
        post: PostCreate,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    return post_crud.create_post(db=db, post=post, author_id=current_user.id)


@router.get("/{post_id}", response_model=PostWithDetails)
def read_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Use the new method to get post with details
    db_post = post_crud.get_post_with_details(db, post_id=post_id, current_user_id=current_user.id if current_user else None)
    if db_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return db_post

@router.put("/{post_id}", response_model=Post)
def update_post(
        post_id: uuid.UUID,
        post_update: PostUpdate,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    db_post = post_crud.get_post(db, post_id=post_id)
    if db_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if db_post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this post")

    return post_crud.update_post(db=db, post_id=post_id, post_update=post_update)


@router.delete("/{post_id}")
def delete_post(
        post_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_user)
):
    db_post = post_crud.get_post(db, post_id=post_id)
    if db_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if db_post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")

    post_crud.delete_post(db=db, post_id=post_id)
    return {"message": "Post deleted successfully"}
