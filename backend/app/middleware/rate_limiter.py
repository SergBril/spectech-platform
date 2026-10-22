import asyncio
"""Rate limiting middleware для защиты API."""
import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiter:
    """In-memory rate limiter with sliding window."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._failed_logins: dict[str, list[float]] = defaultdict(list)

    def check_rate(self, key: str, limit: int, window_seconds: int) -> bool:
        """Check if request is within rate limit. Returns True if allowed."""
        now = time.time()
        cutoff = now - window_seconds

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

        if len(self._requests[key]) >= limit:
            return False

        self._requests[key].append(now)
        return True

    def record_failed_login(self, ip: str) -> int:
        """Record failed login attempt. Returns current fail count."""
        now = time.time()
        cutoff = now - 900  # 15 min window
        self._failed_logins[ip] = [t for t in self._failed_logins[ip] if t > cutoff]
        self._failed_logins[ip].append(now)
        return len(self._failed_logins[ip])

    def is_blocked(self, ip: str, max_fails: int = 10) -> bool:
        """Check if IP is blocked due to too many failed logins."""
        now = time.time()
        cutoff = now - 900
        fails = [t for t in self._failed_logins[ip] if t > cutoff]
        return len(fails) >= max_fails


rate_limiter = RateLimiter()


class RedisRateLimiter:
    """Redis-backed rate limiter for production / multi-instance."""

    def __init__(self):
        self._redis = None
        self._connection_failed = False
        self._fallback = RateLimiter()

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        if self._connection_failed:
            return None
        try:
            import redis.asyncio as aioredis
            from app.core.config import settings
            url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            r = aioredis.from_url(url, encoding="utf-8", decode_responses=True, socket_connect_timeout=2)
            await asyncio.wait_for(r.ping(), timeout=2)
            self._redis = r
            logger.info("Redis rate limiter connected")
            return self._redis
        except Exception as e:
            logger.warning("Redis unavailable, fallback to in-memory: %s", e)
            self._connection_failed = True
            return None

    async def check_rate(self, key: str, limit: int, window_seconds: int) -> bool:
        r = await self._get_redis()
        if r is None:
            return self._fallback.check_rate(key, limit, window_seconds)
        try:
            now = time.time()
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()
            return results[2] <= limit
        except Exception as e:
            logger.error("Redis rate check failed: %s", e)
            return self._fallback.check_rate(key, limit, window_seconds)

    async def record_failed_login(self, ip: str) -> int:
        r = await self._get_redis()
        if r is None:
            return self._fallback.record_failed_login(ip)
        try:
            key = f"login_fails:{ip}"
            now = time.time()
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, now - 900)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, 900)
            results = await pipe.execute()
            return results[2]
        except Exception:
            return self._fallback.record_failed_login(ip)

    async def is_blocked(self, ip: str, max_fails: int = 10) -> bool:
        r = await self._get_redis()
        if r is None:
            return self._fallback.is_blocked(ip, max_fails)
        try:
            key = f"login_fails:{ip}"
            now = time.time()
            await r.zremrangebyscore(key, 0, now - 900)
            count = await r.zcard(key)
            return count >= max_fails
        except Exception:
            return self._fallback.is_blocked(ip, max_fails)


redis_rate_limiter = RedisRateLimiter()

class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    # Endpoints with custom limits: (path_prefix, limit, window_seconds)
    CUSTOM_LIMITS = [
        ("/api/v1/auth/login", 5, 60),       # 5 logins per minute
        ("/api/v1/auth/register", 3, 300),   # 3 registrations per 5 min
        ("/api/v1/max/webhook", 100, 60),    # Webhook: higher limit
    ]
    DEFAULT_LIMIT = 120  # 120 requests per minute
    DEFAULT_WINDOW = 60

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Use Redis if available, fallback to in-memory
        rl = redis_rate_limiter

        # Check brute force block
        if "/auth/login" in path:
            blocked = await rl.is_blocked(client_ip)
            if blocked:
                logger.warning("Blocked login from %s (too many failures)", client_ip)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Try again in 15 minutes."
                )

        # Determine rate limit
        limit = self.DEFAULT_LIMIT
        window = self.DEFAULT_WINDOW
        for prefix, l, w in self.CUSTOM_LIMITS:
            if path.startswith(prefix):
                limit = l
                window = w
                break

        # Check rate
        key = f"{client_ip}:{path}"
        allowed = await rl.check_rate(key, limit, window)
        if not allowed:
            logger.warning("Rate limit exceeded: %s (%d/%ds)", key, limit, window)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {limit} requests per {window}s."
            )

        response = await call_next(request)
        return response


