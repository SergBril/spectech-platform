"""Middleware для логирования и генерации request_id."""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.metrics_service import record_request

logger = logging.getLogger("spectech.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Логирует каждый запрос с request_id для трассировки."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Генерируем уникальный ID для запроса
        request_id = str(uuid.uuid4())[:8]
        start = time.time()

        # Добавляем request_id в контекст лога
        logging.LoggerAdapter(logger, {"request_id": request_id})

        # Пропускаем health-check
        if request.url.path == "/health":
            return await call_next(request)

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start) * 1000

            record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Логируем
            if duration_ms > 500:
                logger.warning(
                    "SLOW REQUEST",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )
            else:
                logger.info(
                    "REQUEST",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )

            # Добавляем request_id в заголовки ответа
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
            return response

        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                duration_ms=duration_ms,
            )
            logger.error(
                "REQUEST ERROR",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(exc),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True
            )
            raise