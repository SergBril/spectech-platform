"""Одноразовые короткоживущие ticket'ы для WebSocket-аутентификации.

Замена сессионного JWT в ?token= (долгоживущий токен в URL утекал
в логи nginx, историю браузера и Referer).

Хранилище — ТОЛЬКО Redis: одноразовость на in-memory не работает при
нескольких воркерах (ticket можно использовать повторно на другом воркере).
Redis недоступен — ошибки пробрасываются, вызывающий код отвечает
fail-closed (503 / close 4002). НЕ переиспользовать in-memory fallback
из middleware/rate_limiter.py.
"""

import logging
import secrets

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("spectech.ws.tickets")

TICKET_TTL_SECONDS = 60
_KEY_PREFIX = "ws_ticket:"

_client = None


async def _get_redis():
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_connection_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client


async def issue_ticket(user_id: int) -> str:
    """Выдаёт одноразовый ticket: SET ws_ticket:<ticket> <user_id> EX 60 NX."""
    ticket = secrets.token_urlsafe(32)
    r = await _get_redis()
    ok = await r.set(
        f"{_KEY_PREFIX}{ticket}", str(user_id), ex=TICKET_TTL_SECONDS, nx=True
    )
    if not ok:
        # коллизия token_urlsafe(32) практически невозможна — fail-closed
        raise RuntimeError("WS ticket collision")
    return ticket


async def consume_ticket(ticket: str) -> int | None:
    """Атомарно забирает ticket (GETDEL — один запрос, безопасно между воркерами).

    None — ticket не найден, истёк или уже использован.
    """
    r = await _get_redis()
    value = await r.getdel(f"{_KEY_PREFIX}{ticket}")
    return int(value) if value is not None else None
