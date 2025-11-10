# core/rate_limiting.py
import time
import logging
from typing import Optional
from app.core.redis_service import redis_service

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    def __init__(self, redis_service):
        self.redis = redis_service

    async def is_rate_limited(
            self,
            identifier: str,
            max_requests: int,
            window_seconds: int
    ) -> bool:
        """Check if request is rate limited using Redis"""
        key = f"rate_limit:{identifier}"

        try:
            # Get current count
            current = self.redis.get(key)
            current_count = int(current) if current else 0

            # If over limit, return True
            if current_count >= max_requests:
                return True

            # Increment counter
            if current_count == 0:
                # First request in window, set with expiration
                self.redis.set(key, 1, window_seconds)
            else:
                # Increment existing counter
                self.redis.incr(key)

            return False

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open - don't block requests if Redis fails
            return False

    async def get_remaining_attempts(
            self,
            identifier: str,
            max_requests: int
    ) -> int:
        """Get remaining attempts"""
        try:
            key = f"rate_limit:{identifier}"
            current = self.redis.get(key)
            current_count = int(current) if current else 0
            return max(0, max_requests - current_count)
        except Exception as e:
            logger.error(f"Get remaining attempts error: {e}")
            return max_requests


# Initialize rate limiter
rate_limiter = RedisRateLimiter(redis_service)