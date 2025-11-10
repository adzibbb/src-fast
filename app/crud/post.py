import logging
from math import ceil
from typing import List

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case

from app.models import Comment, User
from app.models.post import Post
from app.models.vote import Vote, VoteType
from app.schemas.post import PostCreate, PostUpdate
import uuid

from app.services.points_service import PointsService

logger = logging.getLogger(__name__)
point_service = PointsService()

def get_posts_count(db: Session, category: str = None, search: str = None):
    query = db.query(func.count(Post.id))
    
    if category:
        query = query.filter(Post.category == category)
    
    if search:
        query = query.filter(
            (Post.title.ilike(f"%{search}%")) | 
            (Post.content.ilike(f"%{search}%"))
        )
    
    return query.scalar()


def get_post(db: Session, post_id: uuid.UUID):
    return db.query(Post).filter(Post.id == post_id).first()


def create_post(db: Session, post: PostCreate, author_id: uuid.UUID):
    try:
        db_post = Post(**post.model_dump(), author_id=author_id)
        db.add(db_post)
        db.flush()  # Get ID but don't commit yet

        # Award points within same transaction
        point_service.update_points_for_post_creation(db, author_id)

        db.commit()
        db.refresh(db_post)
        return db_post
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating post: {e}")
        raise


def update_post(db: Session, post_id: uuid.UUID, post_update: PostUpdate):
    db_post = get_post(db, post_id)
    if not db_post:
        return None

    update_data = post_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_post, field, value)

    db.commit()
    db.refresh(db_post)
    return db_post


def delete_post(db: Session, post_id: uuid.UUID):
    db_post = get_post(db, post_id)
    if db_post:
        # ✅ Store author ID before deletion
        author_id = db_post.author_id
        
        db.delete(db_post)
        db.commit()
        
        # ✅ Recalculate points after deletion
        point_service.update_user_points(db, author_id)
        
    return db_post


def get_posts_with_details(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        category: str = None,
        sort_by: str = None,
        search: str = None,
        current_user_id: uuid.UUID = None
):

    # Base query with optimized joins
    query = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.comments).joinedload(Comment.author)
    )

    # Apply filters
    if category:
        query = query.filter(Post.category == category)

    if search:
        query = query.filter(
            (Post.title.ilike(f"%{search}%")) |
            (Post.content.ilike(f"%{search}%"))
        )

    # Subquery for vote counts
    from sqlalchemy import select, func, case
    vote_counts = select(
        Vote.post_id,
        func.sum(case((Vote.vote_type == VoteType.UPVOTE, 1), else_=0)).label('upvotes'),
        func.sum(case((Vote.vote_type == VoteType.DOWNVOTE, 1), else_=0)).label('downvotes')
    ).group_by(Vote.post_id).subquery()

    query = query.outerjoin(vote_counts, Post.id == vote_counts.c.post_id)

    # Subquery for comment counts
    comment_counts = select(
        Comment.post_id,
        func.count(Comment.id).label('comment_count')
    ).group_by(Comment.post_id).subquery()

    query = query.outerjoin(comment_counts, Post.id == comment_counts.c.post_id)

    # Subquery for current user vote
    current_user_vote = None
    if current_user_id:
        user_vote_subq = select(
            Vote.post_id,
            Vote.vote_type
        ).where(
            Vote.user_id == current_user_id
        ).subquery()

        query = query.outerjoin(user_vote_subq, Post.id == user_vote_subq.c.post_id)
        current_user_vote = user_vote_subq.c.vote_type

    # Handle sorting
    if sort_by == "newest":
        query = query.order_by(Post.created_at.desc())
    elif sort_by == "oldest":
        query = query.order_by(Post.created_at.asc())
    elif sort_by == "most-votes":
        query = query.order_by(
            (func.coalesce(vote_counts.c.upvotes, 0) - func.coalesce(vote_counts.c.downvotes, 0)).desc()
        )
    elif sort_by == "most-comments":
        query = query.order_by(func.coalesce(comment_counts.c.comment_count, 0).desc())
    else:
        query = query.order_by(Post.created_at.desc())

    # Execute query
    posts = query.offset(skip).limit(limit).all()

    # Format results efficiently
    formatted_posts = []
    for post in posts:
        upvotes = db.scalar(
            select(func.coalesce(vote_counts.c.upvotes, 0))
            .where(vote_counts.c.post_id == post.id)
        ) or 0

        downvotes = db.scalar(
            select(func.coalesce(vote_counts.c.downvotes, 0))
            .where(vote_counts.c.post_id == post.id)
        ) or 0

        current_vote = None
        if current_user_id:
            current_vote = db.scalar(
                select(Vote.vote_type)
                .where(Vote.post_id == post.id, Vote.user_id == current_user_id)
            )

        formatted_posts.append({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "category": post.category,
            "created_at": post.created_at,
            "author_id": post.author_id,
            "author": post.author,
            "upvote_count": upvotes,
            "downvote_count": downvotes,
            "comment_count": len(post.comments),
            "score": upvotes - downvotes,
            "current_user_vote": current_vote,
            "comments": post.comments  # Already loaded with authors
        })

    return formatted_posts


