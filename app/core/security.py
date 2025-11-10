# security.py
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Increased for production (default is 12, but explicit is good)
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Securely verify password with timing attack protection"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        # Still return False to prevent timing attacks
        pwd_context.dummy_verify()
        return False


def get_password_hash(password: str) -> str:
    """Get password hash with work factor"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token with proper claims"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Standard JWT claims
    now = datetime.now(timezone.utc)
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,  # Not before
        "type": "access",
        "iss": settings.JWT_ISSUER,  # Token issuer
        "aud": settings.JWT_AUDIENCE,  # Token audience
    })

    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Token creation error: {e}")
        raise


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token with proper validation"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER
        )

        if payload.get("type") != "access":
            logger.warning("Invalid token type")
            return None

        # Additional validation
        if payload.get("nbf") and time.time() < payload["nbf"]:
            logger.warning("Token not yet valid")
            return None

        return payload
    except JWTError as e:
        logger.debug(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def create_refresh_token(data: dict) -> str:
    """Create refresh token with longer expiration"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_refresh_token(token: str) -> Optional[dict]:
    """Verify refresh token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER
        )

        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


# Redis-based token blacklist for production
class TokenBlacklist:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.prefix = "blacklist:"

    def add_token(self, token: str, expire_seconds: int = 3600):
        """Add token to blacklist with TTL"""
        try:
            import hashlib
            # Store hash of token to save space
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"{self.prefix}{token_hash}"
            self.redis.setex(key, expire_seconds, "1")
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")

    def is_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        try:
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            key = f"{self.prefix}{token_hash}"
            return self.redis.exists(key)
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            return False  # Fail open for availability

# Initialize with Redis client
# token_blacklist = TokenBlacklist(redis_client)