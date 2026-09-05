"""Структурированное логирование в JSON формате."""

import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Форматтер который выводит логи в JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Добавляем request_id если есть
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        # Добавляем дополнительные поля
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level: str = "INFO"):
    """Настраивает корневой логгер с JSON-форматом."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))

    # Удаляем старые хэндлеры
    logger.handlers.clear()

    # Создаём хэндлер для stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Отключаем многословные логи
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер с указанным именем."""
    return logging.getLogger(f"spectech.{name}")
