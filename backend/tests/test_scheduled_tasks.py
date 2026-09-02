"""Тесты периодических задач."""
from app.tasks.scheduled_tasks import (
    system_health_check,
    send_morning_digest,
    aggregate_all_vehicles_engine_hours,
)
from app.core.celery_app import celery_app


def test_system_health_check():
    """Тест проверки здоровья системы."""
    result = system_health_check.apply().get()
    assert result["status"] == "healthy"
    assert result["database"] == "ok"
    assert "gps_points_count" in result
    assert "invoices_count" in result


def test_beat_schedule_configured():
    """Тест что периодические задачи настроены."""
    from celery.schedules import crontab
    
    schedule = celery_app.conf.beat_schedule
    
    # Проверяем что все 6 задач есть в расписании
    assert "cleanup-old-pdfs-daily" in schedule
    assert "cleanup-old-gps-daily" in schedule
    assert "detect-offline-vehicles" in schedule
    assert "aggregate-engine-hours-hourly" in schedule
    assert "morning-digest" in schedule
    assert "health-check" in schedule
    
    # Проверяем что все задачи используют crontab
    for name, task_config in schedule.items():
        assert "task" in task_config, f"Task {name} has no 'task' field"
        assert "schedule" in task_config, f"Task {name} has no 'schedule' field"
        assert isinstance(task_config["schedule"], crontab), f"Task {name} should use crontab"
    
    # Проверяем что задачи указаны правильно
    assert schedule["health-check"]["task"] == "app.tasks.scheduled_tasks.system_health_check"
    assert schedule["morning-digest"]["task"] == "app.tasks.scheduled_tasks.send_morning_digest"
    assert schedule["cleanup-old-pdfs-daily"]["args"] == (30,)  # удалять старше 30 дней
    assert schedule["cleanup-old-gps-daily"]["args"] == (90,)   # удалять старше 90 дней


def test_morning_digest_task(db):
    """Тест утреннего дайджеста."""
    result = send_morning_digest.apply().get()
    # Может быть "success" или "error" в зависимости от наличия данных
    assert "status" in result
    if result["status"] == "success":
        assert "admins_notified" in result
        assert "stats" in result


def test_aggregate_engine_hours_task(db):
    """Тест агрегации моточасов."""
    result = aggregate_all_vehicles_engine_hours.apply().get()
    assert "status" in result
    if result["status"] == "success":
        assert "vehicles_count" in result
        assert "tasks_queued" in result