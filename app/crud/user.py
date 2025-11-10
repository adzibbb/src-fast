# crud/user.py
import logging
from pydantic import EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import uuid

from app.models import Post
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    """Get user by ID with error handling"""
    try:
        return db.query(User).filter(User.id == user_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting user {user_id}: {e}")
        return None


def get_user_by_username(db: Session, username: str) -> User | None:
    """Get user by username with case-insensitive search"""
    try:
        return db.query(User).filter(func.lower(User.username) == func.lower(username)).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting user by username {username}: {e}")
        return None


def get_user_by_email(db: Session, email: EmailStr) -> User | None:
    """Get user by email with case-insensitive search"""
    try:
        return db.query(User).filter(func.lower(User.email) == func.lower(email)).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting user by email {email}: {e}")
        return None


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Get users with pagination and limits"""
    try:
        # Prevent excessive queries
        if limit > 1000:
            limit = 1000
        if skip < 0:
            skip = 0

        return db.query(User).offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting users: {e}")
        return []


def create_user(db: Session, user: UserCreate) -> User:
    """Create user with transaction safety"""
    try:
        # Check for existing user in transaction
        if get_user_by_username(db, user.username):
            raise ValueError("Username already exists")

        if get_user_by_email(db, user.email):
            raise ValueError("Email already exists")

        hashed_password = get_password_hash(user.password)
        db_user = User(
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            hashed_password=hashed_password
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        logger.info(f"User created successfully: {user.username}")
        return db_user

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating user {user.username}: {e}")
        raise ValueError("User already exists") from e
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating user {user.username}: {e}")
        raise ValueError("Database error occurred") from e
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating user {user.username}: {e}")
        raise


def update_user(db: Session, user_id: uuid.UUID, user_update: UserUpdate) -> User | None:
    """Update user with validation and transaction safety"""
    try:
        db_user = get_user(db, user_id)
        if not db_user:
            return None

        update_data = user_update.model_dump(exclude_unset=True, exclude_none=True)

        # Validate email uniqueness if being updated
        if "email" in update_data and update_data["email"] != db_user.email:
            existing_user = get_user_by_email(db, update_data["email"])
            if existing_user and existing_user.id != user_id:
                raise ValueError("Email already exists")

        # Validate username uniqueness if being updated
        if "username" in update_data and update_data["username"] != db_user.username:
            existing_user = get_user_by_username(db, update_data["username"])
            if existing_user and existing_user.id != user_id:
                raise ValueError("Username already exists")

        # Handle password update
        if "password" in update_data:
            if not update_data["password"] or len(update_data["password"]) < 8:
                raise ValueError("Password must be at least 8 characters")
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        # Update fields
        for field, value in update_data.items():
            if hasattr(db_user, field):
                setattr(db_user, field, value)

        db.commit()
        db.refresh(db_user)

        logger.info(f"User updated successfully: {user_id}")
        return db_user

    except (ValueError, IntegrityError) as e:
        db.rollback()
        logger.warning(f"Validation error updating user {user_id}: {e}")
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating user {user_id}: {e}")
        raise ValueError("Database error occurred") from e


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Authenticate user with security considerations"""
    try:
        user = get_user_by_username(db, username)
        if not user:
            # Use constant-time comparison to prevent timing attacks
            verify_password("dummy_password", get_password_hash("dummy_password"))
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user
    except SQLAlchemyError as e:
        logger.error(f"Database error during authentication for {username}: {e}")
        return None


def get_leaderboard(db: Session, limit: int = 50) -> list[dict]:
    """Get leaderboard with performance optimization"""
    try:
        # Validate limit
        if limit > 1000:
            limit = 1000
        if limit < 1:
            limit = 50

        from sqlalchemy import func
        from app.models.post import Post

        # Optimized query with proper joins
        results = db.query(
            User.id,
            User.username,
            User.display_name,
            User.total_points,
            User.created_at,
            func.count(Post.id).label('post_count')
        ).outerjoin(Post, User.id == Post.author_id) \
            .group_by(User.id) \
            .order_by(User.total_points.desc(), User.created_at.asc()) \
            .limit(limit) \
            .all()

        # Convert to list of dictionaries efficiently
        leaderboard_data = []
        for row in results:
            leaderboard_data.append({
                "id": row.id,
                "username": row.username,
                "display_name": row.display_name,
                "total_points": row.total_points or 0,
                "post_count": row.post_count or 0,
                "created_at": row.created_at
            })

        return leaderboard_data

    except SQLAlchemyError as e:
        logger.error(f"Database error getting leaderboard: {e}")
        return []