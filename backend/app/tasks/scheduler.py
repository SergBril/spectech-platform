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


# Only ONE uvicorn worker may run the scheduler. With --workers 4 every
# worker used to start its own AsyncIOScheduler, so all 14 jobs ran 4x:
# duplicate notifications, duplicate payment matching, 4x load on Mapix /
# Diadoc / bank APIs, and duplicate GPS rows.
_SCHEDULER_LOCK_KEY = 7283401
_scheduler_lock_conn = None


def _acquire_scheduler_lock() -> bool:
    """Try to become the scheduler leader (session-level advisory lock).

    The lock is released automatically if this worker dies, so a respawned
    worker takes over. Held on a dedicated connection for the process life.
    """
    global _scheduler_lock_conn
    from sqlalchemy import text

    from app.core.db import engine

    try:
        conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        acquired = conn.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _SCHEDULER_LOCK_KEY}
        ).scalar()
        if acquired:
            _scheduler_lock_conn = conn
            return True
        conn.close()
        return False
    except Exception as e:
        logger.warning("Scheduler leader lock check failed: %s", e)
        return False


def _release_scheduler_lock() -> None:
    global _scheduler_lock_conn
    if _scheduler_lock_conn is None:
        return
    from sqlalchemy import text

    try:
        _scheduler_lock_conn.execute(
            text("SELECT pg_advisory_unlock(:k)"), {"k": _SCHEDULER_LOCK_KEY}
        )
    except Exception:
        pass
    finally:
        try:
            _scheduler_lock_conn.close()
        except Exception:
            pass
        _scheduler_lock_conn = None


