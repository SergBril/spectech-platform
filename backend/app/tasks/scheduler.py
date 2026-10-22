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

    # Проверка простоев и конфликтов расписания (ежедневно в 07:00)
    async def _check_daily_alerts():
        from datetime import date as date_type
        from app.core.db import SessionLocal
        from app.services.alert_service import check_and_notify_idle_vehicles, check_and_notify_conflicts
        from app.models.auth import UserCompany

        today = date_type.today()
        with SessionLocal() as db:
            try:
                company_ids = db.execute(select(UserCompany.company_id).distinct()).scalars().all()
                for cid in company_ids:
                    await check_and_notify_idle_vehicles(db, cid, today)
                    await check_and_notify_conflicts(db, cid, today)
                db.commit()
                logger.info("✅ Daily alerts check completed for %d companies", len(company_ids))
            except Exception as e:
                logger.error("❌ Daily alerts check failed: %s", e)
                db.rollback()

    scheduler.add_job(
        _check_daily_alerts,
        trigger=CronTrigger(hour=7, minute=0),
        id="daily_alert_check",
        name="Daily idle & conflict alerts",
        replace_existing=True,
    )

    # Проверка аномалий расхода топлива (ежедневно в 08:00)
    async def _check_fuel_anomalies():
        from datetime import date as date_type, timedelta
        from sqlalchemy import select, func
        from app.core.db import SessionLocal
        from app.models.shift import ShiftFuelEntry, ShiftTask
        from app.models.vehicle import Vehicle
        from app.models.auth import UserCompany
        from app.services.alert_service import send_alert_email, send_telegram_alert

        yesterday = date_type.today() - timedelta(days=1)
        week_ago = yesterday - timedelta(days=7)

        with SessionLocal() as db:
            try:
                company_ids = db.execute(select(UserCompany.company_id).distinct()).scalars().all()
                for cid in company_ids:
                    entries = db.execute(
                        select(ShiftFuelEntry, Vehicle.name)
                        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
                        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
                        .where(Vehicle.company_id == cid)
                        .where(ShiftTask.shift_date >= week_ago)
                        .where(ShiftTask.shift_date <= yesterday)
                    ).all()

                    if len(entries) < 5:
                        continue

                    # Group by vehicle
                    by_vehicle = {}
                    for entry, vname in entries:
                        vid = entry.vehicle_id
                        if vid not in by_vehicle:
                            by_vehicle[vid] = {"name": vname, "values": []}
                        by_vehicle[vid]["values"].append(entry.quantity_liters)

                    anomalies = []
                    for vid, stats in by_vehicle.items():
                        vals = stats["values"]
                        if len(vals) < 3:
                            continue
                        mean_val = sum(vals) / len(vals)
                        variance = sum((v - mean_val) ** 2 for v in vals) / len(vals)
                        stddev = variance ** 0.5
                        threshold = mean_val + 2 * stddev

                        for v in vals:
                            if v > threshold and stddev > 0:
                                anomalies.append(f"{stats['name']}: {v:.1f}л (норма {mean_val:.1f}л, +{((v-mean_val)/mean_val)*100:.0f}%)")

                    if anomalies:
                        msg = f"⛽ Аномалии расхода за неделю:\n" + "\n".join(anomalies[:10])
                        await send_alert_email(cid, "Аномалии расхода топлива", msg, db)
                        await send_telegram_alert(cid, msg)
                        logger.info("Fuel anomaly alert sent to company %d: %d anomalies", cid, len(anomalies))

                db.commit()
                logger.info("✅ Fuel anomaly check completed")
            except Exception as e:
                logger.error("❌ Fuel anomaly check failed: %s", e)
                db.rollback()

    scheduler.add_job(
        _check_fuel_anomalies,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_fuel_anomaly_check",
        name="Daily fuel anomaly detection",
        replace_existing=True,
    )

    # Авто-генерация и отправка актов (1-е число месяца в 09:00)
    async def _auto_generate_and_send_acts():
        from datetime import date as date_type, timedelta
        from app.core.db import SessionLocal
        from app.models.shift import ShiftTask
        from app.models.vehicle import Vehicle
        from app.models.acts import Act
        from app.services.diadoc_service import diadoc_service
        from xml.etree.ElementTree import Element, SubElement, tostring

        today = date_type.today()
        if today.day != 1:
            logger.debug("Not 1st of month, skipping auto acts")
            return

        prev_month_end = today - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        with SessionLocal() as db:
            try:
                from sqlalchemy import select
                from app.models.auth import UserCompany

                company_ids = db.execute(select(UserCompany.company_id).distinct()).scalars().all()
                for cid in company_ids:
                    tasks = db.execute(
                        select(ShiftTask)
                        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
                        .where(Vehicle.company_id == cid)
                        .where(ShiftTask.shift_date >= prev_month_start)
                        .where(ShiftTask.shift_date <= prev_month_end)
                        .where(ShiftTask.status == "completed")
                    ).scalars().all()

                    created = 0
                    for t in tasks:
                        existing = db.execute(
                            select(Act).where(Act.shift_task_id == t.id)
                        ).scalar_one_or_none()
                        if existing:
                            continue

                        vehicle = db.get(Vehicle, t.vehicle_id)
                        hours = 0
                        if t.planned_start and t.planned_end:
                            hours = round((t.planned_end - t.planned_start).total_seconds() / 3600, 2)

                        act = Act(
                            company_id=cid, shift_task_id=t.id,
                            act_number=f"AUTO-{prev_month_start.strftime('%Y%m')}-{t.id:04d}",
                            act_date=prev_month_end, vehicle_id=t.vehicle_id,
                            hours_worked=hours, hourly_rate=1500,
                            total_amount=round(hours * 1500, 2),
                            vat_amount=round(hours * 1500 * 0.2, 2),
                            status="draft",
                        )
                        db.add(act)
                        created += 1

                    db.commit()
                    if created > 0:
                        logger.info("Auto-generated %d acts for company %d (%s)", created, cid, prev_month_start.strftime("%Y-%m"))

                db.commit()
                logger.info("✅ Auto acts generation completed")
            except Exception as e:
                logger.error("❌ Auto acts generation failed: %s", e)
                db.rollback()

    scheduler.add_job(
        _auto_generate_and_send_acts,
        trigger=CronTrigger(day=1, hour=9, minute=0),
        id="monthly_auto_acts",
        name="Monthly auto-generate acts",
        replace_existing=True,
    )

    # Проверка статусов актов в Diadoc (каждые 4 часа)
    async def _check_act_statuses():
        from app.core.db import SessionLocal
        from sqlalchemy import select
        from app.models.acts import Act
        from app.models.auth import UserCompany
        from app.services.diadoc_service import diadoc_service
        from app.services.fcm_service import fcm_service

        with SessionLocal() as db:
            try:
                acts = db.execute(
                    select(Act).where(Act.status == "sent_to_edo").where(Act.edo_message_id.isnot(None))
                ).scalars().all()

                if not acts:
                    return

                token = await diadoc_service.authenticate()
                if not token:
                    logger.warning("Diadoc auth failed during act status check")
                    return

                updated = 0
                for act in acts:
                    result = await diadoc_service.get_document_status(act.edo_message_id, token)
                    new_status = result.get("status", "")

                    if new_status in ("signed", "rejected") and act.status != new_status:
                        old_status = act.status
                        act.status = new_status
                        updated += 1

                        # Notify dispatchers
                        company_id = act.company_id
                        dispatcher_ids = db.execute(
                            select(UserCompany.user_id).where(UserCompany.company_id == company_id)
                        ).scalars().all()

                        status_emoji = "✅" if new_status == "signed" else "❌"
                        msg = f"{status_emoji} Акт {act.act_number} {'подписан' if new_status == 'signed' else 'ОТКЛОНЁН'} контрагентом"

                        for uid in dispatcher_ids:
                            await fcm_service.send_to_user(uid, "Статус акта", msg, data={"act_id": str(act.id)}, db=db)

                        logger.info("Act %s status changed: %s → %s", act.act_number, old_status, new_status)

                db.commit()
                if updated > 0:
                    logger.info("✅ Act status check: %d acts updated", updated)
            except Exception as e:
                logger.error("❌ Act status check failed: %s", e)
                db.rollback()

    scheduler.add_job(
        _check_act_statuses,
        trigger=IntervalTrigger(hours=4),
        id="act_status_check",
        name="Check Diadoc act statuses",
        replace_existing=True,
    )

    # Уведомления о просроченных актах (ежедневно в 09:00)
    async def _notify_overdue_receivables():
        from datetime import date as date_type
        from app.core.db import SessionLocal
        from sqlalchemy import select
        from app.models.acts import Act
        from app.models.auth import UserCompany
        from app.services.fcm_service import fcm_service

        today = date_type.today()
        with SessionLocal() as db:
            try:
                company_ids = db.execute(select(UserCompany.company_id).distinct()).scalars().all()
                for cid in company_ids:
                    overdue_acts = db.execute(
                        select(Act).where(
                            Act.company_id == cid,
                            Act.status.in_(["draft", "sent_to_edo", "signed"]),
                            Act.act_date <= today - __import__('datetime').timedelta(days=30),
                        )
                    ).scalars().all()

                    if not overdue_acts:
                        continue

                    total_overdue = sum((a.total_amount or 0) - (a.paid_amount or 0) for a in overdue_acts)
                    count = len([a for a in overdue_acts if (a.total_amount or 0) - (a.paid_amount or 0) > 0])

                    if count == 0:
                        continue

                    # Use template for overdue notification
                    try:
                        from app.services.notification_template_service import render_template
                        tmpl_data = render_template(db, "overdue_acts", "max", count=count, amount=f"{total_overdue:,.0f}")
                        msg = tmpl_data["body"] if tmpl_data else f"{count} просроченных актов на сумму {total_overdue:,.0f} RUB"
                    except Exception:
                        msg = f"{count} просроченных актов на сумму {total_overdue:,.0f} RUB"

                    dispatcher_ids = db.execute(
                        select(UserCompany.user_id).where(UserCompany.company_id == cid)
                    ).scalars().all()

                    for uid in dispatcher_ids:
                        await fcm_service.send_to_user(uid, "Просроченные платежи", msg, data={"type": "overdue_alert"}, db=db)

                    # Also notify via MAX
                    try:
                        from app.services.max_messenger_service import max_messenger_service
                        from app.services.notification_prefs_helper import should_notify
                        # Only notify dispatchers who have overdue notifications enabled
                        for uid in dispatcher_ids:
                            if should_notify(db, uid, "overdue", "max"):
                                await max_messenger_service.notify_user(db, uid, "Просроченные платежи", msg)
                    except Exception as max_err:
                        logger.warning("MAX overdue notification failed: %s", max_err)

                    logger.info("Overdue alert sent to company %d: %d acts, %.0f RUB", cid, count, total_overdue)

                db.commit()
                logger.info("✅ Overdue receivables notification completed")
            except Exception as e:
                logger.error("❌ Overdue notification failed: %s", e)
                db.rollback()

    scheduler.add_job(
        _notify_overdue_receivables,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_overdue_receivables",
        name="Daily overdue receivables alert",
        replace_existing=True,
    )

    # Авто-разнесение платежей (ежедневно в 10:00)
    async def _auto_match_payments():
        from app.core.db import SessionLocal
        from sqlalchemy import select
        from app.models.bank import BankTransaction
        from app.models.acts import Act
        from app.models.auth import UserCompany

        with SessionLocal() as db:
            try:
                company_ids = db.execute(select(UserCompany.company_id).distinct()).scalars().all()
                total_matched = 0

                for cid in company_ids:
                    payments = db.execute(
                        select(BankTransaction).where(
                            BankTransaction.company_id == cid,
                            BankTransaction.matched_act_id.is_(None),
                            BankTransaction.status == "processed",
                        )
                    ).scalars().all()

                    unpaid_acts = db.execute(
                        select(Act).where(
                            Act.company_id == cid,
                            Act.status.in_(["draft", "sent_to_edo", "signed"]),
                        )
                    ).scalars().all()

                    for payment in payments:
                        for act in unpaid_acts:
                            remaining = (act.total_amount or 0) - (act.paid_amount or 0)
                            if remaining <= 0:
                                continue
                            amount_match = abs(payment.amount - remaining) < max(remaining * 0.01, 1)
                            inn_match = bool(payment.payer_inn and act.counterparty_inn and payment.payer_inn == act.counterparty_inn)
                            purpose_match = bool(payment.purpose and act.act_number and act.act_number.replace("-", "") in payment.purpose.replace("-", "").replace(" ", ""))

                            if amount_match and (inn_match or purpose_match or not act.counterparty_inn):
                                payment.matched_act_id = act.id
                                act.paid_amount = (act.paid_amount or 0) + payment.amount
                                act.payment_status = "paid" if act.paid_amount >= act.total_amount else "partial"
                                total_matched += 1
                                break

                db.commit()
                if total_matched > 0:
                    logger.info("✅ Auto-match: %d payments matched", total_matched)
            except Exception as e:
                logger.error("❌ Auto-match failed: %s", e)
                db.rollback()

    scheduler.add_job(
        _auto_match_payments,
        trigger=CronTrigger(hour=10, minute=0),
        id="daily_auto_match_payments",
        name="Daily auto-match payments to acts",
        replace_existing=True,
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
