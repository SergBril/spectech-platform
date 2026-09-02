"""Конфигурация Celery приложения с периодическими задачами."""
from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "spectech",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    include=[
        "app.tasks.pdf_tasks",
        "app.tasks.email_tasks",
        "app.tasks.telematics_tasks",
        "app.tasks.scheduled_tasks",
    ],
)

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
    result_expires=3600,
    
    # Логирование
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

# ========================================================
# === ПЕРИОДИЧЕСКИЕ ЗАДАЧИ (Celery Beat) ===
# ========================================================
celery_app.conf.beat_schedule = {
    # Очистка старых PDF каждый день в 03:00
    "cleanup-old-pdfs-daily": {
        "task": "app.tasks.pdf_tasks.cleanup_old_pdfs",
        "schedule": crontab(hour=3, minute=0),
        "args": (30,),  # удалять файлы старше 30 дней
    },
    
    # Очистка старых GPS точек каждый день в 04:00
    "cleanup-old-gps-daily": {
        "task": "app.tasks.telematics_tasks.cleanup_old_gps_points",
        "schedule": crontab(hour=4, minute=0),
        "args": (90,),  # удалять точки старше 90 дней
    },
    
    # Детекция offline техники каждые 15 минут
    "detect-offline-vehicles": {
        "task": "app.tasks.telematics_tasks.detect_offline_vehicles",
        "schedule": crontab(minute="*/15"),  # каждые 15 минут
        "args": (60,),  # offline если нет данных > 60 минут
    },
    
    # Агрегация моточасов каждый час в 00 минут
    "aggregate-engine-hours-hourly": {
        "task": "app.tasks.scheduled_tasks.aggregate_all_vehicles_engine_hours",
        "schedule": crontab(minute=0),  # каждый час в :00
    },
    
    # Утренний дайджест каждый день в 08:00
    "morning-digest": {
        "task": "app.tasks.scheduled_tasks.send_morning_digest",
        "schedule": crontab(hour=8, minute=0),
    },
    
    # Проверка здоровья системы каждые 5 минут
    "health-check": {
        "task": "app.tasks.scheduled_tasks.system_health_check",
        "schedule": crontab(minute="*/5"),  # каждые 5 минут
    },
}