def get_user_posts_with_pagination_simple(
        db: Session,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        current_user_id: uuid.UUID = None
):
    """Simpler version that breaks down the queries"""

    # Count total posts
    total_count = db.query(Post).filter(Post.author_id == user_id).count()
    total_pages = ceil(total_count / page_size) if page_size > 0 else 1
    skip = (page - 1) * page_size

    # Get basic posts with author
    posts = db.query(Post).join(User, Post.author_id == User.id) \
        .filter(Post.author_id == user_id) \
        .order_by(Post.created_at.desc()) \
        .offset(skip) \
        .limit(page_size) \
        .all()

    # Enrich each post with additional data
    formatted_posts = []
    for post in posts:
        # Get vote counts
        vote_counts = db.query(
            func.sum(case((Vote.vote_type == VoteType.UPVOTE, 1), else_=0)).label('upvote_count'),
            func.sum(case((Vote.vote_type == VoteType.DOWNVOTE, 1), else_=0)).label('downvote_count')
        ).filter(Vote.post_id == post.id).first()

        upvote_count = vote_counts.upvote_count or 0 if vote_counts else 0
        downvote_count = vote_counts.downvote_count or 0 if vote_counts else 0

        # Get current user vote
        current_user_vote = None
        if current_user_id:
            user_vote = db.query(Vote.vote_type).filter(
                Vote.post_id == post.id,
                Vote.user_id == current_user_id
            ).first()
            current_user_vote = user_vote[0] if user_vote else None

        # Get comments with authors
        comments = db.query(Comment).join(User, Comment.author_id == User.id) \
            .filter(Comment.post_id == post.id) \
            .order_by(Comment.created_at.asc()) \
            .all()

        # Get comment count
        comment_count = len(comments)
        formatted_posts.append({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "category": post.category,
            "created_at": post.created_at,
            "author_id": post.author_id,
            "author": {
                "id": post.author.id,
                "username": post.author.username,
                "email": post.author.email,
                "display_name": post.author.display_name,
                "total_points": post.author.total_points,
                "created_at": post.author.created_at,
                "last_login_at": post.author.last_login_at
            },
            "upvote_count": upvote_count,
            "downvote_count": downvote_count,
            "comment_count": comment_count,
            "score": upvote_count - downvote_count,
            "current_user_vote": current_user_vote,
            "comments": [
                {
                    "id": comment.id,
                    "content": comment.content,
                    "created_at": comment.created_at,
                    "author": {
                        "id": comment.author.id,
                        "username": comment.author.username,
                        "email": comment.author.email,
                        "display_name": comment.author.display_name,
                        "total_points": comment.author.total_points,
                        "created_at": comment.author.created_at,
                        "last_login_at": post.author.last_login_at
                    },
                    "post_id": comment.post_id,
                    "author_id": comment.author_id
                }
                for comment in comments
            ]
        })

    return {
        "items": formatted_posts,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_next_page": page < total_pages,
        "has_previous_page": page > 1
    }


def get_posts_with_details_by_ids(db: Session, post_ids: List[uuid.UUID], current_user_id: uuid.UUID = None):
    """Get multiple posts with details by their IDs"""
    if not post_ids:
        return []


    # Create a subquery for current user vote
    current_user_vote_subquery = db.query(
        Vote.vote_type
    ).filter(
        Vote.post_id == Post.id,
        Vote.user_id == current_user_id
    ).scalar_subquery().correlate(Post)

    query = db.query(
        Post,
        func.sum(case((Vote.vote_type == VoteType.UPVOTE, 1), else_=0)).label('upvote_count'),
        func.sum(case((Vote.vote_type == VoteType.DOWNVOTE, 1), else_=0)).label('downvote_count'),
        func.count(Comment.id).label('comment_count'),
        func.coalesce(current_user_vote_subquery, None).label('current_user_vote'),
        User
    ).outerjoin(Vote, Vote.post_id == Post.id) \
        .outerjoin(Comment, Comment.post_id == Post.id) \
        .join(User, Post.author_id == User.id) \
        .filter(Post.id.in_(post_ids)) \
        .group_by(Post.id, User.id) \
        .order_by(Post.created_at.desc())

    results = query.all()

    # Format results
    formatted_posts = []
    for post, upvote_count, downvote_count, comment_count, current_user_vote, author in results:
        # Get comments for this post with their authors
        comments = db.query(Comment).join(User, Comment.author_id == User.id) \
            .filter(Comment.post_id == post.id) \
            .all()

        formatted_posts.append({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "category": post.category,
            "created_at": post.created_at,
            "author_id": post.author_id,
            "author": {
                "id": author.id,
                "username": author.username,
                "email": author.email,
                "display_name": author.display_name,
                "total_points": author.total_points,
                "created_at": author.created_at,
                "last_login_at": author.last_login_at
            },
            "upvote_count": upvote_count or 0,
            "downvote_count": downvote_count or 0,
            "comment_count": comment_count or 0,
            "score": (upvote_count or 0) - (downvote_count or 0),
            "current_user_vote": current_user_vote,
            "comments": [
                {
                    "id": comment.id,
                    "content": comment.content,
                    "created_at": comment.created_at,
                    "author": {
                        "id": comment.author.id,
                        "username": comment.author.username,
                        "email": comment.author.email,
                        "display_name": comment.author.display_name,
                        "total_points": comment.author.total_points,
                        "created_at": comment.author.created_at,
                        "last_login_at": comment.author.last_login_at
                    },
                    "post_id": comment.post_id,
                    "author_id": comment.author_id
                }
                for comment in comments
            ]
        })

    return formatted_posts


def get_post_with_details(db: Session, post_id: uuid.UUID, current_user_id: uuid.UUID = None):
    """Get a single post with full details"""
    posts = get_posts_with_details_by_ids(db, [post_id], current_user_id)
    return posts[0] if posts else None
