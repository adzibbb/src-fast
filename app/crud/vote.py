from sqlalchemy.orm import Session

from app.crud.post import get_post, get_post_with_details
from app.models.vote import Vote, VoteType
import uuid

from app.services.points_service import PointsService

point_service = PointsService()


def get_vote(db: Session, post_id: uuid.UUID, user_id: uuid.UUID):
    return db.query(Vote) \
        .filter(Vote.post_id == post_id, Vote.user_id == user_id) \
        .first()


def handle_vote(db: Session, post_id: uuid.UUID, user_id: uuid.UUID, vote_type: VoteType):
    existing_vote = get_vote(db, post_id, user_id)
    is_new_vote = False
    previous_vote_type = None

    if existing_vote:
        previous_vote_type = existing_vote.vote_type
        if existing_vote.vote_type == vote_type:
            db.delete(existing_vote)
        else:
            existing_vote.vote_type = vote_type
    else:
        vote = Vote(post_id=post_id, user_id=user_id, vote_type=vote_type)
        db.add(vote)
        is_new_vote = True

    db.commit()

    # Get updated post with details to return
    updated_post = get_post_with_details(db, post_id, user_id)

    # Update points
    post = get_post(db, post_id)
    if post:
        point_service.update_points_for_vote(db=db, post_author_id=post.author_id)

    return updated_post