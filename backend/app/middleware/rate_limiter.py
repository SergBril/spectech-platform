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

        # Check brute force block
        if "/auth/login" in path and rate_limiter.is_blocked(client_ip):
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
        if not rate_limiter.check_rate(key, limit, window):
            logger.warning("Rate limit exceeded: %s (%d/%ds)", key, limit, window)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {limit} requests per {window}s."
            )

        response = await call_next(request)
        return response
