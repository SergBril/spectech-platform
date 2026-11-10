"""Synchronous Redis cache for sync FastAPI endpoints."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    """Get or create sync Redis client."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        from app.core.config import settings

        url = settings.redis_connection_url
        _redis_client = redis.from_url(
            url, decode_responses=True, socket_connect_timeout=2
        )
        _redis_client.ping()
        logger.info("Sync Redis cache connected")
        return _redis_client
    except Exception as e:
        logger.warning("Sync Redis cache unavailable: %s", e)
        return None


def cache_get(key: str) -> Any | None:
    """Get cached value. Returns None on miss or error."""
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
        if raw is not None:
            from app.core.metrics import record_cache_hit

            record_cache_hit("redis")
            return json.loads(raw)
        from app.core.metrics import record_cache_miss

        record_cache_miss("redis")
        return None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set cached value with TTL (default 5 min)."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.warning("Cache set failed for %s: %s", key, e)


def cache_delete(key: str) -> None:
    """Delete cached value."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        pass


def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching pattern."""
    r = _get_redis()
    if r is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=100)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning("Cache delete_pattern failed: %s", e)
