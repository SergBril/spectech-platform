"""Планировщик фоновых задач (APScheduler)."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.db import SessionLocal
from app.services import dispute_service
from app.services.weekly_digest_service import weekly_digest_service

logger = logging.getLogger("spectech.scheduler")

# Глобальный экземпляр планировщика
scheduler = AsyncIOScheduler(timezone="UTC")


async def auto_escalate_disputes_task() -> None:
    """
    Фоновая задача: автоэскалация просроченных споров.

    Запускается каждые N минут (настраивается через SCHEDULER_INTERVAL_MINUTES).
    Проверяет споры с истёкшим SLA и эскалирует их на следующий уровень.
    """
    db = SessionLocal()
    try:
        count = dispute_service.auto_escalate_overdue(db)
        if count > 0:
            logger.info("⏰ Auto-escalated %d overdue dispute(s)", count)
        else:
            logger.debug("No overdue disputes found")
    except Exception as e:
        logger.error("Error in auto_escalate_disputes_task: %s", e, exc_info=True)
    finally:
        db.close()


def start_scheduler() -> None:
    """Запускает планировщик фоновых задач."""
    if not settings.SCHEDULER_ENABLED:
        logger.info("🔇 Scheduler is disabled (SCHEDULER_ENABLED=false)")
        return

    if scheduler.running:
        logger.warning("Scheduler is already running")
        return

    # Задача 1: Автоэскалация просроченных споров
    scheduler.add_job(
        auto_escalate_disputes_task,
        trigger=IntervalTrigger(minutes=settings.SCHEDULER_INTERVAL_MINUTES),
        id="auto_escalate_disputes",
        name="Auto-escalate overdue disputes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Задача 2: Еженедельный дайджест (пятница 18:00)
    from apscheduler.triggers.cron import CronTrigger

    async def weekly_digest_task() -> None:
        """Фоновая задача: отправка еженедельного дайджеста."""
        db = SessionLocal()
        try:
            result = weekly_digest_service.send_digests_for_all_companies(db)
            logger.info("📧 Weekly digest completed: %s", result)
        except Exception as e:
            logger.error("Error in weekly_digest_task: %s", e, exc_info=True)
        finally:
            db.close()

    scheduler.add_job(
        weekly_digest_task,
        trigger=CronTrigger(day_of_week="fri", hour=18, minute=0),
        id="weekly_digest",
        name="Send weekly email digest to accountants",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # === Задача 3: Синхронизация GPS из всех провайдеров (каждые 60 секунд) ===
    from app.tasks.mapix_sync_task import sync_gps_positions

    scheduler.add_job(
        sync_gps_positions,
        trigger=IntervalTrigger(seconds=60),
        id="gps_sync",
        name="Sync GPS positions from all providers",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info(
        "⏰ Scheduler started. Interval: %d min. Jobs: %d",
        settings.SCHEDULER_INTERVAL_MINUTES,
        len(scheduler.get_jobs()),
    )


def stop_scheduler() -> None:
    """Останавливает планировщик."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler stopped")
    else:
        logger.debug("Scheduler was not running")


def get_scheduler_status() -> dict:
    """Возвращает статус планировщика (для health-check)."""
    return {
        "enabled": settings.SCHEDULER_ENABLED,
        "running": scheduler.running,
        "jobs": (
            [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                }
                for job in scheduler.get_jobs()
            ]
            if scheduler.running
            else []
        ),
    }
