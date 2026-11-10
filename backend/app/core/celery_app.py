"""Конфигурация Celery с периодическими задачами."""

import os

from celery import Celery
from celery.schedules import crontab

# Use REDIS_URL from env (set by docker-compose / .env.prod)
_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "spectech",
    broker=_redis_url,
    backend=_redis_url.replace("/0", "/1"),  # separate DB for results
    include=[
        "app.tasks.pdf_tasks",
        "app.tasks.email_tasks",
        "app.tasks.telematics_tasks",
        "app.tasks.scheduled_tasks",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Retry & reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_transport_options={
        "master_name": None,
        "socket_timeout": 10,
        "socket_connect_timeout": 5,
        "retry_on_timeout": True,
    },
    # Worker tuning
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Results
    result_expires=3600,
    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

# ========================================================
# === PERIODIC TASKS (Celery Beat) =======================
# ========================================================
celery_app.conf.beat_schedule = {
    "cleanup-old-pdfs-daily": {
        "task": "app.tasks.pdf_tasks.cleanup_old_pdfs",
        "schedule": crontab(hour=3, minute=0),
        "args": (30,),
    },
    "cleanup-old-gps-daily": {
        "task": "app.tasks.telematics_tasks.cleanup_old_gps_points",
        "schedule": crontab(hour=4, minute=0),
        "args": (90,),
    },
    "detect-offline-vehicles": {
        "task": "app.tasks.telematics_tasks.detect_offline_vehicles",
        "schedule": crontab(minute="*/15"),
        "args": (60,),
    },
    "aggregate-engine-hours-hourly": {
        "task": "app.tasks.scheduled_tasks.aggregate_all_vehicles_engine_hours",
        "schedule": crontab(minute=0),
    },
    "morning-digest": {
        "task": "app.tasks.scheduled_tasks.send_morning_digest",
        "schedule": crontab(hour=8, minute=0),
    },
    "health-check": {
        "task": "app.tasks.scheduled_tasks.system_health_check",
        "schedule": crontab(minute="*/5"),
    },
}
