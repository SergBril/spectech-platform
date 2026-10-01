"""Сервис диспетчеризации: проверка доступности техники, назначение, валидация."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.dispatch import Request, RequestAssignment
from app.models.shift import ShiftTask, ShiftTaskStatus

logger = logging.getLogger("spectech.dispatch_service")


class ConflictType(str, Enum):
    """Типы конфликтов при назначении техники."""

    VEHICLE_NOT_FOUND = "vehicle_not_found"
    VEHICLE_WRONG_COMPANY = "vehicle_wrong_company"
    VEHICLE_UNAVAILABLE_STATUS = "vehicle_unavailable_status"
    INVALID_PERIOD = "invalid_period"
    ASSIGNMENT_OVERLAP = "assignment_overlap"
    SHIFT_TASK_OVERLAP = "shift_task_overlap"
    REQUEST_NOT_FOUND = "request_not_found"
    REQUEST_CLOSED = "request_closed"


@dataclass
class AvailabilityConflict:
    """Описание одного конфликта."""

    conflict_type: ConflictType
    message: str
    conflicting_entity_id: int | None = None
    conflicting_entity_type: str | None = None
    details: dict = field(default_factory=dict)


@dataclass
class AvailabilityResult:
    """Результат проверки доступности техники."""

    available: bool
    vehicle_id: int | None = None
    vehicle_name: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    conflicts: list[AvailabilityConflict] = field(default_factory=list)
    reason: str = "OK"

    def add_conflict(
        self,
        conflict_type: ConflictType,
        message: str,
        entity_id: int | None = None,
        entity_type: str | None = None,
        **details,
    ) -> None:
        """Добавить конфликт в список."""
        self.conflicts.append(
            AvailabilityConflict(
                conflict_type=conflict_type,
                message=message,
                conflicting_entity_id=entity_id,
                conflicting_entity_type=entity_type,
                details=details,
            )
        )
        self.available = False
        if not self.reason or self.reason == "OK":
            self.reason = message


# Статусы техники, при которых назначение невозможно
UNAVAILABLE_VEHICLE_STATUSES = {"repair", "decommissioned", "sold"}

# Статусы RequestAssignment, которые блокируют назначение
BLOCKING_ASSIGNMENT_STATUSES = {"planned", "confirmed", "active"}

# Статусы ShiftTask, которые блокируют назначение
BLOCKING_SHIFT_STATUSES = {
    ShiftTaskStatus.draft,
    ShiftTaskStatus.signed_by_operator,
    ShiftTaskStatus.checked,
    ShiftTaskStatus.released,
}


def check_vehicle_availability(
    db: Session,
    vehicle_id: int,
    company_id: int,
    period_start: datetime,
    period_end: datetime,
    exclude_assignment_id: int | None = None,
) -> AvailabilityResult:
    """
    Комплексная проверка доступности техники на указанный период.

    Проверяет:
    1. Валидность периода (start < end)
    2. Существование техники и принадлежность компании
    3. Статус техники (не repair/decommissioned/sold)
    4. Отсутствие пересекающихся RequestAssignment
    5. Отсутствие пересекающихся ShiftTask

    Args:
        db: Сессия БД
        vehicle_id: ID техники
        company_id: ID компании (для проверки принадлежности)
        period_start: Начало периода
        period_end: Конец периода
        exclude_assignment_id: ID назначения для исключения
                               (при редактировании существующего)

    Returns:
        AvailabilityResult с флагом available и списком конфликтов
    """
    result = AvailabilityResult(
        available=True,
        vehicle_id=vehicle_id,
        period_start=period_start,
        period_end=period_end,
    )

    # ── Проверка 1: Валидность периода ──────────────────────────────────
    if period_start >= period_end:
        result.add_conflict(
            conflict_type=ConflictType.INVALID_PERIOD,
            message="period_start must be before period_end",
            start=period_start.isoformat(),
            end=period_end.isoformat(),
        )
        return result

    # ── Проверка 2: Существование техники ──────────────────────────────
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        result.add_conflict(
            conflict_type=ConflictType.VEHICLE_NOT_FOUND,
            message=f"Vehicle #{vehicle_id} not found",
        )
        return result

    result.vehicle_name = vehicle.name

    # ── Проверка 3: Принадлежность компании ────────────────────────────
    if vehicle.company_id != company_id:
        result.add_conflict(
            conflict_type=ConflictType.VEHICLE_WRONG_COMPANY,
            message=f"Vehicle #{vehicle_id} belongs to another company",
            entity_id=vehicle_id,
            entity_type="vehicle",
        )
        return result

    # ── Проверка 4: Статус техники ─────────────────────────────────────
    if vehicle.status in UNAVAILABLE_VEHICLE_STATUSES:
        result.add_conflict(
            conflict_type=ConflictType.VEHICLE_UNAVAILABLE_STATUS,
            message=f"Vehicle status is '{vehicle.status}' — assignment not allowed",
            entity_id=vehicle_id,
            entity_type="vehicle",
            current_status=vehicle.status,
        )
        return result

    # ── Проверка 5: Пересечения с RequestAssignment ────────────────────
    assignment_query = select(RequestAssignment).where(
        RequestAssignment.vehicle_id == vehicle_id,
        RequestAssignment.status.in_(list(BLOCKING_ASSIGNMENT_STATUSES)),
        RequestAssignment.planned_start < period_end,
        RequestAssignment.planned_end > period_start,
    )

    if exclude_assignment_id:
        assignment_query = assignment_query.where(
            RequestAssignment.id != exclude_assignment_id
        )

    overlapping_assignments = db.scalars(assignment_query).all()

    for assignment in overlapping_assignments:
        result.add_conflict(
            conflict_type=ConflictType.ASSIGNMENT_OVERLAP,
            message=(
                f"Vehicle '{vehicle.name}' already assigned "
                f"to request #{assignment.request_id} "
                f"({assignment.planned_start:%d.%m %H:%M} — "
                f"{assignment.planned_end:%d.%m %H:%M})"
            ),
            entity_id=assignment.id,
            entity_type="request_assignment",
            request_id=assignment.request_id,
            overlap_start=max(assignment.planned_start, period_start).isoformat(),
            overlap_end=min(assignment.planned_end, period_end).isoformat(),
        )

    # ── Проверка 6: Пересечения с ShiftTask ────────────────────────────
    # ShiftTask привязан к дате, проверяем по дате + статусу
    shift_date = period_start.date()
    shift_query = select(ShiftTask).where(
        ShiftTask.vehicle_id == vehicle_id,
        ShiftTask.shift_date == shift_date,
        ShiftTask.status.in_(list(BLOCKING_SHIFT_STATUSES)),
    )

    # Если есть exclude_assignment_id — исключаем смену этого назначения
    if exclude_assignment_id:
        shift_query = shift_query.where(
            or_(
                ShiftTask.assignment_id != exclude_assignment_id,
                ShiftTask.assignment_id.is_(None),
            )
        )

    overlapping_shifts = db.scalars(shift_query).all()

    for shift in overlapping_shifts:
        result.add_conflict(
            conflict_type=ConflictType.SHIFT_TASK_OVERLAP,
            message=(
                f"Vehicle '{vehicle.name}' has active shift task "
                f"#{shift.id} on {shift.shift_date:%d.%m.%Y} "
                f"(status: {shift.status.value})"
            ),
            entity_id=shift.id,
            entity_type="shift_task",
            shift_date=shift.shift_date.isoformat(),
            shift_status=shift.status.value,
        )

    # ── Финальный результат ────────────────────────────────────────────
    if result.available:
        result.reason = "OK"
        logger.debug(
            f"✅ Vehicle #{vehicle_id} '{vehicle.name}' available "
            f"for {period_start:%Y-%m-%d %H:%M} — {period_end:%Y-%m-%d %H:%M}"
        )
    else:
        logger.warning(
            f"❌ Vehicle #{vehicle_id} '{vehicle.name}' NOT available: "
            f"{len(result.conflicts)} conflict(s)"
        )

    return result


def validate_request_for_assignment(
    db: Session,
    request_id: int,
    company_id: int,
) -> tuple[Request | None, str | None]:
    """
    Валидация заявки перед назначением техники.

    Returns:
        (request, error_message) — если error_message не None,
        назначение невозможно
    """
    request = db.get(Request, request_id)
    if not request:
        return None, "Request not found"

    if request.company_id != company_id:
        return None, "Request belongs to another company"

    if request.status in ("closed", "cancelled"):
        return None, f"Request is {request.status} — cannot assign"

    return request, None
