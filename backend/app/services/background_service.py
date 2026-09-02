"""Сервис фоновых задач на основе FastAPI BackgroundTasks."""
import logging
from datetime import datetime, timezone

logger = logging.getLogger("spectech.background")

# Журнал фоновых задач
_task_log = []


def log_task(task_name: str, status: str, details: str = ""):
    """Записывает задачу в журнал."""
    _task_log.append({
        "task": task_name,
        "status": status,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Храним только последние 100
    if len(_task_log) > 100:
        _task_log.pop(0)


def get_task_log() -> list:
    """Возвращает журнал фоновых задач."""
    return list(reversed(_task_log))


# === Фоновые задачи ===


def background_generate_pdf(document_type: str, document_id: int, path: str):
    """Фоновая генерация PDF (вызывается через BackgroundTasks)."""
    try:
        logger.info("Background PDF: %s #%s -> %s", document_type, document_id, path)
        # Здесь можно добавить реальную генерацию, если она не была сделана синхронно
        log_task(f"generate_pdf_{document_type}", "completed", f"ID={document_id}")
    except Exception as e:
        logger.error("Background PDF error: %s", e)
        log_task(f"generate_pdf_{document_type}", "failed", str(e))


def background_send_email(to: str, subject: str, body: str):
    """Фоновая отправка email (мок для разработки)."""
    try:
        logger.info("Background EMAIL to %s: %s", to, subject)
        # В продакшене здесь будет реальная отправка через SMTP/SendGrid
        log_task("send_email", "completed", f"to={to}")
    except Exception as e:
        logger.error("Background EMAIL error: %s", e)
        log_task("send_email", "failed", str(e))


def background_process_gps_batch(vehicle_id: int, points_count: int):
    """Фоновая пост-обработка пачки GPS-точек."""
    try:
        logger.info(
            "Background GPS processing: vehicle=%s, points=%s",
            vehicle_id, points_count,
        )
        # Здесь можно добавить агрегацию моточасов, проверку геозон и т.д.
        log_task("process_gps_batch", "completed", f"vehicle={vehicle_id}, points={points_count}")
    except Exception as e:
        logger.error("Background GPS error: %s", e)
        log_task("process_gps_batch", "failed", str(e))