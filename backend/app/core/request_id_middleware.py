"""Middleware для добавления Request ID ко всем запросам."""

import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Добавляет уникальный Request ID к каждому запросу."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Генерируем или получаем Request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]

        # Привязываем к контексту structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        logger = structlog.get_logger("spectech.api")

        # Логируем запрос
        logger.info(
            "REQUEST",
            user_agent=request.headers.get("user-agent", "unknown")[:50],
        )

        try:
            # Выполняем запрос
            response = await call_next(request)

            # Логируем ответ
            logger.info(
                "RESPONSE",
                status_code=response.status_code,
            )

            # Добавляем Request ID в заголовки ответа
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Логируем ошибку
            logger.error(
                "REQUEST_ERROR",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise
