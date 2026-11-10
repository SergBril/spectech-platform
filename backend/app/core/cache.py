"""Async Redis cache with JSON serialization and metrics."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_redis_pool = None


async def _get_redis():
    """Get or create async Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        url = getattr(settings, "redis_url", "redis://localhost:6379/0")
        _redis_pool = aioredis.from_url(
            url, encoding="utf-8", decode_responses=True, socket_connect_timeout=2
        )
        await _redis_pool.ping()
        logger.info("Redis cache connected")
        return _redis_pool
    except Exception as e:
        logger.warning("Redis cache unavailable: %s", e)
        return None


async def cache_get(key: str) -> Any | None:
    """Get cached value. Returns None on miss or error."""
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        if raw is not None:
            from app.core.metrics import record_cache_hit

            record_cache_hit("redis")
            return json.loads(raw)
        from app.core.metrics import record_cache_miss

        record_cache_miss("redis")
        return None
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set cached value with TTL (default 5 min)."""
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.warning("Cache set failed for %s: %s", key, e)


async def cache_delete(key: str) -> None:
    """Delete cached value."""
    r = await _get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception:
        pass


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching pattern (e.g. 'analytics:*')."""
    r = await _get_redis()
    if r is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning("Cache delete_pattern failed for %s: %s", pattern, e)
