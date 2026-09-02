"""Middleware для логирования запросов и замера времени."""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.metrics_service import record_request

logger = logging.getLogger("spectech.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Логирует каждый запрос и записывает метрики."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()
        
        # Пропускаем health-check чтобы не засорять логи
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
            
            # Логируем медленные запросы (>500мс)
            if duration_ms > 500:
                logger.warning(
                    "SLOW REQUEST: %s %s -> %s (%.1fms)",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                )
            else:
                logger.info(
                    "%s %s -> %s (%.1fms)",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                )
            
            # Добавляем заголовок с временем обработки
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
                "REQUEST ERROR: %s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                str(exc),
                duration_ms,
            )
            raise