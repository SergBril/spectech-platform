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
                "status": req.status.value if hasattr(req.status, "value") else str(req.status),
                "request_type": req.request_type,
                "vehicle_category_id": req.vehicle_category_id,
                "work_type": req.work_type,
                "object_address": req.object_address,
                "planned_start": req.planned_start,
                "planned_end": req.planned_end,
                "actual_start": req.actual_start,
                "actual_end": req.actual_end,
                "shift_duration_hours": float(req.shift_duration_hours) if req.shift_duration_hours else None,
                "client_rate": float(req.client_rate) if req.client_rate else None,
                "rate_type": req.rate_type,
                "estimated_amount": float(req.estimated_amount) if req.estimated_amount else None,
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
            enriched.append({
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
            })

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

        # Auto-calculate estimated amount
        if not request.estimated_amount:
            try:
                estimate = pricing_service.calculate_estimate(
                    region=request.region,
                    rate_type=request.rate_type or "per_shift",
                    shift_duration_hours=float(request.shift_duration_hours) if request.shift_duration_hours else None,
                    custom_rate=float(request.client_rate) if request.client_rate else None,
                )
                request.estimated_amount = estimate["estimated_amount"]
                if not request.client_rate:
                    request.client_rate = estimate["rate_used"]
                if not request.rate_type:
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
                from app.services.max_messenger_service import max_messenger_service, notification_templates
                title, body = notification_templates.request_created(
                    request_id=request.id,
                    work_type=request.work_type or "без типа",
                    address=request.object_address or "не указан",
                    planned_start=request.planned_start.strftime("%d.%m.%Y %H:%M"),
                )
                await max_messenger_service.notify_company_dispatchers(self.db, company_id, title, body)
            except Exception as max_err:
                logger.warning("MAX notification failed: %s", max_err)
            logger.warning("Failed to send notification: %s", e)

        return request

