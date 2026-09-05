"""Настройка Celery для тестов — синхронное выполнение."""

import pytest

from app.core.celery_app import celery_app


@pytest.fixture(autouse=True)
def celery_eager_mode():
    """
    В тестах все Celery задачи выполняются синхронно (без worker).
    .delay() и .apply_async() превращаются в обычные вызовы функций.
    """
    original_always_eager = celery_app.conf.task_always_eager
    original_eager_propagates = celery_app.conf.task_eager_propagates

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    yield

    # Восстанавливаем оригинальные настройки
    celery_app.conf.task_always_eager = original_always_eager
    celery_app.conf.task_eager_propagates = original_eager_propagates
