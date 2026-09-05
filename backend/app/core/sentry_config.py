"""Конфигурация Sentry для отслеживания ошибок."""

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.core.config import settings


def init_sentry():
    """Инициализирует Sentry SDK с интеграциями."""
    if not settings.sentry_dsn:
        print("⚠️  Sentry DSN не настроен, пропускаем инициализацию")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,  # 10% запросов для performance monitoring
        profiles_sample_rate=0.1,  # 10% для profiling
        # Интеграции
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(
                level=None,  # Не логируем обычные логи в Sentry
                event_level="ERROR",  # Только ERROR и выше как события
            ),
        ],
        # Фильтрация
        send_default_pii=True,  # Отправлять PII (IP, user agent)
        attach_stacktrace=True,  # Прикреплять stacktrace к логам
        # Before send callback для фильтрации
        before_send=before_send_callback,
    )

    print(f"✅ Sentry инициализирован для environment: {settings.environment}")


def before_send_callback(event, hint):
    """Фильтрует события перед отправкой в Sentry."""
    # Игнорируем определённые ошибки
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]

        # Игнорируем HTTPException (это нормальное поведение)
        if exc_type.__name__ == "HTTPException":
            return None

        # Игнорируем ValidationError (ошибки валидации)
        if exc_type.__name__ == "ValidationError":
            return None

    return event
