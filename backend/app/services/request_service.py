"""Request business logic service.

Extracted from app/api/routes/requests.py to separate business logic
from HTTP layer. Route handlers should only handle validation, auth,
and response formatting.
"""

import logging
from datetime import datetime

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
            logger.info(
                f"Request #{request_id} already has active assignment #{existing.id}"
            )
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
                    from_status=(
                        old_status.value if hasattr(old_status, "value") else old_status
                    ),
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
                logger.info(
                    f"Skipping ShiftTask creation: no operator for request #{request_id}"
                )

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
            raise RequestServiceError(
                409, "Назначение уже существует или нарушена уникальность данных."
            )
        except RequestServiceError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Unexpected error on request #{request_id} assign: {e}", exc_info=True
            )
            raise RequestServiceError(500, f"Ошибка при назначении техники: {str(e)}")

    def list_requests(
        self,
        company_ids: list[int],
        status_filter: str | None = None,
        priority: str | None = None,
        client_id: int | None = None,
        vehicle_category_id: int | None = None,
        assigned_vehicle_id: int | None = None,
        work_type: str | None = None,
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List requests with filtering, sorting, and enrichment."""
        from datetime import datetime as dt

        from app.models.catalog import Category, Vehicle
        from app.models.contractor import Contractor

        stmt = (
            select(Request)
            .outerjoin(Contractor, Request.client_id == Contractor.id)
            .outerjoin(Category, Request.vehicle_category_id == Category.id)
            .outerjoin(Vehicle, Request.assigned_vehicle_id == Vehicle.id)
            .where(Request.company_id.in_(company_ids))
        )

        if status_filter:
            stmt = stmt.where(Request.status == status_filter)
        if priority:
            stmt = stmt.where(Request.priority == priority)
        if client_id:
            stmt = stmt.where(Request.client_id == client_id)
        if vehicle_category_id:
            stmt = stmt.where(Request.vehicle_category_id == vehicle_category_id)
        if assigned_vehicle_id:
            stmt = stmt.where(Request.assigned_vehicle_id == assigned_vehicle_id)
        if work_type:
            stmt = stmt.where(Request.work_type.ilike(f"%{work_type}%"))
        if search:
            stmt = stmt.where(
                (Request.work_type.ilike(f"%{search}%"))
                | (Request.object_address.ilike(f"%{search}%"))
            )
        if date_from:
            stmt = stmt.where(Request.planned_start >= dt.fromisoformat(date_from))
        if date_to:
            stmt = stmt.where(Request.planned_end <= dt.fromisoformat(date_to))

        sort_col = getattr(Request, sort_by, Request.created_at)
        if sort_order == "desc":
            stmt = stmt.order_by(sort_col.desc()).offset(offset).limit(limit)
        else:
            stmt = stmt.order_by(sort_col.asc()).offset(offset).limit(limit)

        requests_list = self.db.scalars(stmt).all()

        # Enrichment
        enriched = []
        for req in requests_list:
            data = {
                "id": req.id,
                "client_id": req.client_id,
                "status": (
                    req.status.value
                    if hasattr(req.status, "value")
                    else str(req.status)
                ),
                "request_type": req.request_type,
                "vehicle_category_id": req.vehicle_category_id,
                "work_type": req.work_type,
                "object_address": req.object_address,
                "planned_start": req.planned_start,
                "planned_end": req.planned_end,
                "actual_start": req.actual_start,
                "actual_end": req.actual_end,
                "shift_duration_hours": (
                    float(req.shift_duration_hours)
                    if req.shift_duration_hours
                    else None
                ),
                "client_rate": float(req.client_rate) if req.client_rate else None,
                "rate_type": req.rate_type,
                "estimated_amount": (
                    float(req.estimated_amount) if req.estimated_amount else None
                ),
                "final_amount": float(req.final_amount) if req.final_amount else None,
                "assigned_vehicle_id": req.assigned_vehicle_id,
                "assigned_operator_id": req.assigned_operator_id,
                "assigned_owner_id": req.assigned_owner_id,
                "source_channel": req.source_channel,
                "priority": req.priority,
                "comment": req.comment,
                "company_id": req.company_id,
                "created_by": req.created_by,
                "created_at": req.created_at,
                "updated_at": req.updated_at,
            }

            if req.client_id:
                contractor = self.db.get(Contractor, req.client_id)
                if contractor:
                    data["client_name"] = contractor.name

            if req.vehicle_category_id:
                category = self.db.get(Category, req.vehicle_category_id)
                if category:
                    data["vehicle_category_name"] = category.name

            if req.assigned_vehicle_id:
                vehicle = self.db.get(Vehicle, req.assigned_vehicle_id)
                if vehicle:
                    data["assigned_vehicle_name"] = vehicle.name

            enriched.append(data)

        return enriched

    def _fetch_requests_for_export(
        self,
        company_ids: list[int],
        status_filter: str | None = None,
        priority: str | None = None,
        client_id: int | None = None,
        vehicle_category_id: int | None = None,
        assigned_vehicle_id: int | None = None,
        work_type: str | None = None,
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[dict]:
        """Fetch and enrich requests for export (shared by PDF/Excel)."""
        from datetime import datetime as dt

        from app.models.catalog import Category, Vehicle
        from app.models.contractor import Contractor

        stmt = (
            select(Request)
            .outerjoin(Contractor, Request.client_id == Contractor.id)
            .outerjoin(Category, Request.vehicle_category_id == Category.id)
            .outerjoin(Vehicle, Request.assigned_vehicle_id == Vehicle.id)
            .where(Request.company_id.in_(company_ids))
        )

        if status_filter:
            stmt = stmt.where(Request.status == status_filter)
        if priority:
            stmt = stmt.where(Request.priority == priority)
        if client_id:
            stmt = stmt.where(Request.client_id == client_id)
        if vehicle_category_id:
            stmt = stmt.where(Request.vehicle_category_id == vehicle_category_id)
        if assigned_vehicle_id:
            stmt = stmt.where(Request.assigned_vehicle_id == assigned_vehicle_id)
        if work_type:
            stmt = stmt.where(Request.work_type.ilike(f"%{work_type}%"))
        if search:
            stmt = stmt.where(
                (Request.work_type.ilike(f"%{search}%"))
                | (Request.object_address.ilike(f"%{search}%"))
            )
        if date_from:
            stmt = stmt.where(Request.planned_start >= dt.fromisoformat(date_from))
        if date_to:
            stmt = stmt.where(Request.planned_end <= dt.fromisoformat(date_to))

        sort_col = getattr(Request, sort_by, Request.created_at)
        stmt = stmt.order_by(
            sort_col.desc() if sort_order == "desc" else sort_col.asc()
        ).limit(5000)

        requests_list = self.db.scalars(stmt).all()

        enriched = []
        for req in requests_list:
            cat_name = ""
            if req.vehicle_category_id:
                cat = self.db.get(Category, req.vehicle_category_id)
                if cat:
                    cat_name = cat.name
            client_name = ""
            if req.client_id:
                contractor = self.db.get(Contractor, req.client_id)
                if contractor:
                    client_name = contractor.name
            vehicle_name = ""
            if req.assigned_vehicle_id:
                v = self.db.get(Vehicle, req.assigned_vehicle_id)
                if v:
                    vehicle_name = v.name
            enriched.append(
                {
                    "id": req.id,
                    "work_type": req.work_type,
                    "object_address": req.object_address,
                    "planned_start": req.planned_start,
                    "planned_end": req.planned_end,
                    "status": req.status,
                    "priority": req.priority,
                    "estimated_amount": req.estimated_amount,
                    "final_amount": req.final_amount,
                    "vehicle_category_name": cat_name,
                    "assigned_vehicle_name": vehicle_name,
                    "client_name": client_name,
                }
            )

        return enriched

    def export_requests_pdf(self, **filters) -> bytes:
        """Generate PDF export of filtered requests."""
        from app.utils.export_utils import export_requests_pdf as gen_pdf

        enriched = self._fetch_requests_for_export(**filters)
        return gen_pdf(enriched)

    def export_requests_excel(self, **filters) -> bytes:
        """Generate Excel export of filtered requests."""
        from app.utils.export_utils import export_requests_excel as gen_excel

        enriched = self._fetch_requests_for_export(**filters)
        return gen_excel(enriched)

    async def create_request(
        self,
        payload_data: dict,
        company_id: int,
        user_id: int,
    ) -> Request:
        """Create a new request with auto-pricing and notifications."""
        from app.models.catalog import Category
        from app.services.notification_service import create_notification
        from app.services.pricing_service import pricing_service

        # Validate planned dates
        planned_start = payload_data.get("planned_start")
        planned_end = payload_data.get("planned_end")
        if planned_start and planned_end and planned_end <= planned_start:
            raise RequestServiceError(422, "planned_end must be after planned_start")

        # Validate vehicle_category_id
        cat_id = payload_data.get("vehicle_category_id")
        if cat_id:
            cat = self.db.get(Category, cat_id)
            if not cat:
                raise RequestServiceError(422, f"Vehicle category {cat_id} not found")

        # === Self-transaction prevention ===
        # Если указан vehicle_id, проверяем что техника не принадлежит той же компании
        vehicle_id = payload_data.get("vehicle_id") or payload_data.get(
            "assigned_vehicle_id"
        )
        if vehicle_id:
            from app.models.catalog import Vehicle as VehicleModel

            vehicle = self.db.get(VehicleModel, vehicle_id)
            if vehicle and vehicle.company_id == company_id:
                raise RequestServiceError(
                    422, "Cannot create request for your own vehicle"
                )

        # Create request
        request = Request(
            **payload_data,
            company_id=company_id,
            created_by=user_id,
        )
        self.db.add(request)
        self.db.flush()

        # Status log
        self.db.add(
            RequestStatusLog(
                request_id=request.id,
                from_status=None,
                to_status="new",
                changed_by_user_id=user_id,
                comment="Заявка создана",
            )
        )

        # === Server-Authoritative Pricing ===
        # ВСЕГДА пересчитываем на сервере, клиентские значения игнорируются
        try:
            estimate = pricing_service.calculate_estimate(
                region=request.region,
                rate_type=request.rate_type or "per_shift",
                shift_duration_hours=(
                    float(request.shift_duration_hours)
                    if request.shift_duration_hours
                    else None
                ),
                custom_rate=float(request.client_rate) if request.client_rate else None,
            )
            request.estimated_amount = estimate["estimated_amount"]
            request.client_rate = estimate["rate_used"]
            request.rate_type = estimate["rate_type"]
        except Exception as e:
            logger.warning(f"Auto-pricing failed for request #{request.id}: {e}")

        self.db.commit()
        self.db.refresh(request)

        # Notifications
        try:
            await create_notification(
                db=self.db,
                user_id=user_id,
                title="Новая заявка создана",
                body=f"Заявка #{request.id} ({request.work_type or 'без типа'}) на период {request.planned_start:%d.%m} — {request.planned_end:%d.%m}",
                channel="in_app",
            )
        except Exception as e:
            try:
                from app.services.max_messenger_service import (
                    max_messenger_service,
                    notification_templates,
                )

                title, body = notification_templates.request_created(
                    request_id=request.id,
                    work_type=request.work_type or "без типа",
                    address=request.object_address or "не указан",
                    planned_start=request.planned_start.strftime("%d.%m.%Y %H:%M"),
                )
                await max_messenger_service.notify_company_dispatchers(
                    self.db, company_id, title, body
                )
            except Exception as max_err:
                logger.warning("MAX notification failed: %s", max_err)
            logger.warning("Failed to send notification: %s", e)

        return request

    async def bulk_response_action(
        self,
        assignment_ids: list[int],
        action: str,
        reason: str,
        company_id: int,
        user_id: int,
    ) -> dict:
        """Bulk approve or reject response assignments."""
        from app.models.dispatch import RequestAssignment, RequestStatusLog
        from app.models.shift import ShiftTask, ShiftTaskStatus
        from app.services.notification_service import create_notification
        from app.services.websocket_manager import manager

        if action not in ("approve", "reject"):
            raise RequestServiceError(400, "action must be 'approve' or 'reject'")

        processed = 0
        errors = []

        for aid in assignment_ids:
            assignment = self.db.get(RequestAssignment, aid)
            if not assignment:
                errors.append({"id": aid, "error": "Not found"})
                continue

            request = self.db.get(Request, assignment.request_id)
            if not request or request.company_id != company_id:
                errors.append({"id": aid, "error": "Access denied"})
                continue

            if assignment.status != "pending_approval":
                errors.append({"id": aid, "error": f"Already {assignment.status}"})
                continue

            if action == "approve":
                assignment.status = "approved"
                vehicle = self.db.get(Vehicle, assignment.vehicle_id)

                # Reject other responses for same request
                others = (
                    self.db.execute(
                        select(RequestAssignment).where(
                            RequestAssignment.request_id == assignment.request_id,
                            RequestAssignment.id != aid,
                            RequestAssignment.status == "pending_approval",
                        )
                    )
                    .scalars()
                    .all()
                )
                for o in others:
                    o.status = "rejected"

                # Create ShiftTask
                shift_task = ShiftTask(
                    request_id=assignment.request_id,
                    assignment_id=assignment.id,
                    vehicle_id=assignment.vehicle_id,
                    operator_id=getattr(vehicle, "current_driver_id", None),
                    shift_date=(
                        request.planned_start.date()
                        if request.planned_start
                        else date.today()
                    ),
                    status=ShiftTaskStatus.draft,
                    company_id=request.company_id,
                )
                self.db.add(shift_task)
                request.status = "assigned"

                try:
                    await create_notification(
                        db=self.db,
                        user_id=assignment.assigned_by,
                        title="✅ Ваш отклик одобрен!",
                        body=f"Заявка #{request.id} подтверждена.",
                        channel="in_app",
                    )
                    await manager.send_to_user(
                        assignment.assigned_by,
                        {"type": "response_approved", "request_id": request.id},
                    )
                except Exception:
                    pass

            else:  # reject
                assignment.status = "rejected"
                try:
                    await create_notification(
                        db=self.db,
                        user_id=assignment.assigned_by,
                        title="❌ Ваш отклик отклонён",
                        body=f"Заявка #{request.id}: {reason or 'Выбран другой исполнитель'}",
                        channel="in_app",
                    )
                    await manager.send_to_user(
                        assignment.assigned_by,
                        {"type": "response_rejected", "request_id": request.id},
                    )
                except Exception:
                    pass

            self.db.add(
                RequestStatusLog(
                    request_id=assignment.request_id,
                    from_status=(
                        request.status if action == "reject" else "has_responses"
                    ),
                    to_status=request.status,
                    changed_by_user_id=user_id,
                    comment=f"Массовое {action}: отклик #{aid}",
                )
            )
            processed += 1

        self.db.commit()
        return {"processed": processed, "errors": errors, "action": action}

    async def approve_response(
        self,
        request_id: int,
        assignment_id: int,
        company_id: int,
        user_id: int,
    ) -> dict:
        """Approve a marketplace response and create shift task."""
        from app.models.dispatch import RequestAssignment, RequestStatusLog
        from app.models.shift import ShiftTask, ShiftTaskStatus
        from app.services.notification_service import create_notification

        request = self.db.get(Request, request_id)
        if not request or request.company_id != company_id:
            raise RequestServiceError(404, "Request not found")

        assignment = self.db.get(RequestAssignment, assignment_id)
        if not assignment or assignment.request_id != request_id:
            raise RequestServiceError(404, "Response not found")

        if assignment.status != "pending_approval":
            raise RequestServiceError(409, f"Response already {assignment.status}")

        vehicle = self.db.get(Vehicle, assignment.vehicle_id)

        assignment.status = "approved"
        assignment.assigned_by = user_id

        # Reject other pending responses
        other_responses = (
            self.db.execute(
                select(RequestAssignment).where(
                    RequestAssignment.request_id == request_id,
                    RequestAssignment.id != assignment_id,
                    RequestAssignment.status == "pending_approval",
                )
            )
            .scalars()
            .all()
        )
        for resp in other_responses:
            resp.status = "rejected"

        # Auto-create ShiftTask
        shift_task = ShiftTask(
            request_id=request_id,
            vehicle_id=assignment.vehicle_id,
            shift_date=request.planned_start.date() if request.planned_start else None,
            status=(
                ShiftTaskStatus.planned
                if hasattr(ShiftTaskStatus, "planned")
                else "planned"
            ),
            company_id=company_id,
        )
        self.db.add(shift_task)

        self.db.add(
            RequestStatusLog(
                request_id=request_id,
                from_status=request.status,
                to_status="assigned",
                changed_by_user_id=user_id,
                comment=f"Одобрен отклик: {vehicle.name if vehicle else 'N/A'}",
            )
        )

        request.status = "assigned"
        self.db.commit()

        try:
            await create_notification(
                db=self.db,
                user_id=assignment.assigned_by,
                title="✅ Ваш отклик одобрен!",
                body=f"Заявка #{request_id} подтверждена. Техника: {vehicle.name if vehicle else 'N/A'}. Создана смена.",
                channel="in_app",
            )
        except Exception:
            pass

        return {
            "message": "Отклик одобрен, смена создана",
            "shift_task_id": shift_task.id,
        }

    async def reject_response(
        self,
        request_id: int,
        assignment_id: int,
        reason: str,
        company_id: int,
        user_id: int,
    ) -> dict:
        """Reject a marketplace response."""
        from app.models.dispatch import RequestAssignment, RequestStatusLog
        from app.services.notification_service import create_notification

        request = self.db.get(Request, request_id)
        if not request or request.company_id != company_id:
            raise RequestServiceError(404, "Request not found")

        assignment = self.db.get(RequestAssignment, assignment_id)
        if not assignment or assignment.request_id != request_id:
            raise RequestServiceError(404, "Response not found")

        if assignment.status != "pending_approval":
            raise RequestServiceError(409, f"Response already {assignment.status}")

        assignment.status = "rejected"

        self.db.add(
            RequestStatusLog(
                request_id=request_id,
                from_status=request.status,
                to_status=request.status,
                changed_by_user_id=user_id,
                comment=f"Отклик отклонён: {reason or 'Без причины'}",
            )
        )
        self.db.commit()

        try:
            await create_notification(
                db=self.db,
                user_id=assignment.assigned_by,
                title="❌ Ваш отклик отклонён",
                body=f"Заявка #{request_id}: {reason or 'Владелец выбрал другого исполнителя'}",
                channel="in_app",
            )
        except Exception:
            pass

        return {"message": "Отклик отклонён"}

    def get_request_timeline(
        self,
        request_id: int,
        company_id: int,
    ) -> list[dict]:
        """Get status change history for a request."""
        from app.models.auth import User as UserModel
        from app.models.dispatch import RequestAssignment, RequestStatusLog

        request = self.db.get(Request, request_id)
        if not request:
            raise RequestServiceError(404, "Request not found")

        # Access check: owner or contractor with response
        has_access = request.company_id == company_id
        if not has_access:
            resp = self.db.execute(
                select(RequestAssignment)
                .join(Vehicle)
                .where(
                    RequestAssignment.request_id == request_id,
                    Vehicle.company_id == company_id,
                )
            ).scalar_one_or_none()
            has_access = resp is not None

        if not has_access:
            raise RequestServiceError(403, "Access denied")

        logs = (
            self.db.execute(
                select(RequestStatusLog)
                .where(RequestStatusLog.request_id == request_id)
                .order_by(RequestStatusLog.changed_at.desc())
            )
            .scalars()
            .all()
        )

        result = []
        for log in logs:
            user_name = ""
            if log.changed_by_user_id:
                user = self.db.get(UserModel, log.changed_by_user_id)
                user_name = (
                    user.full_name or user.email
                    if user
                    else f"User#{log.changed_by_user_id}"
                )
            result.append(
                {
                    "id": log.id,
                    "from_status": log.from_status,
                    "to_status": log.to_status,
                    "comment": log.comment,
                    "changed_by": user_name,
                    "created_at": (
                        log.created_at.isoformat() if log.created_at else None
                    ),
                }
            )

        return result

    def update_request_put(
        self,
        request_id: int,
        company_id: int,
        user_id: int,
        work_type: str | None = None,
        object_address: str | None = None,
        planned_start: str | None = None,
        planned_end: str | None = None,
        client_rate: float | None = None,
        rate_type: str | None = None,
        payment_terms_days: int | None = None,
        marketplace_mode: str | None = None,
        priority: str | None = None,
        requirements: dict | None = None,
    ) -> dict:
        """Full update of request fields (PUT semantics)."""
        from datetime import datetime
        from decimal import Decimal

        from app.models.dispatch import RequestStatusLog

        request = self.db.get(Request, request_id)
        if not request or request.company_id != company_id:
            raise RequestServiceError(404, "Request not found")

        if request.status == "assigned":
            raise RequestServiceError(409, "Cannot edit assigned request")

        changes = []
        if work_type is not None and work_type != request.work_type:
            changes.append(f"work_type: {request.work_type} → {work_type}")
            request.work_type = work_type
        if object_address is not None and object_address != request.object_address:
            changes.append(f"address: {request.object_address} → {object_address}")
            request.object_address = object_address
        if planned_start is not None:
            request.planned_start = datetime.fromisoformat(planned_start)
        if planned_end is not None:
            request.planned_end = datetime.fromisoformat(planned_end)
        if client_rate is not None:
            request.client_rate = Decimal(str(client_rate))
        if rate_type is not None:
            request.rate_type = rate_type
        if payment_terms_days is not None:
            request.payment_terms_days = payment_terms_days
        if marketplace_mode is not None:
            request.marketplace_mode = marketplace_mode
        if priority is not None:
            request.priority = priority
        if requirements is not None:
            request.requirements = requirements

        if changes:
            self.db.add(
                RequestStatusLog(
                    request_id=request_id,
                    from_status=request.status,
                    to_status=request.status,
                    changed_by_user_id=user_id,
                    comment=f"Редактирование: {'; '.join(changes)}",
                )
            )

        self.db.commit()
        return {"message": "Заявка обновлена", "id": request_id}

    async def complete_request(
        self,
        request_id: int,
        company_id: int,
        user_id: int,
        final_amount: float | None = None,
        comment: str | None = None,
    ) -> Request:
        """
        Завершить заявку: перевести в статус 'completed' и автоматически создать акт.

        Логика:
        1. Проверить что заявка в статусе assigned/confirmed/in_progress
        2. Перевести в статус completed
        3. Установить actual_end = now
        4. Вычислить final_amount (или использовать переданный)
        5. Автоматически создать Act из заявки
        6. Автоматически сгенерировать PDF акта
        """
        from datetime import date, datetime
        from decimal import Decimal

        from app.models.dispatch import RequestStatus, RequestStatusLog
        from app.models.finance import Act, DocumentStatus
        from app.services.finance_service import (
            generate_and_save_act_pdf,
            generate_document_number,
        )

        request = self.db.get(Request, request_id)
        if not request or request.company_id != company_id:
            raise RequestServiceError(404, "Request not found")

        allowed = (
            RequestStatus.assigned,
            RequestStatus.confirmed,
            RequestStatus.in_progress,
        )
        if request.status not in allowed:
            raise RequestServiceError(
                409,
                f"Cannot complete request with status '{request.status.value}'",
            )

        old_status = request.status
        request.status = RequestStatus.completed
        request.actual_end = datetime.utcnow()

        if final_amount is not None:
            request.final_amount = Decimal(str(final_amount))
        elif request.estimated_amount:
            request.final_amount = request.estimated_amount
        elif request.client_rate and request.shift_duration_hours:
            request.final_amount = request.client_rate * request.shift_duration_hours
        else:
            request.final_amount = Decimal("0")

        self.db.add(
            RequestStatusLog(
                request_id=request.id,
                from_status=(
                    old_status.value
                    if hasattr(old_status, "value")
                    else str(old_status)
                ),
                to_status="completed",
                changed_by_user_id=user_id,
                comment=comment or f"Заявка завершена пользователем #{user_id}",
            )
        )
        self.db.flush()

        act = None
        if request.final_amount and request.final_amount > 0:
            subtotal = request.final_amount
            vat_amount = (subtotal * Decimal("20") / Decimal("120")).quantize(
                Decimal("0.01")
            )

            act = Act(
                document_number=generate_document_number(self.db, "ACT"),
                request_id=request.id,
                client_id=request.client_id,
                company_id=request.company_id,
                total_amount=subtotal,
                vat_amount=vat_amount,
                vat_rate=Decimal("20"),
                tax_system="OSNO",
                is_vat_included=True,
                act_date=date.today(),
                status=DocumentStatus.draft,
                comment=f"Автосоздан при завершении заявки #{request.id}",
            )
            self.db.add(act)
            self.db.flush()
            logger.info(
                "Auto-created Act #%s for Request #%s: total=%s",
                act.id,
                request.id,
                act.total_amount,
            )

        self.db.commit()
        self.db.refresh(request)

        if act:
            try:
                pdf_result = generate_and_save_act_pdf(act.id, self.db)
                if pdf_result:
                    logger.info(
                        "PDF auto-generated for act #%s: %s",
                        act.id,
                        pdf_result.get("path"),
                    )
            except Exception as e:
                logger.warning(f"PDF generation failed for act #{act.id}: {e}")

        # 8. Trigger review request notifications if rental exists
        await self._notify_review_opportunity(request)

        return request

    async def _notify_review_opportunity(self, request: Request) -> None:
        """
        Отправляет уведомления участникам сделки о возможности оставить отзыв.

        Вызывается после завершения заявки. Проверяет наличие связанного
        завершённого Rental и отправляет уведомления клиенту и собственнику.
        """
        from app.models.rental import Rental, RentalStatus
        from app.services.notification_service import create_notification

        # Check if request has associated rental
        rental = self.db.query(Rental).filter(Rental.request_id == request.id).first()

        if not rental:
            logger.info(
                "No rental found for request #%s, skipping review notifications",
                request.id,
            )
            return

        if rental.status != RentalStatus.COMPLETED:
            logger.info(
                "Rental #%s status is %s, not COMPLETED. Skipping review notifications",
                rental.id,
                rental.status.value,
            )
            return

        # Get participants
        client_contractor_id = rental.client_id
        owner_contractor_id = request.assigned_owner_id

        if not client_contractor_id:
            logger.warning(
                "Rental #%s has no client_id, cannot send review notifications",
                rental.id,
            )
            return

        # Notify client to review owner
        try:
            # Get user ID from contractor
            from app.models.auth import User
            from app.models.contractor import Contractor

            client_contractor = self.db.get(Contractor, client_contractor_id)
            if client_contractor:
                # Find user associated with this contractor
                client_user = (
                    self.db.query(User)
                    .filter(User.email == client_contractor.contact_email)
                    .first()
                )
                if client_user:
                    await create_notification(
                        db=self.db,
                        user_id=client_user.id,
                        title="⭐ Оцените сотрудничество",
                        body=(
                            f"Сделка по заявке #{request.id} завершена. "
                            "Оставьте отзыв о компании-исполнителе — это поможет другим заказчикам."
                        ),
                        channel="in_app",
                    )
                    logger.info(
                        "Sent review request to client (user #%s) for rental #%s",
                        client_user.id,
                        rental.id,
                    )
        except Exception as e:
            logger.warning(f"Failed to notify client about review: {e}")

        # Notify owner to review client
        try:
            if owner_contractor_id:
                owner_contractor = self.db.get(Contractor, owner_contractor_id)
                if owner_contractor:
                    owner_user = (
                        self.db.query(User)
                        .filter(User.email == owner_contractor.contact_email)
                        .first()
                    )
                    if owner_user:
                        await create_notification(
                            db=self.db,
                            user_id=owner_user.id,
                            title="⭐ Оцените клиента",
                            body=(
                                f"Сделка по заявке #{request.id} завершена. "
                                "Оставьте отзыв о заказчике — это поможет другим исполнителям."
                            ),
                            channel="in_app",
                        )
                        logger.info(
                            "Sent review request to owner (user #%s) for rental #%s",
                            owner_user.id,
                            rental.id,
                        )
        except Exception as e:
            logger.warning(f"Failed to notify owner about review: {e}")

    async def update_request_patch(
        self,
        request_id: int,
        update_data: dict,
        company_id: int,
        user_id: int,
    ) -> Request:
        """Partial update of request (PATCH semantics)."""
        from app.models.dispatch import RequestStatusLog
        from app.services.notification_service import create_notification

        request = self.db.get(Request, request_id)
        if not request or request.company_id != company_id:
            raise RequestServiceError(404, "Request not found")

        old_status = request.status

        if "status" in update_data and update_data["status"] != old_status:
            new_status = update_data["status"]
            old_status_str = (
                old_status.value if hasattr(old_status, "value") else str(old_status)
            )
            new_status_str = (
                new_status.value if hasattr(new_status, "value") else str(new_status)
            )

            self.db.add(
                RequestStatusLog(
                    request_id=request.id,
                    from_status=old_status,
                    to_status=new_status,
                    changed_by_user_id=user_id,
                    comment=f"Статус изменён вручную: {old_status_str} -> {new_status_str}",
                )
            )

            if request.created_by and request.created_by != user_id:
                await create_notification(
                    db=self.db,
                    user_id=request.created_by,
                    title=f"Статус заявки #{request.id} изменён",
                    body=f"Заявка '{request.work_type}' переведена из '{old_status_str}' в '{new_status_str}'",
                    channel="in_app",
                )

        for field, value in update_data.items():
            setattr(request, field, value)

        self.db.commit()
        self.db.refresh(request)
        return request
