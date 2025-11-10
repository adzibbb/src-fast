# core/redis_service.py
import redis
import json
import logging
from typing import Optional, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    def __init__(self):
        self.redis_client = None
        self._connect()

    def _connect(self):
        """Connect to Redis with error handling"""
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                # ssl=settings.REDIS_SSL,
                decode_responses=True,  # Automatically decode responses to strings
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
            self.redis_client = None

    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False

    def set(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        """Set key-value pair with optional expiration"""
        if not self.is_connected():
            return False

        try:
            # Convert value to JSON string for complex objects
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)

            if expire_seconds:
                return self.redis_client.setex(key, expire_seconds, value)
            else:
                return self.redis_client.set(key, value)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key"""
        if not self.is_connected():
            return default

        try:
            value = self.redis_client.get(key)
            if value is None:
                return default

            # Try to parse as JSON, return as string if it fails
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return default

    def delete(self, key: str) -> bool:
        """Delete key"""
        if not self.is_connected():
            return False

        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.is_connected():
            return False

        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment key by amount"""
        if not self.is_connected():
            return None

        try:
            return self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis incr error: {e}")
            return None


# Global Redis service instance
redis_service = RedisService()