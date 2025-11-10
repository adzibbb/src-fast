from sqlalchemy.orm import Session

from app.models import Post
from app.models.comment import Comment
from app.schemas.comment import CommentCreate
import uuid

from app.services.points_service import PointsService

point_service = PointsService()

def get_comment(db: Session, comment_id: uuid.UUID):
    return db.query(Comment).filter(Comment.id == comment_id).first()

def get_comments_by_post(db: Session, post_id: uuid.UUID, skip: int = 0, limit: int = 100):
    return db.query(Comment)\
        .filter(Comment.post_id == post_id)\
        .offset(skip)\
        .limit(limit)\
        .all()


def create_comment(db: Session, comment: CommentCreate, post_id: uuid.UUID, author_id: uuid.UUID):
    db_comment = Comment(
        content=comment.content,
        post_id=post_id,
        author_id=author_id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    # Get the post to find its author
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        # Give points to the POST author, not comment author
        point_service.update_points_for_comment(db=db, post_author_id=post.author_id)

    return db_comment

def delete_comment(db: Session, comment_id: uuid.UUID):
    db_comment = get_comment(db, comment_id)
    if db_comment:
        post_author_id = db_comment.post.author_id
    	
        db.delete(db_comment)
        db.commit()
        
        point_service.update_user_points(db, post_author_id)
    return db_comment
