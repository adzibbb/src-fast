import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.crud.vote import handle_vote
from app.database import get_db
from app.models.user import User
from app.schemas.post import PostWithDetails
from app.schemas.vote import VoteType

router = APIRouter()


@router.post("/{post_id}/upvote", response_model=PostWithDetails)
async def upvote_post(
        post_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    return handle_vote(
        db, post_id, current_user.id, VoteType.UPVOTE
    )


@router.post("/{post_id}/downvote", response_model=PostWithDetails)
async def downvote_post(
        post_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    return handle_vote(
        db, post_id, current_user.id, VoteType.DOWNVOTE
    )



