"""Глобальные обработчики ошибок."""
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger("spectech.errors")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обрабатывает ошибки валидации Pydantic."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        "VALIDATION ERROR",
        extra={
            "path": request.url.path,
            "errors": errors,
        }
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Ошибка валидации данных",
            "details": errors,
        },
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Обрабатывает ошибки базы данных."""
    logger.error(
        "DATABASE ERROR",
        extra={
            "path": request.url.path,
            "error": str(exc),
        },
        exc_info=True
    )

    # Определяем тип ошибки
    if isinstance(exc, IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "integrity_error",
                "message": "Нарушение целостности данных (возможно, дубликат)",
            },
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "database_error",
            "message": "Ошибка базы данных",
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Обрабатывает все необработанные ошибки."""
    logger.error(
        "UNHANDLED ERROR",
        extra={
            "path": request.url.path,
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "Внутренняя ошибка сервера",
        },
    )