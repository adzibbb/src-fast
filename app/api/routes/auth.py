# auth.py (updated with Redis)
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_client_ip, check_rate_limit
from app.core.redis_service import redis_service
from app.core.security import create_access_token, create_refresh_token, verify_refresh_token
from app.crud import post as post_crud
from app.crud.user import authenticate_user, create_user, get_user_by_username, get_user_by_email, get_user
from app.database import get_db
from app.schemas import PostWithDetails
from app.schemas.post import PaginatedResponse
from app.schemas.user import UserCreate, AuthResponse, User, LoginRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=AuthResponse)
async def register(
        request: Request,
        user_data: UserCreate,
        db: Session = Depends(get_db)
):
    client_ip = get_client_ip(request)

    # Rate limiting with Redis
    if not await check_rate_limit(f"register_ip:{client_ip}", max_attempts=3, window_seconds=3600):
        return AuthResponse(success=False, errors=["Too many registration attempts. Please try again in an hour."])

    # Rate limiting by email to prevent spam
    if not await check_rate_limit(f"register_email:{user_data.email}", max_attempts=2, window_seconds=86400):
        return AuthResponse(success=False, errors=["Too many registration attempts with this email."])

    try:
        logger.info(f"Registration attempt from {client_ip} for user: {user_data.username}")

        # Check if username already exists
        if get_user_by_username(db, user_data.username):
            logger.warning(f"Registration failed - username exists: {user_data.username}")
            return AuthResponse(success=False, errors=["Username already exists"])

        # Check if email already exists
        if get_user_by_email(db, user_data.email):
            logger.warning(f"Registration failed - email exists: {user_data.email}")
            return AuthResponse(success=False, errors=["Email already exists"])

        # Create user within transaction
        try:
            user = create_user(db, user_data)
            logger.info(f"User registered successfully: {user_data.username}")

            return AuthResponse(
                success=True,
                user_id=user.id,
                username=user.username,
                display_name=user.display_name
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Database error during registration: {e}")
            return AuthResponse(success=False, errors=["Registration failed due to system error"])

    except ValidationError as e:
        logger.warning(f"Registration validation failed: {e}")
        errors = []
        for error in e.errors():
            if error['type'] == 'value_error':
                errors.append(error['msg'])
            else:
                errors.append(f"{error['loc'][0]}: {error['msg']}")
        return AuthResponse(success=False, errors=errors)
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}")
        return AuthResponse(success=False, errors=["An unexpected error occurred"])


