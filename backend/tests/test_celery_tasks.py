"""Тесты Celery задач."""
from app.tasks.pdf_tasks import cleanup_old_pdfs
from app.tasks.email_tasks import send_email_async
from app.tasks.telematics_tasks import cleanup_old_gps_points


def test_cleanup_old_pdfs_task():
    """Тест очистки старых PDF."""
    result = cleanup_old_pdfs.apply(args=[30]).get()
    assert result["status"] == "success"
    assert "deleted_count" in result


def test_send_email_async_mock():
    """Тест отправки email (mock режим)."""
    result = send_email_async.apply(
        args=["test@example.com", "Test Subject", "<p>Test body</p>"]
    ).get()
    assert result["status"] == "success"
    assert result["to"] == "test@example.com"
    assert result["subject"] == "Test Subject"
    assert result["mock"] is True


def test_cleanup_old_gps_points_task(db):
    """Тест очистки старых GPS точек."""
    result = cleanup_old_gps_points.apply(args=[90]).get()
    assert result["status"] == "success"
    assert "deleted_count" in result
    assert result["days_old"] == 90