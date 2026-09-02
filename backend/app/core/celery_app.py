"""Конфигурация Celery приложения."""
from celery import Celery

# Создаём Celery instance
celery_app = Celery(
    "spectech",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    # Явно указываем только существующие модули с задачами
    include=["app.tasks.pdf_tasks", "app.tasks.email_tasks", "app.tasks.telematics_tasks",],
)

# Конфигурация
celery_app.conf.update(
    # Сериализация
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Таймзоны
    timezone="UTC",
    enable_utc=True,
    
    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Rate limiting
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Результат задач
    result_expires=3600,  # 1 час
    
    # Логирование
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)