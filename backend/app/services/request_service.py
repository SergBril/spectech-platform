"""Request business logic service.

Extracted from app/api/routes/requests.py to separate business logic
from HTTP layer. Route handlers should only handle validation, auth,
and response formatting.
"""
import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.dispatch import Request, RequestAssignment, RequestStatusLog
from app.models.shift import ShiftTask, ShiftTaskStatus
from app.services.notification_service import create_notification

logger = logging.getLogger("spectech.request_service")

UNAVAILABLE_VEHICLE_STATUSES = {"repair", "decommissioned", "sold"}
BLOCKING_ASSIGNMENT_STATUSES = ("planned", "confirmed", "active")


class RequestServiceError(Exception):
    """Base exception for request service errors."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class RequestService:
    """Business logic for request operations."""

    def __init__(self, db: Session):
        self.db = db

    async def assign_vehicle(
        self,
        request_id: int,
        vehicle_id: int,
        operator_id: int | None,
        company_id: int,
        user_id: int,
        planned_start: datetime | None = None,
        planned_end: datetime | None = None,
    ) -> Request:
        """Assign a vehicle to a request.

        Raises RequestServiceError on validation/business rule failures.
        """
        # ── Validate request ───────────────────────────────────────────
        request = self.db.get(Request, request_id)
        if not request or request.company_id != company_id:
            raise RequestServiceError(404, "Request not found")

        if request.status in ("closed", "cancelled"):
            raise RequestServiceError(
                409, f"Request is {request.status} — cannot assign"
            )

        # ── Validate vehicle ───────────────────────────────────────────
        vehicle = self.db.get(Vehicle, vehicle_id)
        if not vehicle or vehicle.company_id != company_id:
            raise RequestServiceError(404, "Vehicle not found")

        if vehicle.status in UNAVAILABLE_VEHICLE_STATUSES:
            raise RequestServiceError(
                409,
                f"Vehicle '{vehicle.name}' has status '{vehicle.status}' — assignment not allowed",
            )

        # ── Marketplace commission check ───────────────────────────────
        is_marketplace = getattr(request, "source_channel", None) == "marketplace"
        commission_agreed = getattr(vehicle, "marketplace_commission_agreed", False)
        if is_marketplace and not commission_agreed:
            try:
                await create_notification(
                    db=self.db,
                    user_id=user_id,
                    title="⚠️ Назначение отклонено",
                    body=(
                        f"Техника «{vehicle.name}» не может быть назначена на заказ из маркетплейса. "
                        "Необходимо дать согласие на комиссию 10% в карточке техники."
                    ),
                    channel="in_app",
                )
            except Exception:
                pass
            raise RequestServiceError(
                403,
                f"Техника '{vehicle.name}' не может быть назначена на заказ из маркетплейса. "
                "Собственник не дал согласие на комиссию 10%. "
                "Для участия в маркетплейсе необходимо дать согласие в карточке техники.",
            )

        # ── Determine assignment period ────────────────────────────────
        p_start = planned_start or request.planned_start
        p_end = planned_end or request.planned_end

        if p_start >= p_end:
            raise RequestServiceError(422, "planned_start must be before planned_end")

        # ── Check overlapping assignments ──────────────────────────────
        overlap = self.db.scalar(
            select(RequestAssignment).where(
                RequestAssignment.vehicle_id == vehicle_id,
                RequestAssignment.request_id != request_id,
                RequestAssignment.status.in_(BLOCKING_ASSIGNMENT_STATUSES),
                RequestAssignment.planned_start < p_end,
                RequestAssignment.planned_end > p_start,
            )
        )

        if overlap:
            raise RequestServiceError(
                409,
                f"Vehicle '{vehicle.name}' already assigned to request #{overlap.request_id} "
                f"for this period ({overlap.planned_start:%d.%m %H:%M} — {overlap.planned_end:%d.%m %H:%M})",
            )

        # ── Idempotency check ──────────────────────────────────────────
        existing = (
            self.db.query(RequestAssignment)
            .filter(
                RequestAssignment.request_id == request_id,
                RequestAssignment.status.in_(BLOCKING_ASSIGNMENT_STATUSES),
            )
            .first()
        )

        if existing:
            logger.info(f"Request #{request_id} already has active assignment #{existing.id}")
            self.db.refresh(request)
            return request

        # ── Create assignment ──────────────────────────────────────────
        try:
            assignment = RequestAssignment(
                request_id=request.id,
                vehicle_id=vehicle_id,
                operator_id=operator_id,
                planned_start=p_start,
                planned_end=p_end,
                status="planned",
            )
            self.db.add(assignment)
            self.db.flush()

            # Update request status
            old_status = request.status
            request.status = "assigned"
            request.assigned_vehicle_id = vehicle_id
            request.assigned_operator_id = operator_id

            # Status log
            self.db.add(
                RequestStatusLog(
                    request_id=request.id,
                    from_status=old_status.value if hasattr(old_status, "value") else old_status,
                    to_status="assigned",
                    changed_by_user_id=user_id,
                    comment=f"Назначена техника: {vehicle.name}",
                )
            )

            # Auto-create ShiftTask if operator assigned
            if operator_id is not None:
                existing_task = (
                    self.db.query(ShiftTask)
                    .filter(
                        ShiftTask.request_id == request_id,
                        ShiftTask.assignment_id == assignment.id,
                    )
                    .first()
                )
                if not existing_task:
                    shift_task = ShiftTask(
                        request_id=request_id,
                        assignment_id=assignment.id,
                        operator_id=operator_id,
                        vehicle_id=vehicle_id,
                        shift_date=p_start.date(),
                        shift_number=1,
                        status=ShiftTaskStatus.draft,
                        company_id=company_id,
                    )
                    self.db.add(shift_task)
                    logger.info(
                        f"Auto-created ShiftTask for assignment #{assignment.id} "
                        f"on date {p_start.date()}, operator #{operator_id}"
                    )
            else:
                logger.info(f"Skipping ShiftTask creation: no operator for request #{request_id}")

            self.db.commit()
            self.db.refresh(request)

            logger.info(
                f"Request #{request_id} assigned: vehicle={vehicle.name}, assignment=#{assignment.id}"
            )

            # Notification
            try:
                await create_notification(
                    db=self.db,
                    user_id=user_id,
                    title="Техника назначена на заявку",
                    body=f"{vehicle.name} → Заявка #{request.id} ({request.work_type or 'без типа'})",
                    channel="in_app",
                )
            except Exception as e:
                logger.warning("Failed to send assignment notification: %s", e)

            return request

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"IntegrityError on request #{request_id} assign: {e}")
            raise RequestServiceError(409, "Назначение уже существует или нарушена уникальность данных.")
        except RequestServiceError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error on request #{request_id} assign: {e}", exc_info=True)
            raise RequestServiceError(500, f"Ошибка при назначении техники: {str(e)}")
