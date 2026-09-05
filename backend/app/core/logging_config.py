"""Конфигурация structured logging с structlog."""

import logging
import sys
from typing import Any

import structlog


def setup_logging(log_level: str = "INFO"):
    """Настраивает structured logging с JSON форматом."""

    # Определяем формат в зависимости от окружения
    import os

    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    # Общие processors
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,  # Добавляем context vars
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),  # ISO формат времени
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_production:
        # Production: JSON формат
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: цветной консольный вывод
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            pad_event=35,
        )

    # Конфигурируем structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Конфигурируем стандартный logging
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Уменьшаем шум от библиотек
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    print(
        f"✅ Structured logging настроен (level={log_level}, format={'JSON' if is_production else 'console'})"
    )


def get_logger(name: str = "spectech.app") -> structlog.stdlib.BoundLogger:
    """Возвращает logger с привязкой к контексту."""
    return structlog.get_logger(name)
