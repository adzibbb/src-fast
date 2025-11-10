# dependencies.py
import logging
import time
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.rate_limiting import rate_limiter
from app.database import get_db
from app.core.security import verify_token
from app.crud.user import get_user
import uuid

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)  # Don't auto-raise exceptions

# Rate limiting storage (use Redis in production)
_login_attempts = {}


async def rate_limit_check(identifier: str, max_attempts: int = 5, window: int = 300) -> bool:
    """Rate limiting using Redis"""
    return not await rate_limiter.is_rate_limited(identifier, max_attempts, window)

async def check_rate_limit(identifier: str, max_attempts: int, window_seconds: int) -> bool:
    """Check rate limit using Redis"""
    return not await rate_limiter.is_rate_limited(identifier, max_attempts, window_seconds)

def get_client_ip(request: Request) -> str:
    """Get client IP for rate limiting"""
    if request.client and hasattr(request.client, 'host'):
        return request.client.host
    return request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()

def get_current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
):
    # Rate limiting by IP
    client_ip = get_client_ip(request)
    if not rate_limit_check(f"auth_{client_ip}", 10, 300):  # 10 attempts per 5 minutes
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts",
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Basic token validation
    if not token or len(token) > 2000:  # Reasonable token length limit
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        )

    payload = verify_token(token)
    if payload is None:
        logger.warning(f"Invalid token from IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_str = payload.get("sub")
        if not user_id_str:
            logger.warning("Missing user ID in token payload")
            raise ValueError("Missing user ID in token")

        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Invalid user ID in token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = get_user(db, user_id)
    if user is None:
        logger.warning(f"User not found for token: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Check if user is active (if you add this field)
    if hasattr(user, 'is_active') and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
        )

    logger.info(f"User authenticated: {user.username} from {client_ip}")
    return user


async def get_current_user_ws(token: str, db: Session):
    """WebSocket authentication with rate limiting"""
    try:
        # Basic token validation
        if not token or len(token) > 2000:
            logger.warning("WebSocket: Invalid token length")
            return None

        payload = verify_token(token)
        if payload is None:
            logger.warning("WebSocket: Invalid token")
            return None

        # Token expiration check
        current_time = time.time()
        exp = payload.get("exp")
        if exp and current_time > exp:
            logger.warning("WebSocket: Token expired")
            return None

        # Issued at check (optional - prevent token reuse)
        iat = payload.get("iat")
        if iat and current_time - iat > 86400:  # Token older than 24 hours
            logger.warning("WebSocket: Token too old")
            return None

        try:
            user_id_str = payload.get("sub")
            if not user_id_str:
                logger.warning("WebSocket: Missing user ID in token")
                return None

            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"WebSocket: Invalid user ID format: {e}")
            return None

        user = get_user(db, user_id)
        if not user:
            logger.warning(f"WebSocket: User not found {user_id}")
            return None

        logger.info(f"WebSocket authentication successful for user: {user.username}")
        return user

    except Exception as e:
        logger.error(f"WebSocket token verification error: {e}")
        return None