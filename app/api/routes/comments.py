import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.crud import comment as comment_crud
from app.crud import post as post_crud
from app.database import get_db
from app.models.user import User
from app.schemas.comment import Comment, CommentCreate
from app.services.notification_service import NotificationService
from app.services.points_service import PointsService
from app.websocket.hub import manager
from app.schemas.notification import NotificationCreate, NotificationType

router = APIRouter()

def get_points_service() -> PointsService:
    return PointsService()

def get_notification_service() -> NotificationService:
    return NotificationService()


@router.post("/{post_id}/comments", response_model=Comment)
async def create_comment(
        post_id: uuid.UUID,
        comment: CommentCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        points_service: PointsService = Depends(),
        notification_service: NotificationService = Depends()
):
    # Check if post exists
    db_post = post_crud.get_post(db, post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Create comment
    db_comment = comment_crud.create_comment(
        db=db,
        comment=comment,
        post_id=post_id,
        author_id=current_user.id
    )

    # Send notification to post author if not the commenter
    if db_post.author_id != current_user.id:
        notification_data = NotificationCreate(
            title="New comment on your post",
            message=f"{current_user.username} commented on your post: {db_post.title}",
            type=NotificationType.COMMENT,  # This should match your NotificationType enum
            user_id=db_post.author_id,
            related_post_id=post_id,
            triggered_by_user_id=current_user.id
        )
        await notification_service.create_notification(db, notification_data)

    # Update post author's points
    points_service.update_user_points(db, db_post.author_id)

    # Notify all clients via WebSocket
    await manager.broadcast({
        "type": "receive_post_update",
        "postId": str(post_id)
    })
    await manager.broadcast({
        "type": "receive_leaderboard_update"
    })

    return db_comment


@router.delete("/comments/{comment_id}")
async def delete_comment(
        comment_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        points_service: PointsService = Depends()
):
    db_comment = comment_crud.get_comment(db, comment_id)
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only allow author or admin to delete
    if db_comment.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    post_author_id = db_comment.post.author_id

    # Delete comment
    comment_crud.delete_comment(db, comment_id)

    # Update post author's points
    points_service.update_points_for_comment(db, post_author_id)

    return {"message": "Comment deleted successfully"}