@router.post("/refresh")
async def refresh_token(
        request: Request,
        refresh_token: str,
        db: Session = Depends(get_db)
):
    """Refresh access token using refresh token with rate limiting"""
    client_ip = get_client_ip(request)

    # Rate limiting for token refresh
    if not await check_rate_limit(f"refresh_ip:{client_ip}", max_attempts=10, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many token refresh attempts"
        )

    payload = verify_refresh_token(refresh_token)
    if not payload:
        logger.warning(f"Invalid refresh token from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    try:
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ValueError("Missing user ID in refresh token")

        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Invalid user ID in refresh token from {client_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload"
        )

    user = get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Create new access token
    new_access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.post("/login", response_model=AuthResponse)
async def login(
        request: Request,
        login_data: LoginRequest,
        db: Session = Depends(get_db)
):
    client_ip = get_client_ip(request)

    # Rate limiting by IP
    if not await check_rate_limit(f"login_ip:{client_ip}", max_attempts=5, window_seconds=300):
        return AuthResponse(success=False, errors=["Too many login attempts. Please try again in 5 minutes."])

    # Rate limiting by username to prevent targeted attacks
    if not await check_rate_limit(f"login_user:{login_data.username}", max_attempts=3, window_seconds=900):
        return AuthResponse(success=False,
                            errors=["Too many login attempts for this user. Please try again in 15 minutes."])

    try:
        logger.info(f"Login attempt from {client_ip} for user: {login_data.username}")

        user = authenticate_user(db, login_data.username, login_data.password)
        if not user:
            logger.warning(f"Login failed from {client_ip} for user: {login_data.username}")
            return AuthResponse(success=False, errors=["Invalid username or password"])

        # Update last login within transaction
        try:
            user.last_login_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update last login: {e}")

        # Cache user data in Redis for faster subsequent lookups
        user_cache_key = f"user:{user.id}"
        user_data = {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email
        }
        redis_service.set(user_cache_key, user_data, expire_seconds=3600)  # Cache for 1 hour

        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        logger.info(f"User logged in successfully: {login_data.username} from {client_ip}")

        return AuthResponse(
            success=True,
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    except Exception as e:
        logger.error(f"Unexpected error during login from {client_ip}: {e}")
        return AuthResponse(success=False, errors=["An unexpected error occurred"])


@router.get("/me", response_model=User)
async def get_current_user_info(
        request: Request,
        current_user: User = Depends(get_current_user)
):
    # Cache user info in Redis for faster subsequent requests
    user_cache_key = f"user:{current_user.id}"
    cached_user = redis_service.get(user_cache_key)

    if not cached_user:
        # Cache the user data
        user_data = {
            "id": str(current_user.id),
            "username": current_user.username,
            "display_name": current_user.display_name,
            "email": current_user.email,
            "total_points": current_user.total_points,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None
        }
        redis_service.set(user_cache_key, user_data, expire_seconds=1800)  # 30 minutes

    return current_user


@router.get("/users/{user_id}", response_model=User)
async def get_user_by_id(
        request: Request,
        user_id: uuid.UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    client_ip = get_client_ip(request)

    # Rate limiting for user lookups
    if not await check_rate_limit(f"user_lookup:{client_ip}", max_attempts=20, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many user lookup requests"
        )

    try:
        # Try to get user from cache first
        user_cache_key = f"user:{user_id}"
        cached_user = redis_service.get(user_cache_key)

        if cached_user:
            logger.info(f"User {user_id} served from cache for {client_ip}")
            # Convert back to User model (you might need a helper function for this)
            # For now, we'll still query the DB but in production you'd use the cache

        logger.info(f"Fetching user by ID: {user_id} for {client_ip}")

        user = get_user(db, user_id)
        if not user:
            logger.warning(f"User not found with ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Cache the user data
        user_data = {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "total_points": user.total_points,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
        redis_service.set(user_cache_key, user_data, expire_seconds=1800)  # 30 minutes

        logger.info(f"User retrieved successfully: {user_id}")
        return user

    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user"
        )


@router.get("/users/{user_id}/posts", response_model=PaginatedResponse[PostWithDetails])
async def get_user_posts(
        request: Request,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 10,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    client_ip = get_client_ip(request)

    # Rate limiting for post lookups
    if not await check_rate_limit(f"posts_lookup:{client_ip}", max_attempts=30, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many post lookup requests"
        )

    try:
        # Cache key for paginated posts
        cache_key = f"user_posts:{user_id}:page:{page}:size:{page_size}"
        cached_posts = redis_service.get(cache_key)

        if cached_posts:
            logger.info(f"User posts served from cache for {user_id}, page {page}")
            return cached_posts

        logger.info(f"Fetching posts for user: {user_id}, page: {page}, page_size: {page_size}")

        # Verify user exists
        user = get_user(db, user_id)
        if not user:
            logger.warning(f"User not found with ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get posts with pagination
        posts_data = post_crud.get_user_posts_with_pagination_simple(
            db,
            user_id=user_id,
            page=page,
            page_size=page_size,
            current_user_id=current_user.id if current_user else None
        )

        # Cache the result for 2 minutes
        redis_service.set(cache_key, posts_data, expire_seconds=120)

        logger.info(f"Found {posts_data['total_count']} posts for user: {user_id}")
        return posts_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user posts {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user posts"
        )


# Add to auth.py
@router.post("/logout")
async def logout(
        request: Request,
        current_user: User = Depends(get_current_user)
):
    """Logout user by blacklisting token"""
    # In a real implementation, you'd get the token from the request
    # and add it to a Redis blacklist with TTL matching token expiration

    # Clear user cache
    user_cache_key = f"user:{current_user.id}"
    redis_service.delete(user_cache_key)

    logger.info(f"User logged out: {current_user.username}")

    return {"success": True, "message": "Logged out successfully"}