def start_scheduler() -> None:
    """Запускает планировщик фоновых задач."""
    if not settings.SCHEDULER_ENABLED:
        logger.info("🔇 Scheduler is disabled (SCHEDULER_ENABLED=false)")
        return

    if scheduler.running:
        logger.warning("Scheduler is already running")
        return

    # In tests keep the old behaviour (no real Postgres lock available).
    if not settings.TESTING and not _acquire_scheduler_lock():
        logger.info(
            "\U0001f507 Scheduler skipped: another worker holds the leader lock"
        )
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
        from app.models.user_company import UserCompany
        from app.services.alert_service import (
            check_and_notify_conflicts,
            check_and_notify_idle_vehicles,
        )

        today = date_type.today()
        with SessionLocal() as db:
            try:
                from sqlalchemy import select

                company_ids = (
                    db.execute(select(UserCompany.company_id).distinct())
                    .scalars()
                    .all()
                )
                for cid in company_ids:
                    await check_and_notify_idle_vehicles(db, cid, today)
                    await check_and_notify_conflicts(db, cid, today)
                db.commit()
                logger.info(
                    "✅ Daily alerts check completed for %d companies", len(company_ids)
                )
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
        from datetime import date as date_type
        from datetime import timedelta

        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.models.catalog import Vehicle
        from app.models.shift import ShiftFuelEntry, ShiftTask
        from app.models.user_company import UserCompany
        from app.services.alert_service import send_alert_email, send_telegram_alert

        yesterday = date_type.today() - timedelta(days=1)
        week_ago = yesterday - timedelta(days=7)

        with SessionLocal() as db:
            try:
                company_ids = (
                    db.execute(select(UserCompany.company_id).distinct())
                    .scalars()
                    .all()
                )
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
                        stddev = variance**0.5
                        threshold = mean_val + 2 * stddev

                        for v in vals:
                            if v > threshold and stddev > 0:
                                anomalies.append(
                                    f"{stats['name']}: {v:.1f}л (норма {mean_val:.1f}л, +{((v-mean_val)/mean_val)*100:.0f}%)"
                                )

                    if anomalies:
                        msg = "⛽ Аномалии расхода за неделю:\n" + "\n".join(
                            anomalies[:10]
                        )
                        await send_alert_email(cid, "Аномалии расхода топлива", msg, db)
                        await send_telegram_alert(cid, msg)
                        logger.info(
                            "Fuel anomaly alert sent to company %d: %d anomalies",
                            cid,
                            len(anomalies),
                        )

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
        from datetime import date as date_type
        from datetime import timedelta

        from app.core.db import SessionLocal
        from app.models.catalog import Vehicle
        from app.models.finance import Act
        from app.models.shift import ShiftTask

        today = date_type.today()
        if today.day != 1:
            logger.debug("Not 1st of month, skipping auto acts")
            return

        prev_month_end = today - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        with SessionLocal() as db:
            try:
                from sqlalchemy import select

                from app.models.user_company import UserCompany

                company_ids = (
                    db.execute(select(UserCompany.company_id).distinct())
                    .scalars()
                    .all()
                )
                for cid in company_ids:
                    tasks = (
                        db.execute(
                            select(ShiftTask)
                            .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
                            .where(Vehicle.company_id == cid)
                            .where(ShiftTask.shift_date >= prev_month_start)
                            .where(ShiftTask.shift_date <= prev_month_end)
                            .where(ShiftTask.status == "completed")
                        )
                        .scalars()
                        .all()
                    )

                    created = 0
                    for t in tasks:
                        existing = db.execute(
                            select(Act).where(Act.shift_task_id == t.id)
                        ).scalar_one_or_none()
                        if existing:
                            continue

                        hours = 0
                        if t.planned_start and t.planned_end:
                            hours = round(
                                (t.planned_end - t.planned_start).total_seconds()
                                / 3600,
                                2,
                            )

                        act = Act(
                            company_id=cid,
                            shift_task_id=t.id,
                            act_number=f"AUTO-{prev_month_start.strftime('%Y%m')}-{t.id:04d}",
                            act_date=prev_month_end,
                            vehicle_id=t.vehicle_id,
                            hours_worked=hours,
                            hourly_rate=1500,
                            total_amount=round(hours * 1500, 2),
                            vat_amount=round(hours * 1500 * 0.2, 2),
                            status="draft",
                        )
                        db.add(act)
                        created += 1

                    db.commit()
                    if created > 0:
                        logger.info(
                            "Auto-generated %d acts for company %d (%s)",
                            created,
                            cid,
                            prev_month_start.strftime("%Y-%m"),
                        )

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
        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.models.finance import Act
        from app.models.user_company import UserCompany
        from app.services.diadoc_service import diadoc_service
        from app.services.fcm_service import fcm_service

        with SessionLocal() as db:
            try:
                acts = (
                    db.execute(
                        select(Act)
                        .where(Act.status == "sent_to_edo")
                        .where(Act.edo_message_id.isnot(None))
                    )
                    .scalars()
                    .all()
                )

                if not acts:
                    return

                token = await diadoc_service.authenticate()
                if not token:
                    logger.warning("Diadoc auth failed during act status check")
                    return

                updated = 0
                for act in acts:
                    result = await diadoc_service.get_document_status(
                        act.edo_message_id, token
                    )
                    new_status = result.get("status", "")

                    if (
                        new_status in ("signed", "rejected")
                        and act.status != new_status
                    ):
                        old_status = act.status
                        act.status = new_status
                        updated += 1

                        # Notify dispatchers
                        company_id = act.company_id
                        dispatcher_ids = (
                            db.execute(
                                select(UserCompany.user_id).where(
                                    UserCompany.company_id == company_id
                                )
                            )
                            .scalars()
                            .all()
                        )

                        status_emoji = "✅" if new_status == "signed" else "❌"
                        msg = f"{status_emoji} Акт {act.act_number} {'подписан' if new_status == 'signed' else 'ОТКЛОНЁН'} контрагентом"

                        for uid in dispatcher_ids:
                            await fcm_service.send_to_user(
                                uid,
                                "Статус акта",
                                msg,
                                data={"act_id": str(act.id)},
                                db=db,
                            )

                        logger.info(
                            "Act %s status changed: %s → %s",
                            act.act_number,
                            old_status,
                            new_status,
                        )

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

        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.models.finance import Act
        from app.models.user_company import UserCompany
        from app.services.fcm_service import fcm_service

        today = date_type.today()
        with SessionLocal() as db:
            try:
                company_ids = (
                    db.execute(select(UserCompany.company_id).distinct())
                    .scalars()
                    .all()
                )
                for cid in company_ids:
                    overdue_acts = (
                        db.execute(
                            select(Act).where(
                                Act.company_id == cid,
                                Act.status.in_(["draft", "sent_to_edo", "signed"]),
                                Act.act_date
                                <= today - __import__("datetime").timedelta(days=30),
                            )
                        )
                        .scalars()
                        .all()
                    )

                    if not overdue_acts:
                        continue

                    total_overdue = sum(
                        (a.total_amount or 0) - (a.paid_amount or 0)
                        for a in overdue_acts
                    )
                    count = len(
                        [
                            a
                            for a in overdue_acts
                            if (a.total_amount or 0) - (a.paid_amount or 0) > 0
                        ]
                    )

                    if count == 0:
                        continue

                    # Use template for overdue notification
                    try:
                        from app.services.notification_template_service import (
                            render_template,
                        )

                        tmpl_data = render_template(
                            db,
                            "overdue_acts",
                            "max",
                            count=count,
                            amount=f"{total_overdue:,.0f}",
                        )
                        msg = (
                            tmpl_data["body"]
                            if tmpl_data
                            else f"{count} просроченных актов на сумму {total_overdue:,.0f} RUB"
                        )
                    except Exception:
                        msg = f"{count} просроченных актов на сумму {total_overdue:,.0f} RUB"

                    dispatcher_ids = (
                        db.execute(
                            select(UserCompany.user_id).where(
                                UserCompany.company_id == cid
                            )
                        )
                        .scalars()
                        .all()
                    )

                    for uid in dispatcher_ids:
                        await fcm_service.send_to_user(
                            uid,
                            "Просроченные платежи",
                            msg,
                            data={"type": "overdue_alert"},
                            db=db,
                        )

                    # Also notify via MAX
                    try:
                        from app.services.max_messenger_service import (
                            max_messenger_service,
                        )
                        from app.services.notification_prefs_helper import should_notify

                        # Only notify dispatchers who have overdue notifications enabled
                        for uid in dispatcher_ids:
                            if should_notify(db, uid, "overdue", "max"):
                                await max_messenger_service.notify_user(
                                    db, uid, "Просроченные платежи", msg
                                )
                    except Exception as max_err:
                        logger.warning("MAX overdue notification failed: %s", max_err)

                    logger.info(
                        "Overdue alert sent to company %d: %d acts, %.0f RUB",
                        cid,
                        count,
                        total_overdue,
                    )

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
        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.models.bank_statement import BankTransaction
        from app.models.finance import Act
        from app.models.user_company import UserCompany

        with SessionLocal() as db:
            try:
                company_ids = (
                    db.execute(select(UserCompany.company_id).distinct())
                    .scalars()
                    .all()
                )
                total_matched = 0

                for cid in company_ids:
                    payments = (
                        db.execute(
                            select(BankTransaction).where(
                                BankTransaction.company_id == cid,
                                BankTransaction.matched_invoice_id.is_(None),
                                BankTransaction.match_status == "unmatched",
                            )
                        )
                        .scalars()
                        .all()
                    )

                    unpaid_acts = (
                        db.execute(
                            select(Act).where(
                                Act.company_id == cid,
                                Act.status.in_(["draft", "sent_to_edo", "signed"]),
                            )
                        )
                        .scalars()
                        .all()
                    )

                    for payment in payments:
                        for act in unpaid_acts:
                            remaining = (act.total_amount or 0) - (act.paid_amount or 0)
                            if remaining <= 0:
                                continue
                            amount_match = abs(payment.amount - remaining) < max(
                                remaining * 0.01, 1
                            )
                            inn_match = bool(
                                payment.payer_inn
                                and act.counterparty_inn
                                and payment.payer_inn == act.counterparty_inn
                            )
                            purpose_match = bool(
                                payment.purpose
                                and act.act_number
                                and act.act_number.replace("-", "")
                                in payment.purpose.replace("-", "").replace(" ", "")
                            )

                            if amount_match and (
                                inn_match or purpose_match or not act.counterparty_inn
                            ):
                                payment.matched_invoice_id = act.id
                                act.paid_amount = (
                                    act.paid_amount or 0
                                ) + payment.amount
                                act.payment_status = (
                                    "paid"
                                    if act.paid_amount >= act.total_amount
                                    else "partial"
                                )
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

    # === PHASE 4: New scheduled tasks ===

    async def _check_maintenance_due():
        """Проверка техники, требующей ТО по моточасам."""

        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.models.catalog import Vehicle
        from app.models.telematics import EngineHoursLog

        db = SessionLocal()
        try:
            threshold = 250.0  # Стандартный порог ТО

            # Получаем последние записи моточасов для каждой техники
            result = await db.execute(
                select(Vehicle.id, Vehicle.name, Vehicle.company_id).where(
                    Vehicle.is_active == True
                )
            )
            vehicles = result.all()

            due_count = 0
            for v_id, v_name, company_id in vehicles:
                hours_result = await db.execute(
                    select(EngineHoursLog.total_hours)
                    .where(EngineHoursLog.vehicle_id == v_id)
                    .order_by(EngineHoursLog.recorded_at.desc())
                    .limit(1)
                )
                row = hours_result.scalar_one_or_none()
                if row and row >= threshold:
                    due_count += 1
                    logger.warning(
                        f"🔧 Maintenance due: {v_name} ({row:.0f}h >= {threshold}h)"
                    )

            if due_count > 0:
                logger.info(
                    f"🔧 Maintenance due check: {due_count} vehicles need service"
                )
            else:
                logger.debug("Maintenance due check: all clear")
        except Exception as e:
            logger.error(f"Maintenance due check failed: {e}")
        finally:
            await db.close()

    scheduler.add_job(
        _check_maintenance_due,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_maintenance_due_check",
        name="Daily maintenance due check",
        replace_existing=True,
    )

    async def _check_pending_payouts():
        """Уведомление о зависших выплатах (старше 3 дней)."""
        from datetime import datetime, timedelta

        from sqlalchemy import func, select

        from app.core.db import SessionLocal
        from app.models.finance import Payout

        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(days=3)
            result = await db.execute(
                select(func.count(Payout.id))
                .where(Payout.status == "pending")
                .where(Payout.created_at < cutoff)
            )
            count = result.scalar() or 0
            if count > 0:
                logger.warning(f"💸 {count} pending payouts older than 3 days")
            else:
                logger.debug("Pending payouts check: all clear")
        except Exception as e:
            logger.error(f"Pending payouts check failed: {e}")
        finally:
            await db.close()

    scheduler.add_job(
        _check_pending_payouts,
        trigger=CronTrigger(hour=11, minute=0),
        id="daily_pending_payouts_check",
        name="Daily pending payouts check",
        replace_existing=True,
    )

    async def _cleanup_expired_sessions():
        """Очистка истёкших сессий и токенов."""
        from datetime import datetime

        from sqlalchemy import text

        from app.core.db import SessionLocal

        db = SessionLocal()
        try:
            # Очищаем истёкшие записи gps_sync_logs старше 30 дней
            cutoff = datetime.utcnow() - __import__("datetime").timedelta(days=30)
            result = await db.execute(
                text("DELETE FROM gps_sync_logs WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            deleted = result.rowcount
            if deleted > 0:
                logger.info(f"🧹 Cleaned up {deleted} old gps_sync_logs entries")

            await db.commit()
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            await db.rollback()
        finally:
            await db.close()

    scheduler.add_job(
        _cleanup_expired_sessions,
        trigger=CronTrigger(hour=3, minute=0),
        id="daily_session_cleanup",
        name="Daily session/log cleanup",
        replace_existing=True,
    )

    async def _send_daily_company_report():
        """Ежедневный отчёт: сводка по компании за вчера."""
        from datetime import date as date_type
        from datetime import timedelta

        from sqlalchemy import func, select

        from app.core.db import SessionLocal
        from app.models.finance import Invoice
        from app.models.shift import ShiftTask

        db = SessionLocal()
        try:
            yesterday = date_type.today() - timedelta(days=1)

            shifts_result = await db.execute(
                select(func.count(ShiftTask.id)).where(
                    func.date(ShiftTask.planned_start) == yesterday
                )
            )
            shifts_count = shifts_result.scalar() or 0

            invoices_result = await db.execute(
                select(func.sum(Invoice.total_amount))
                .where(func.date(Invoice.created_at) == yesterday)
                .where(Invoice.status == "paid")
            )
            revenue = invoices_result.scalar() or 0

            logger.info(
                f"📊 Daily report ({yesterday}): {shifts_count} shifts, {revenue:,.0f} ₽ revenue"
            )
        except Exception as e:
            logger.error(f"Daily report failed: {e}")
        finally:
            await db.close()

    scheduler.add_job(
        _send_daily_company_report,
        trigger=CronTrigger(hour=8, minute=30),
        id="daily_company_report",
        name="Daily company report",
        replace_existing=True,
    )

    async def _check_overdue_invoices():
        """Проверка просроченных счетов (не оплаченных после дедлайна)."""
        from datetime import date as date_type

        from sqlalchemy import func, select

        from app.core.db import SessionLocal
        from app.models.finance import Invoice

        db = SessionLocal()
        try:
            today = date_type.today()
            result = await db.execute(
                select(func.count(Invoice.id))
                .where(Invoice.status.in_(["sent", "approved"]))
                .where(Invoice.due_date < today)
            )
            count = result.scalar() or 0
            if count > 0:
                logger.warning(f"📄 {count} overdue invoices detected")
            else:
                logger.debug("Overdue invoices check: all clear")
        except Exception as e:
            logger.error(f"Overdue invoices check failed: {e}")
        finally:
            await db.close()

    scheduler.add_job(
        _check_overdue_invoices,
        trigger=CronTrigger(hour=9, minute=30),
        id="daily_overdue_invoices_check",
        name="Daily overdue invoices check",
        replace_existing=True,
    )


def stop_scheduler() -> None:
    """Останавливает планировщик."""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("🛑 Scheduler stopped")
        else:
            logger.debug("Scheduler was not running")
    except Exception as e:
        logger.warning("Error stopping scheduler: %s", e)
    finally:
        _release_scheduler_lock()


def get_scheduler_status() -> dict:
    """Возвращает статус планировщика (для health-check)."""
    try:
        is_running = scheduler.running
        jobs_list = (
            [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                }
                for job in scheduler.get_jobs()
            ]
            if is_running
            else []
        )
    except Exception:
        # Scheduler may be shutting down during parallel tests
        is_running = False
        jobs_list = []
    return {
        "enabled": settings.SCHEDULER_ENABLED,
        "running": is_running,
        "jobs": jobs_list,
    }
