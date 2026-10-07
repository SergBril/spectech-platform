"""Service for handling disputes with SLA tracking."""

import logging
from datetime import datetime, timedelta, UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dispute import (
    Dispute,
    DisputeStatus,
    DisputeType,
    InitiatorRole,
    AssignedRole,
)
from app.models.shift import ShiftReport, ShiftReportStatus, ShiftTask
from app.models.dispatch import Request

logger = logging.getLogger("spectech.dispute_service")

# SLA deadlines
INITIAL_SLA_HOURS = 3
MANAGER_ESCALATION_HOURS = 24
CEO_ESCALATION_HOURS = 48

def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Гарантирует, что datetime имеет timezone (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt

def open_dispute(
    db: Session,
    shift_report_id: int,
    dispute_type: DisputeType,
    initiator_id: int,
    initiator_role: InitiatorRole,
    operator_version: dict | None = None,
    client_version: dict | None = None,
    evidence: dict | None = None,
) -> Dispute:
    """
    Opens a new dispute for a shift report.

    Sets SLA deadline to 3 hours from now.
    Assigns to dispatcher for initial review.
    """
    # Get shift report
    shift_report = db.get(ShiftReport, shift_report_id)
    if not shift_report:
        raise ValueError(f"ShiftReport {shift_report_id} not found")

    # Get shift task to find request_id
    shift_task = db.get(ShiftTask, shift_report.shift_task_id)
    if not shift_task:
        raise ValueError(f"ShiftTask {shift_report.shift_task_id} not found")

    # Get request
    request = db.get(Request, shift_task.request_id)
    if not request:
        raise ValueError(f"Request {shift_task.request_id} not found")

    # Calculate SLA deadline (✅ ИСПРАВЛЕНО: используем UTC)
    now = datetime.now(UTC)
    sla_deadline = now + timedelta(hours=INITIAL_SLA_HOURS)

    # Create dispute
    dispute = Dispute(
        shift_report_id=shift_report_id,
        request_id=request.id,
        company_id=request.company_id,
        status=DisputeStatus.dispatcher_review,
        dispute_type=dispute_type,
        opened_at=now,
        sla_deadline=sla_deadline,
        initiator_id=initiator_id,
        initiator_role=initiator_role,
        operator_version=operator_version,
        client_version=client_version,
        evidence=evidence,
    )

    db.add(dispute)

    # Update shift report status
    shift_report.status = ShiftReportStatus.disputed

    db.commit()
    db.refresh(dispute)

    logger.info(
        f"Dispute {dispute.id} opened for shift_report {shift_report_id}, "
        f"SLA deadline: {sla_deadline}"
    )

    return dispute


def escalate_dispute(
    db: Session,
    dispute_id: int,
    escalated_by: int,
) -> Dispute:
    """
    Escalates dispute to next level.

    dispatcher_review -> escalated_to_manager (24h deadline)
    escalated_to_manager -> escalated_to_ceo (48h deadline)
    """
    dispute = db.get(Dispute, dispute_id)
    if not dispute:
        raise ValueError(f"Dispute {dispute_id} not found")

    # ✅ ИСПРАВЛЕНО: используем UTC
    now = datetime.now(UTC)

    if dispute.status == DisputeStatus.dispatcher_review:
        dispute.status = DisputeStatus.escalated_to_manager
        dispute.escalated_at = now
        dispute.escalation_deadline = now + timedelta(hours=MANAGER_ESCALATION_HOURS)
        dispute.assigned_role = AssignedRole.manager
        logger.info(f"Dispute {dispute_id} escalated to manager")

    elif dispute.status == DisputeStatus.escalated_to_manager:
        dispute.status = DisputeStatus.escalated_to_ceo
        dispute.escalated_at = now
        dispute.escalation_deadline = now + timedelta(hours=CEO_ESCALATION_HOURS)
        dispute.assigned_role = AssignedRole.ceo
        logger.info(f"Dispute {dispute_id} escalated to CEO")

    else:
        raise ValueError(f"Cannot escalate dispute in status {dispute.status}")

    db.commit()
    db.refresh(dispute)

    return dispute


def resolve_dispute(
    db: Session,
    dispute_id: int,
    resolved_by: int,
    resolution: dict,
    final_moto_hours: float | None = None,
    final_odometer: int | None = None,
    final_fuel_used: float | None = None,
) -> Dispute:
    """
    Resolves a dispute and updates shift report with final values.
    """
    dispute = db.get(Dispute, dispute_id)
    if not dispute:
        raise ValueError(f"Dispute {dispute_id} not found")

    if dispute.status == DisputeStatus.resolved:
        raise ValueError(f"Dispute {dispute_id} already resolved")

    # ✅ ИСПРАВЛЕНО: используем UTC
    now = datetime.now(UTC)
    
    # Нормализуем opened_at для безопасного расчёта
    opened_at = _ensure_aware(dispute.opened_at)
    if opened_at:
        resolution_time = (now - opened_at).total_seconds() / 60
    else:
        resolution_time = 0

    # Update dispute
    dispute.status = DisputeStatus.resolved
    dispute.resolution = resolution
    dispute.resolved_at = now
    dispute.resolved_by = resolved_by
    dispute.resolution_time_minutes = int(resolution_time)

    # Check if SLA was breached
    sla_deadline = _ensure_aware(dispute.sla_deadline)
    if sla_deadline and now > sla_deadline:
        dispute.sla_breached = True

    # Update shift report with final values
    shift_report = db.get(ShiftReport, dispute.shift_report_id)
    if shift_report:
        shift_report.status = ShiftReportStatus.finalized

        if final_moto_hours is not None:
            shift_report.final_moto_hours = final_moto_hours
        if final_odometer is not None:
            shift_report.final_odometer = final_odometer
        if final_fuel_used is not None:
            shift_report.final_fuel_used = final_fuel_used

    db.commit()
    db.refresh(dispute)

    logger.info(
        f"Dispute {dispute_id} resolved in {resolution_time:.1f} minutes, "
        f"SLA breached: {dispute.sla_breached}"
    )

    return dispute


def get_overdue_disputes(db: Session) -> list[Dispute]:
    """Returns all disputes that have exceeded their SLA deadline."""
    now = datetime.now(UTC)

    # Получаем все активные споры
    stmt = select(Dispute).where(
        Dispute.status.in_([
            DisputeStatus.dispatcher_review,
            DisputeStatus.escalated_to_manager,
            DisputeStatus.escalated_to_ceo,
        ]),
    )
    
    all_disputes = list(db.scalars(stmt).all())
    
    # Фильтруем по SLA вручную (для надёжности с таймзонами)
    overdue = []
    for d in all_disputes:
        sla = _ensure_aware(d.sla_deadline)
        if sla and now > sla:
            overdue.append(d)
    
    return overdue


def auto_escalate_overdue(db: Session) -> int:
    """
    Automatically escalates overdue disputes.

    Returns number of escalated disputes.
    """
    overdue = get_overdue_disputes(db)
    escalated_count = 0

    for dispute in overdue:
        try:
            escalate_dispute(db, dispute.id, escalated_by=0)  # System escalation
            escalated_count += 1
        except ValueError as e:
            logger.error(f"Failed to auto-escalate dispute {dispute.id}: {e}")

    if escalated_count > 0:
        logger.info(f"Auto-escalated {escalated_count} overdue disputes")

    return escalated_count