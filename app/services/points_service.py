from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.core.redis_service import redis_service
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.vote import Vote, VoteType
import uuid
import logging

logger = logging.getLogger(__name__)

class PointsService:
    def __init__(self):
        self.POINTS_CACHE_TTL = 3600

        # Point values for different actions
    POINTS_FOR_NEW_POST = 5
    POINTS_FOR_COMMENT_ON_POST = 2
    POINTS_FOR_UPVOTE = 1
    POINTS_FOR_DOWNVOTE = -1

    def update_user_points(self, db: Session, user_id: uuid.UUID):
        """Update total points for a user"""
        try:
            cache_key = f"user_points:{user_id}"

            # Check Redis cache first
            cached_points = redis_service.get(cache_key)
            if cached_points is not None:
                return int(cached_points)

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return

            # Calculate points from posts
            post_count = db.query(Post).filter(Post.author_id == user_id).count()
            post_points = post_count * self.POINTS_FOR_NEW_POST

            # Calculate points from comments on user's posts
            comment_count = db.query(Comment) \
                .join(Post, Comment.post_id == Post.id) \
                .filter(Post.author_id == user_id) \
                .count()
            comment_points = comment_count * self.POINTS_FOR_COMMENT_ON_POST

            # Calculate points from votes on user's posts
            vote_points_result = db.query(
                func.sum(
                    case(
                        (Vote.vote_type == VoteType.UPVOTE, self.POINTS_FOR_UPVOTE),
                        (Vote.vote_type == VoteType.DOWNVOTE, self.POINTS_FOR_DOWNVOTE),
                        else_=0
                    )
                )
            ).select_from(Vote) \
                .join(Post, Vote.post_id == Post.id) \
                .filter(Post.author_id == user_id) \
                .scalar()

            vote_points = vote_points_result or 0

            user.total_points = post_points + comment_points + vote_points
            db.commit()

            # Cache in Redis
            redis_service.set(cache_key, user.total_points, self.POINTS_CACHE_TTL)

            logger.info(f"Updated points for user {user_id}: {user.total_points}")

        except Exception as e:
            logger.error(f"Error updating user points: {e}")
            db.rollback()
            raise


    def calculate_points_for_post(self, post: Post) -> int:
        """Calculate points for a specific post"""
        vote_points = sum(
            self.POINTS_FOR_UPVOTE if vote.vote_type == VoteType.UPVOTE else self.POINTS_FOR_DOWNVOTE
            for vote in post.votes
        )
        comment_points = len(post.comments) * self.POINTS_FOR_COMMENT_ON_POST
        return vote_points + comment_points + self.POINTS_FOR_NEW_POST

    def update_points_for_post_creation(self, db: Session, user_id: uuid.UUID):
        """Update points when a user creates a new post"""
        self.update_user_points(db, user_id)

    def update_points_for_comment(self, db: Session, post_author_id: uuid.UUID):
        """Update points when someone comments on a user's post"""
        self.update_user_points(db, post_author_id)

    def update_points_for_vote(self, db: Session, post_author_id: uuid.UUID):
        """Update points when someone votes on a user's post"""
        self.update_user_points(db, post_author_id)



