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
    # Проверяем что DSN настроен и не пустой
    if not settings.sentry_dsn or settings.sentry_dsn.strip() == "":
        print("⚠️  Sentry DSN не настроен, пропускаем инициализацию")
        return

    # Валидация формата DSN
    if "your-dsn" in settings.sentry_dsn or "project-id" in settings.sentry_dsn:
        print("⚠️  Sentry DSN содержит placeholder, пропускаем инициализацию")
        return

    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                CeleryIntegration(),
                RedisIntegration(),
                LoggingIntegration(
                    level=None,
                    event_level="ERROR",
                ),
            ],
            send_default_pii=True,
            attach_stacktrace=True,
            before_send=before_send_callback,
        )

        print(f"✅ Sentry инициализирован для environment: {settings.environment}")

    except Exception as e:
        # Graceful degradation: если Sentry не работает, приложение всё равно запускается
        print(f"⚠️  Не удалось инициализировать Sentry: {type(e).__name__}: {e}")
        print("   Приложение продолжит работу без error tracking")


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
