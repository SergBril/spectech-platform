"""Celery tasks for dispute management and SLA enforcement."""

import logging
from datetime import datetime

from app.core.celery_app import celery_app
from app.core.db import SessionLocal
from app.services import dispute_service
from app.models.dispute import Dispute, DisputeStatus

logger = logging.getLogger("spectech.tasks.disputes")


@celery_app.task(
    name="auto_escalate_overdue_disputes",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def auto_escalate_overdue_disputes(self):
    """
    Автоматически эскалирует просроченные споры.

    Проверяет все споры со статусами:
    - dispatcher_review (SLA 3 часа)
    - escalated_to_manager (SLA 24 часа)
    - escalated_to_ceo (SLA 48 часа)

    Если SLA deadline прошёл — эскалирует на следующий уровень.

    Запускается каждые 5 минут через Celery Beat.

    Returns:
        dict: Количество эскалированных споров по уровням
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        logger.info(f"Starting auto-escalation check at {now}")

        # Получаем все просроченные споры
        overdue_disputes = dispute_service.get_overdue_disputes(db)

        if not overdue_disputes:
            logger.info("No overdue disputes found")
            return {"escalated": 0, "total_checked": 0}

        logger.info(f"Found {len(overdue_disputes)} overdue disputes")

        escalated_count = 0
        results = {
            "dispatcher_to_manager": 0,
            "manager_to_ceo": 0,
            "already_at_ceo": 0,
            "errors": 0,
        }

        for dispute in overdue_disputes:
            try:
                old_status = dispute.status

                # Эскалируем спор
                dispute_service.escalate_dispute(
                    db=db,
                    dispute_id=dispute.id,
                    escalated_by=0,  # System escalation
                )

                escalated_count += 1

                # Подсчитываем по уровням
                if old_status == DisputeStatus.dispatcher_review:
                    results["dispatcher_to_manager"] += 1
                    logger.warning(
                        f"Dispute #{dispute.id} auto-escalated: "
                        f"dispatcher_review → escalated_to_manager"
                    )
                elif old_status == DisputeStatus.escalated_to_manager:
                    results["manager_to_ceo"] += 1
                    logger.warning(
                        f"Dispute #{dispute.id} auto-escalated: "
                        f"escalated_to_manager → escalated_to_ceo"
                    )
                elif old_status == DisputeStatus.escalated_to_ceo:
                    results["already_at_ceo"] += 1
                    logger.error(
                        f"Dispute #{dispute.id} already at CEO level, "
                        f"SLA breached but cannot escalate further"
                    )

            except Exception as e:
                results["errors"] += 1
                logger.error(
                    f"Failed to auto-escalate dispute #{dispute.id}: {e}",
                    exc_info=True,
                )

        # Коммитим все изменения
        db.commit()

        logger.info(
            f"Auto-escalation completed: {escalated_count} disputes escalated. "
            f"Results: {results}"
        )

        return {
            "escalated": escalated_count,
            "total_checked": len(overdue_disputes),
            "breakdown": results,
        }

    except Exception as exc:
        logger.error(f"Auto-escalation task failed: {exc}", exc_info=True)
        # Retry с экспоненциальной задержкой
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

    finally:
        db.close()


@celery_app.task(name="check_sla_breaches")
def check_sla_breaches():
    """
    Проверяет споры с нарушенным SLA и отправляет уведомления.

    Запускается каждые 30 минут.
    Отправляет уведомления руководителям о просроченных спорах.

    Returns:
        dict: Количество споров с нарушенным SLA
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        logger.info(f"Checking SLA breaches at {now}")

        # Находим споры с нарушенным SLA
        breached_disputes = (
            db.query(Dispute)
            .filter(
                Dispute.status.in_([
                    DisputeStatus.dispatcher_review,
                    DisputeStatus.escalated_to_manager,
                    DisputeStatus.escalated_to_ceo,
                ]),
                Dispute.sla_deadline < now,
                Dispute.sla_breached == False,
            )
            .all()
        )

        if not breached_disputes:
            logger.info("No SLA breaches found")
            return {"breached": 0}

        logger.warning(f"Found {len(breached_disputes)} disputes with breached SLA")

        for dispute in breached_disputes:
            dispute.sla_breached = True

            # TODO: Отправить уведомления через notification_service
            # notification_service.send_sla_breach_alert(dispute)

            logger.warning(
                f"Dispute #{dispute.id} SLA breached: "
                f"deadline was {dispute.sla_deadline}, now {now}"
            )

        db.commit()

        return {"breached": len(breached_disputes)}

    except Exception as e:
        logger.error(f"SLA breach check failed: {e}", exc_info=True)
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task(name="generate_dispute_metrics")
def generate_dispute_metrics():
    """
    Генерирует метрики по спорам для дашборда.

    Подсчитывает:
    - Общее количество споров за последние 30 дней
    - Количество споров с нарушенным SLA
    - Среднее время разрешения спора
    - Количество споров по типам
    - Количество споров по уровням эскалации

    Запускается каждый час.

    Returns:
        dict: Метрики по спорам
    """
    from datetime import timedelta
    from sqlalchemy import func

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        logger.info(f"Generating dispute metrics for last 30 days")

        # Общее количество споров за последние 30 дней
        total_disputes = (
            db.query(func.count(Dispute.id))
            .filter(Dispute.created_at >= thirty_days_ago)
            .scalar()
        )

        # Количество споров с нарушенным SLA
        breached_count = (
            db.query(func.count(Dispute.id))
            .filter(
                Dispute.created_at >= thirty_days_ago,
                Dispute.sla_breached == True,
            )
            .scalar()
        )

        # Среднее время разрешения (в минутах)
        avg_resolution_time = (
            db.query(func.avg(Dispute.resolution_time_minutes))
            .filter(
                Dispute.status == DisputeStatus.resolved,
                Dispute.created_at >= thirty_days_ago,
            )
            .scalar()
        )

        # Количество споров по типам
        disputes_by_type = (
            db.query(
                Dispute.dispute_type,
                func.count(Dispute.id),
            )
            .filter(Dispute.created_at >= thirty_days_ago)
            .group_by(Dispute.dispute_type)
            .all()
        )

        # Количество споров по статусам
        disputes_by_status = (
            db.query(
                Dispute.status,
                func.count(Dispute.id),
            )
            .filter(Dispute.created_at >= thirty_days_ago)
            .group_by(Dispute.status)
            .all()
        )

        # Активные споры (не resolved)
        active_disputes = (
            db.query(func.count(Dispute.id))
            .filter(
                Dispute.status.in_([
                    DisputeStatus.dispatcher_review,
                    DisputeStatus.escalated_to_manager,
                    DisputeStatus.escalated_to_ceo,
                ])
            )
            .scalar()
        )

        metrics = {
            "total_disputes_30d": total_disputes,
            "breached_sla_count": breached_count,
            "breach_rate_percent": (
                round((breached_count / total_disputes * 100), 2)
                if total_disputes > 0
                else 0
            ),
            "avg_resolution_time_minutes": (
                round(avg_resolution_time, 2) if avg_resolution_time else 0
            ),
            "disputes_by_type": {
                dtype.value: count for dtype, count in disputes_by_type  # ✅ enum.value = "hours"
            },
            "disputes_by_status": {
                status.value: count for status, count in disputes_by_status  # ✅ enum.value = "resolved"
            },
            "active_disputes": active_disputes,
            "generated_at": now.isoformat(),
        }

        # TODO: Сохранить метрики в Redis или БД для дашборда
        # redis_client.set("dispute_metrics", json.dumps(metrics), ex=3600)

        logger.info(f"Dispute metrics generated: {metrics}")

        return metrics

    except Exception as e:
        logger.error(f"Failed to generate dispute metrics: {e}", exc_info=True)
        return {"error": str(e)}

    finally:
        db.close()