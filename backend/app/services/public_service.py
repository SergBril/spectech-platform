"""Сервис публичных API эндпоинтов."""

import logging
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.dispatch import Request as DispatchRequest
from app.models.dispatch import RequestAssignment, RequestStatusLog
from app.models.finance import Payout
from app.models.review import Review

logger = logging.getLogger("spectech.public")

from pydantic import BaseModel


class PublicCompanyRead(BaseModel):
    id: int
    name: str
    legal_name: str | None = None
    company_type: str | None = None
    description: str | None = None
    logo_url: str | None = None
    city: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    total_deals: int = 0
    is_verified: bool = False
    vehicles_count: int = 0
    created_at: str | None = None

    model_config = {"from_attributes": True}


from datetime import UTC

from app.schemas.public import (
    PublicRequestResponse,
    PublicVehicleRead,
    VehicleAvailabilityResponse,
)


class PublicService:
    """Бизнес-логика публичных эндпоинтов."""

    def _to_float(self, value):
        """Безопасное конвертирование Decimal/str/int → float."""
        if value is None:
            return None
        try:
            if isinstance(value, Decimal):
                return float(value)
            return float(value)
        except (TypeError, ValueError, AttributeError):
            return None

    def _normalize_photos(self, value):
        """Нормализация поля photos из БД (может быть list, dict, str, None)."""
        if value is None:
            return None
        if isinstance(value, list):
            return [str(x) for x in value if x is not None]
        if isinstance(value, str):
            return [value] if value else None
        if isinstance(value, dict):
            # Если это объект, преобразуем в список значений
            return [str(v) for v in value.values() if v is not None]
        return None

    def _build_vehicle_response(self, db: Session, company_id: int, v, company_name):
        """Построение ответа для техники."""
        # Получаем имя компании из relationship, если не передано явно
        if company_name is None:
            try:
                company_name = v.company.name if v.company else None
            except Exception:
                company_name = None

        return PublicVehicleRead(
            id=v.id,
            name=v.name,
            category_name=v.category.name if v.category else None,
            year=v.year,
            status=v.status,
            hourly_rate=self._to_float(getattr(v, "hourly_rate", None)),
            shift_rate=self._to_float(getattr(v, "shift_rate", None)),
            is_available_for_rent=bool(getattr(v, "is_available_for_rent", False)),
            photos=self._normalize_photos(getattr(v, "photos", None)),
            owner_company_id=v.company_id or 0,
            owner_company_name=company_name,
            marketplace_commission_agreed=bool(
                getattr(v, "marketplace_commission_agreed", False)
            ),
            marketplace_commission_rate=self._to_float(
                getattr(v, "marketplace_commission_rate", None)
            ),
        )

    def health_check(self, db: Session):
        """🌐 Проверка работоспособности."""
        return {"status": "ok", "timestamp": "2026-10-12"}

    def list_public_companies(
        self,
        db: Session,
        company_type,
        city,
        limit,
        offset,
        company_id: int | None = None,
    ):
        """🌐 Публичный список компаний (для маркетплейса)."""
        try:
            stmt = select(Company).where(Company.is_active == True)

            if company_type and hasattr(Company, "company_type"):
                stmt = stmt.where(Company.company_type == company_type)
            if city and hasattr(Company, "city"):
                stmt = stmt.where(Company.city == city)

            stmt = stmt.offset(offset).limit(limit).order_by(Company.created_at.desc())
            companies = db.scalars(stmt).all()

            result = []
            # Рассчитываем рейтинг и количество сделок для каждой компании
            from app.models.dispatch import Request
            from app.services.reviews_service import ReviewsService

            def get_company_metrics(company_id_: int) -> tuple[float, int]:
                rating_data = ReviewsService.get_company_rating(db, company_id_)
                avg_rating = float(rating_data.get("average_rating") or 0)

                deals_count = (
                    db.query(func.count(Request.id))
                    .filter(
                        Request.company_id == company_id_,
                        Request.status == "completed",
                    )
                    .scalar()
                    or 0
                )

                return round(avg_rating, 2) if avg_rating > 0 else 0.0, int(deals_count)

            for c in companies:
                company_rating, company_deals = get_company_metrics(c.id)
                vehicles_count = (
                    db.query(Vehicle).filter(Vehicle.company_id == c.id).count()
                )
                result.append(
                    PublicCompanyRead(
                        id=c.id,
                        name=c.name,
                        legal_name=c.legal_name,
                        company_type=getattr(c, "company_type", None),
                        description=getattr(c, "description", None),
                        logo_url=getattr(c, "logo_url", None),
                        city=getattr(c, "city", None),
                        phone=getattr(c, "phone", None),
                        website=getattr(c, "website", None),
                        rating=company_rating,
                        total_deals=company_deals,
                        is_verified=bool(getattr(c, "is_verified", False)),
                        vehicles_count=vehicles_count,
                        created_at=c.created_at.isoformat() if c.created_at else None,
                    )
                )
            return result

        except Exception as e:
            logger.exception("❌ Error in list_public_companies: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def get_public_company(self, db: Session, company_id: int | None = None):
        """🌐 Публичный профиль компании."""
        try:
            company = db.get(Company, company_id)
            if not company or not company.is_active:
                raise HTTPException(status_code=404, detail="Company not found")

            vehicles_count = (
                db.query(Vehicle).filter(Vehicle.company_id == company.id).count()
            )

            return PublicCompanyRead(
                id=company.id,
                name=company.name,
                legal_name=company.legal_name,
                company_type=getattr(company, "company_type", None),
                description=getattr(company, "description", None),
                logo_url=getattr(company, "logo_url", None),
                city=getattr(company, "city", None),
                phone=getattr(company, "phone", None),
                website=getattr(company, "website", None),
                rating=4.5,
                total_deals=10,
                is_verified=bool(getattr(company, "is_verified", False)),
                vehicles_count=vehicles_count,
                created_at=(
                    company.created_at.isoformat() if company.created_at else None
                ),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error in get_public_company: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def get_public_company_vehicles(
        self,
        db: Session,
        category_id,
        available_only,
        limit,
        company_id: int | None = None,
    ):
        """🌐 Публичный список техники компании."""
        try:
            company = db.get(Company, company_id)
            if not company or not company.is_active:
                raise HTTPException(status_code=404, detail="Company not found")

            stmt = select(Vehicle).where(Vehicle.company_id == company_id)

            if category_id:
                stmt = stmt.where(Vehicle.category_id == category_id)
            if available_only and hasattr(Vehicle, "is_available_for_rent"):
                stmt = stmt.where(Vehicle.is_available_for_rent == True)

            stmt = stmt.limit(limit)
            vehicles = db.scalars(stmt).all()

            return [
                self._build_vehicle_response(db, company.id, v, company.name)
                for v in vehicles
            ]

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error in get_public_company_vehicles: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def list_public_vehicles(
        self,
        db: Session,
        category_id,
        available_only,
        min_hourly_rate,
        max_hourly_rate,
        limit,
        offset,
        company_id: int | None = None,
    ):
        """
        🌐 Публичный каталог доступной техники (для маркетплейса).

        Основной endpoint для поиска техники заказчиками.
        """
        try:
            stmt = (
                select(Vehicle)
                .join(Company, Vehicle.company_id == Company.id)
                .where(Company.is_active == True)
            )

            # В маркетплейсе показываем только технику с согласием на комиссию
            stmt = stmt.where(Vehicle.marketplace_commission_agreed == True)

            if category_id:
                stmt = stmt.where(Vehicle.category_id == category_id)
            if company_id:
                stmt = stmt.where(Vehicle.company_id == company_id)
            if available_only and hasattr(Vehicle, "is_available_for_rent"):
                stmt = stmt.where(Vehicle.is_available_for_rent == True)
            if min_hourly_rate is not None and hasattr(Vehicle, "hourly_rate"):
                stmt = stmt.where(Vehicle.hourly_rate >= min_hourly_rate)
            if max_hourly_rate is not None and hasattr(Vehicle, "hourly_rate"):
                stmt = stmt.where(Vehicle.hourly_rate <= max_hourly_rate)

            stmt = stmt.offset(offset).limit(limit)
            vehicles = db.scalars(stmt).all()

            return [self._build_vehicle_response(db, None, v, None) for v in vehicles]

        except Exception as e:
            logger.exception("❌ Error in list_public_vehicles: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def get_public_vehicle_details(self, db: Session, vehicle_id):
        """
        🌐 Детальная страница техники (публичная).

        Возвращает только опубликованную технику.
        """
        try:
            from app.services.marketplace_service import marketplace_service

            vehicle = marketplace_service.get_vehicle_details(db, vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=404, detail="Vehicle not found or not published"
                )

            return self._build_vehicle_response(db, None, vehicle, None)

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error in get_public_vehicle_details: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def get_vehicle_availability(self, db: Session, vehicle_id, from_date, to_date):
        """
        🌐 Календарь доступности техники на основе Rental.

        Возвращает список дат с флагом `available` и `rental_id` (если занята).
        """
        from datetime import date as DateType

        from app.services.marketplace_service import marketplace_service

        try:
            vehicle = marketplace_service.get_vehicle_details(db, vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=404, detail="Vehicle not found or not published"
                )

            # Парсим даты
            from_dt = DateType.fromisoformat(from_date) if from_date else None
            to_dt = DateType.fromisoformat(to_date) if to_date else None

            calendar = marketplace_service.get_availability_calendar(
                db, vehicle_id, from_dt, to_dt
            )

            return VehicleAvailabilityResponse(
                vehicle_id=vehicle.id,
                vehicle_name=vehicle.name,
                from_date=calendar[0]["date"] if calendar else "",
                to_date=calendar[-1]["date"] if calendar else "",
                calendar=calendar,
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error in get_vehicle_availability: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def create_request_from_listing(
        self, db: Session, vehicle_id, data, company_id: int | None = None
    ):
        """
        🌐 Создание заявки из публичной витрины (без регистрации).

        Отправляет уведомление собственнику техники.

        **Примечание:** В production здесь должна быть проверка reCAPTCHA
        или регистрация через телефон/email для защиты от спама.
        """
        from datetime import datetime as dt

        from app.services.marketplace_service import marketplace_service

        try:
            # 1. Проверяем технику
            vehicle = marketplace_service.get_vehicle_details(db, vehicle_id)
            if not vehicle:
                raise HTTPException(
                    status_code=404, detail="Vehicle not found or not published"
                )

            # 2. Парсим даты
            try:
                planned_start = dt.fromisoformat(data.planned_start)
                planned_end = dt.fromisoformat(data.planned_end)
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid datetime format: {e}"
                )

            if planned_start >= planned_end:
                raise HTTPException(
                    status_code=400,
                    detail="planned_end must be after planned_start",
                )

            # 3. Создаём или находим Contractor (клиента) по контактным данным
            # Ищем существующего клиента по email или телефону в этой компании
            from sqlalchemy import or_

            existing_client = None
            if data.contact_email:
                existing_client = (
                    db.query(Contractor)
                    .filter(
                        Contractor.company_id == vehicle.company_id,
                        Contractor.type == "client",
                        or_(
                            Contractor.email == data.contact_email,
                            Contractor.contact_email == data.contact_email,
                        ),
                    )
                    .first()
                )
            if not existing_client and data.contact_phone:
                existing_client = (
                    db.query(Contractor)
                    .filter(
                        Contractor.company_id == vehicle.company_id,
                        Contractor.type == "client",
                        Contractor.contact_phone == data.contact_phone,
                    )
                    .first()
                )

            if existing_client:
                client_contractor = existing_client
            else:
                client_contractor = Contractor(
                    name=data.contact_name,
                    type="client",
                    contact_phone=data.contact_phone,
                    contact_email=data.contact_email,
                    email=data.contact_email,
                    company_id=vehicle.company_id,
                    is_public_lead=True,
                )
                db.add(client_contractor)
                db.flush()

            # 4. Создаём заявку
            request = marketplace_service.create_request_from_listing(
                db=db,
                vehicle_id=vehicle_id,
                client_contractor_id=client_contractor.id,
                company_id=vehicle.company_id or 1,
                work_type=data.work_type,
                planned_start=planned_start,
                planned_end=planned_end,
                comment=data.comment,
            )

            return PublicRequestResponse(
                request_id=request.id,
                vehicle_id=vehicle_id,
                vehicle_name=vehicle.name,
                status=(
                    request.status.value
                    if hasattr(request.status, "value")
                    else str(request.status)
                ),
                planned_start=planned_start.isoformat(),
                planned_end=planned_end.isoformat(),
                message=(
                    f"✅ Заявка #{request.id} создана. "
                    f"Собственник техники '{vehicle.name}' получит уведомление."
                ),
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error in create_request_from_listing: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def get_public_company_rating(self, db: Session, company_id: int | None = None):
        """🌐 Рейтинг компании (средний балл и количество отзывов)."""
        try:
            company = db.get(Company, company_id)
            if not company or not company.is_active:
                raise HTTPException(status_code=404, detail="Company not found")

            from sqlalchemy import func

            result = (
                db.query(
                    func.coalesce(func.avg(Review.rating), 0).label("avg_rating"),
                    func.count(Review.id).label("total"),
                )
                .filter(
                    Review.reviewed_company_id == company_id,
                    Review.status == "approved",
                )
                .one()
            )

            return {
                "average_rating": (
                    round(float(result.avg_rating), 2) if result.total > 0 else None
                ),
                "total_reviews": int(result.total or 0),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error in get_public_company_rating: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def get_public_company_reviews(
        self, db: Session, limit, company_id: int | None = None
    ):
        """🌐 Отзывы о компании."""
        try:
            company = db.get(Company, company_id)
            if not company or not company.is_active:
                raise HTTPException(status_code=404, detail="Company not found")

            reviews = (
                db.query(Review)
                .join(Contractor, Review.reviewer_contractor_id == Contractor.id)
                .filter(
                    Review.reviewed_company_id == company_id,
                    Review.status == "approved",
                )
                .order_by(Review.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": r.id,
                    "rating": r.rating,
                    "comment": r.comment,
                    "reviewer_contractor_name": (
                        r.reviewer.name if r.reviewer else "Anonymous"
                    ),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reviews
            ]

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error in get_public_company_reviews: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def list_public_categories(self, db: Session, company_id: int | None = None):
        """🌐 Публичный список категорий техники."""
        try:
            stmt = select(Category).order_by(Category.level, Category.name)
            categories = db.scalars(stmt).all()

            result = []
            for c in categories:
                vehicles_count = (
                    db.query(Vehicle).filter(Vehicle.category_id == c.id).count()
                )
                result.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "code": c.code,
                        "level": c.level,
                        "parent_id": c.parent_id,
                        "is_active": c.is_active,
                        "company_id": c.company_id,
                        "vehicles_count": vehicles_count,
                        "created_at": (
                            c.created_at.isoformat() if c.created_at else None
                        ),
                    }
                )
            return result

        except Exception as e:
            logger.exception("❌ Error in list_public_categories: %s", e)
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    def list_marketplace_requests(
        self, db: Session, company_id: int, category_id, cross_category, limit, offset
    ):
        """
        🌐 Публичный список заявок в маркетплейсе.

        Возвращает только опубликованные заявки из маркетплейса с условиями оплаты.
        Исполнители видят: требования, срок оплаты, режим (заказчик/диспетчер).
        """
        stmt = (
            select(DispatchRequest)
            .where(DispatchRequest.source_channel == "marketplace")
            .where(DispatchRequest.is_published == True)
            .where(DispatchRequest.status.in_(["new", "processing"]))
        )

        if category_id:
            stmt = stmt.where(DispatchRequest.vehicle_category_id == category_id)

        # Исключаем заявки собственной компании (если авторизован)
        if company_id:
            stmt = stmt.where(DispatchRequest.company_id != company_id)

        # Региональная фильтрация: владелец техники видит только заявки своего региона
        vehicle_regions = []
        if company_id:
            from app.models.catalog import Vehicle

            vehicle_regions = (
                db.execute(
                    select(Vehicle.region)
                    .where(
                        Vehicle.company_id == company_id,
                        Vehicle.region.isnot(None),
                    )
                    .distinct()
                )
                .scalars()
                .all()
            )

            if vehicle_regions:
                stmt = stmt.where(DispatchRequest.region.in_(vehicle_regions))

        # Count total for pagination
        count_stmt = (
            select(func.count())
            .select_from(DispatchRequest)
            .where(
                DispatchRequest.source_channel == "marketplace",
                DispatchRequest.is_published == True,
                DispatchRequest.status.in_(["new", "processing"]),
            )
        )
        if category_id:
            count_stmt = count_stmt.where(
                DispatchRequest.vehicle_category_id == category_id
            )
        if company_id:
            count_stmt = count_stmt.where(DispatchRequest.company_id != company_id)
        if company_id and vehicle_regions:
            count_stmt = count_stmt.where(DispatchRequest.region.in_(vehicle_regions))
        total = db.execute(count_stmt).scalar() or 0

        stmt = (
            stmt.order_by(DispatchRequest.created_at.desc()).offset(offset).limit(limit)
        )
        requests_list = db.scalars(stmt).all()

        result = []
        for req in requests_list:
            cat_name = None
            if req.vehicle_category_id:
                cat = db.get(Category, req.vehicle_category_id)
                cat_name = cat.name if cat else None

            payment_days = getattr(req, "payment_terms_days", 7) or 7
            is_extended = payment_days > 7

            result.append(
                {
                    "id": req.id,
                    "vehicle_category_id": req.vehicle_category_id,
                    "vehicle_category_name": cat_name,
                    "work_type": req.work_type,
                    "object_address": req.object_address,
                    "planned_start": (
                        req.planned_start.isoformat() if req.planned_start else None
                    ),
                    "planned_end": (
                        req.planned_end.isoformat() if req.planned_end else None
                    ),
                    "shift_duration_hours": (
                        float(req.shift_duration_hours)
                        if req.shift_duration_hours
                        else None
                    ),
                    "client_rate": float(req.client_rate) if req.client_rate else None,
                    "rate_type": req.rate_type,
                    "marketplace_mode": getattr(req, "marketplace_mode", "client"),
                    "is_surplus": "[Surplus]" in (getattr(req, "comment", "") or ""),
                    "payment_terms_days": payment_days,
                    "is_extended_payment": is_extended,
                    "requirements": getattr(req, "requirements", None),
                    "priority": req.priority,
                    "created_at": (
                        req.created_at.isoformat() if req.created_at else None
                    ),
                }
            )

        return {
            "items": result,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def respond_to_marketplace_request(
        self, db: Session, company_id: int, request_id, vehicle_id, current_user=None
    ):
        """
        🌐 Откликнуться на заявку маркетплейса.

        Исполнитель указывает свою технику для выполнения заказа.
        Владелец заявки получает уведомление об отклике.
        """

        from app.services.notification_service import create_notification

        # Проверяем заявку
        request = db.get(DispatchRequest, request_id)
        if not request or request.source_channel != "marketplace":
            raise HTTPException(status_code=404, detail="Marketplace request not found")

        if request.status not in ("new", "processing"):
            raise HTTPException(
                status_code=409, detail=f"Request is {request.status} — cannot respond"
            )

        # Нельзя откликнуться на свою заявку
        if request.company_id == company_id:
            raise HTTPException(
                status_code=403, detail="Cannot respond to your own request"
            )

        # Проверяем технику
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle or vehicle.company_id != company_id:
            raise HTTPException(
                status_code=404,
                detail="Vehicle not found or does not belong to your company",
            )

        if vehicle.status in ("maintenance", "repair", "decommissioned"):
            raise HTTPException(
                status_code=409, detail=f"Vehicle '{vehicle.name}' is not available"
            )

        # Проверяем согласие на комиссию
        if not getattr(vehicle, "marketplace_commission_agreed", False):
            raise HTTPException(
                status_code=403,
                detail=f"Vehicle '{vehicle.name}' requires marketplace commission agreement",
            )

        # Создаём отклик (RequestAssignment со статусом pending)
        existing = db.execute(
            select(RequestAssignment).where(
                RequestAssignment.request_id == request_id,
                RequestAssignment.vehicle_id == vehicle_id,
            )
        ).scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=409, detail="Already responded with this vehicle"
            )

        from datetime import datetime as dt

        assignment = RequestAssignment(
            request_id=request_id,
            vehicle_id=vehicle_id,
            operator_id=getattr(current_user, "id", None),
            planned_start=(
                request.planned_start
                if hasattr(request, "planned_start") and request.planned_start
                else dt.now(UTC)
            ),
            planned_end=(
                request.planned_end
                if hasattr(request, "planned_end") and request.planned_end
                else dt.now(UTC)
            ),
            status="pending_approval",
        )
        db.add(assignment)
        db.flush()

        # Логируем
        db.add(
            RequestStatusLog(
                request_id=request_id,
                from_status=request.status,
                to_status="has_responses",
                changed_by_user_id=current_user.id,
                comment=f"Отклик от {current_user.full_name or current_user.email} ({vehicle.name})",
            )
        )

        db.commit()

        # Уведомляем владельца заявки (in-app + WebSocket)
        try:
            mp_mode = getattr(request, "marketplace_mode", "client")
            mode_label = (
                "📋 Диспетчер" if mp_mode == "owner_dispatcher" else "🏪 Заказчик"
            )
            payment_days = getattr(request, "payment_terms_days", 7) or 7

            await create_notification(
                db=db,
                user_id=request.created_by,
                title="🔔 Новый отклик на заявку",
                body=(
                    f"{mode_label} | Техника «{vehicle.name}» откликнулась на вашу заявку.\n"
                    f"Адрес: {request.object_address}\n"
                    f"Оплата: {payment_days} дн."
                ),
                channel="in_app",
            )

            # WebSocket real-time notification
            from app.services.websocket_manager import manager

            await manager.send_to_user(
                request.created_by,
                {
                    "type": "marketplace_response",
                    "request_id": request_id,
                    "vehicle_name": vehicle.name,
                    "company_name": (
                        current_user.company.name
                        if hasattr(current_user, "company") and current_user.company
                        else ""
                    ),
                    "mode": mp_mode,
                },
            )
        except Exception:
            pass  # Не блокируем если уведомление не отправилось

        return {
            "id": assignment.id,
            "request_id": request_id,
            "vehicle_id": vehicle_id,
            "vehicle_name": vehicle.name,
            "status": "pending_approval",
            "message": "Отклик успешно отправлен! Владелец заявки уведомлён.",
        }

    def marketplace_payouts_report(self, db: Session, date_from, date_to):
        """Экспорт отчёта по выплатам маркетплейса в Excel."""
        import io
        from datetime import date, datetime

        from fastapi.responses import StreamingResponse

        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl not installed")

        # Get payouts related to marketplace requests

        stmt = (
            select(Payout)
            .join(DispatchRequest, Payout.request_id == DispatchRequest.id)
            .where(DispatchRequest.source_channel == "marketplace")
        )

        if date_from:
            stmt = stmt.where(Payout.payout_date >= date.fromisoformat(date_from))
        if date_to:
            stmt = stmt.where(Payout.payout_date <= date.fromisoformat(date_to))

        stmt = stmt.order_by(Payout.payout_date.desc())
        payouts = db.scalars(stmt).all()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Выплаты маркетплейса"

        header_fill = PatternFill(
            start_color="2F5496", end_color="2F5496", fill_type="solid"
        )
        header_font = Font(color="FFFFFF", bold=True, size=11)

        headers = [
            "ID",
            "Период",
            "Заявка",
            "Техника",
            "Исполнитель",
            "Сумма",
            "Комиссия (10%)",
            "К выплате",
            "Статус",
            "Дата",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        total_amount = 0
        total_commission = 0
        total_net = 0

        for row_idx, p in enumerate(payouts, 2):
            request = db.get(DispatchRequest, p.request_id) if p.request_id else None
            vehicle = db.get(Vehicle, p.vehicle_id) if p.vehicle_id else None

            amount = float(p.gross_amount) if p.gross_amount else 0
            commission = float(p.platform_commission) if p.platform_commission else 0
            net = float(p.net_amount) if p.net_amount else 0
            total_amount += amount
            total_commission += commission
            total_net += net

            period = p.payout_date.strftime("%d.%m.%Y") if p.payout_date else ""

            ws.cell(row=row_idx, column=1, value=p.id)
            ws.cell(row=row_idx, column=2, value=period)
            ws.cell(row=row_idx, column=3, value=f"#{request.id}" if request else "")
            ws.cell(row=row_idx, column=4, value=vehicle.name if vehicle else "")
            ws.cell(row=row_idx, column=5, value=getattr(p, "owner_name", "") or "")
            ws.cell(row=row_idx, column=6, value=amount)
            ws.cell(row=row_idx, column=7, value=commission)
            ws.cell(row=row_idx, column=8, value=net)
            ws.cell(
                row=row_idx, column=9, value=p.status if hasattr(p, "status") else ""
            )
            ws.cell(
                row=row_idx,
                column=10,
                value=(
                    p.created_at.strftime("%d.%m.%Y")
                    if hasattr(p, "created_at") and p.created_at
                    else ""
                ),
            )

            ws.cell(row=row_idx, column=6).number_format = "#,##0.00 ₽"
            ws.cell(row=row_idx, column=7).number_format = "#,##0.00 ₽"
            ws.cell(row=row_idx, column=8).number_format = "#,##0.00 ₽"

        # Totals row
        total_row = len(payouts) + 2
        ws.cell(row=total_row, column=5, value="ИТОГО").font = Font(bold=True)
        ws.cell(row=total_row, column=6, value=total_amount).font = Font(bold=True)
        ws.cell(row=total_row, column=6).number_format = "#,##0.00 ₽"
        ws.cell(row=total_row, column=7, value=total_commission).font = Font(bold=True)
        ws.cell(row=total_row, column=7).number_format = "#,##0.00 ₽"
        ws.cell(row=total_row, column=8, value=total_net).font = Font(bold=True)
        ws.cell(row=total_row, column=8).number_format = "#,##0.00 ₽"

        for col_cells in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(
                max_len + 4, 35
            )

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = (
            f"marketplace_payouts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def marketplace_stats(self, db: Session):
        """Статистика маркетплейса для дашборда."""
        from sqlalchemy import func

        total_requests = (
            db.execute(
                select(func.count())
                .select_from(DispatchRequest)
                .where(DispatchRequest.source_channel == "marketplace")
            ).scalar()
            or 0
        )

        active_requests = (
            db.execute(
                select(func.count())
                .select_from(DispatchRequest)
                .where(
                    DispatchRequest.source_channel == "marketplace",
                    DispatchRequest.status.in_(["new", "processing", "has_responses"]),
                )
            ).scalar()
            or 0
        )

        assigned_requests = (
            db.execute(
                select(func.count())
                .select_from(DispatchRequest)
                .where(
                    DispatchRequest.source_channel == "marketplace",
                    DispatchRequest.status == "assigned",
                )
            ).scalar()
            or 0
        )

        # По режимам
        client_count = (
            db.execute(
                select(func.count())
                .select_from(DispatchRequest)
                .where(
                    DispatchRequest.source_channel == "marketplace",
                    DispatchRequest.marketplace_mode == "client",
                )
            ).scalar()
            or 0
        )

        dispatcher_count = (
            db.execute(
                select(func.count())
                .select_from(DispatchRequest)
                .where(
                    DispatchRequest.source_channel == "marketplace",
                    DispatchRequest.marketplace_mode == "owner_dispatcher",
                )
            ).scalar()
            or 0
        )

        # Средний срок оплаты
        avg_payment = db.execute(
            select(func.avg(DispatchRequest.payment_terms_days)).where(
                DispatchRequest.source_channel == "marketplace",
                DispatchRequest.payment_terms_days.isnot(None),
            )
        ).scalar()

        # Отклики

        total_responses = (
            db.execute(select(func.count()).select_from(RequestAssignment)).scalar()
            or 0
        )

        pending_responses = (
            db.execute(
                select(func.count())
                .select_from(RequestAssignment)
                .where(RequestAssignment.status == "pending_approval")
            ).scalar()
            or 0
        )

        return {
            "total_requests": total_requests,
            "active_requests": active_requests,
            "assigned_requests": assigned_requests,
            "client_requests": client_count,
            "dispatcher_requests": dispatcher_count,
            "avg_payment_days": round(float(avg_payment), 1) if avg_payment else 7.0,
            "total_responses": total_responses,
            "pending_responses": pending_responses,
        }

    def export_marketplace_requests(self, db: Session, category_id):
        """Экспорт заявок маркетплейса в Excel."""
        import io
        from datetime import datetime

        from fastapi.responses import StreamingResponse

        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl not installed")

        stmt = (
            select(DispatchRequest)
            .where(DispatchRequest.source_channel == "marketplace")
            .where(DispatchRequest.is_published == True)
            .order_by(DispatchRequest.created_at.desc())
        )
        if category_id:
            stmt = stmt.where(DispatchRequest.vehicle_category_id == category_id)

        requests_list = db.scalars(stmt).all()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Заявки маркетплейса"

        # Header style
        header_fill = PatternFill(
            start_color="4472C4", end_color="4472C4", fill_type="solid"
        )
        header_font = Font(color="FFFFFF", bold=True, size=11)

        headers = [
            "ID",
            "Категория",
            "Тип работы",
            "Адрес",
            "Период",
            "Ставка",
            "Режим",
            "Оплата (дн.)",
            "Приоритет",
            "Статус",
            "Дата создания",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # Data rows
        for row_idx, req in enumerate(requests_list, 2):
            cat_name = ""
            if req.vehicle_category_id:
                cat = db.get(Category, req.vehicle_category_id)
                cat_name = cat.name if cat else str(req.vehicle_category_id)

            period = ""
            if req.planned_start and req.planned_end:
                period = f"{req.planned_start.strftime('%d.%m.%Y')} — {req.planned_end.strftime('%d.%m.%Y')}"

            rate = (
                f"{float(req.client_rate)} ₽/{('час' if req.rate_type == 'hourly' else 'смена')}"
                if req.client_rate
                else ""
            )
            mode = (
                "🏪 Заказчик"
                if getattr(req, "marketplace_mode", "client") == "client"
                else "📋 Диспетчер"
            )
            payment_days = getattr(req, "payment_terms_days", 7) or 7

            ws.cell(row=row_idx, column=1, value=req.id)
            ws.cell(row=row_idx, column=2, value=cat_name)
            ws.cell(row=row_idx, column=3, value=req.work_type or "")
            ws.cell(row=row_idx, column=4, value=req.object_address or "")
            ws.cell(row=row_idx, column=5, value=period)
            ws.cell(row=row_idx, column=6, value=rate)
            ws.cell(row=row_idx, column=7, value=mode)
            ws.cell(row=row_idx, column=8, value=payment_days)
            ws.cell(row=row_idx, column=9, value=req.priority or "normal")
            ws.cell(row=row_idx, column=10, value=req.status or "")
            ws.cell(
                row=row_idx,
                column=11,
                value=(
                    req.created_at.strftime("%d.%m.%Y %H:%M") if req.created_at else ""
                ),
            )

            # Highlight extended payment
            if payment_days > 7:
                ws.cell(row=row_idx, column=8).fill = PatternFill(
                    start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"
                )

        # Auto-width columns
        for col_cells in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(
                max_len + 4, 40
            )

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = (
            f"marketplace_requests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def list_my_responses(self, db: Session, company_id: int):
        """Список откликов текущей компании на заявки маркетплейса."""

        assignments = (
            db.execute(
                select(RequestAssignment)
                .join(
                    DispatchRequest, RequestAssignment.request_id == DispatchRequest.id
                )
                .join(Vehicle, RequestAssignment.vehicle_id == Vehicle.id)
                .where(Vehicle.company_id == company_id)
                .order_by(RequestAssignment.created_at.desc())
            )
            .scalars()
            .all()
        )

        result = []
        for a in assignments:
            req = db.get(DispatchRequest, a.request_id)
            vehicle = db.get(Vehicle, a.vehicle_id)
            result.append(
                {
                    "id": a.id,
                    "request_id": a.request_id,
                    "vehicle_id": a.vehicle_id,
                    "vehicle_name": vehicle.name if vehicle else "N/A",
                    "status": a.status,
                    "request_address": req.object_address if req else None,
                    "request_work_type": req.work_type if req else None,
                    "request_category": req.vehicle_category_id if req else None,
                    "created_at": (
                        a.created_at.isoformat()
                        if hasattr(a, "created_at") and a.created_at
                        else None
                    ),
                }
            )

        return result

    def create_company_review(
        self, db: Session, payload, company_id: int | None = None
    ):
        """🌐 Создать отзыв о компании на маркетплейсе."""
        from sqlalchemy import text

        company = db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Компания не найдена")

        # Проверяем дубликат по reviewer_name + company_id
        existing = db.execute(
            text(
                """
                SELECT id FROM company_reviews
                WHERE company_id = :cid
                  AND reviewer_name = :rname
                  AND is_published = true
            """
            ),
            {
                "cid": company_id,
                "rname": payload.reviewer_name or "Анонимный пользователь",
            },
        ).first()
        if existing:
            raise HTTPException(
                status_code=400, detail="Вы уже оставляли отзыв об этой компании"
            )

        # Создаём отзыв (используем reviewer_user_id = NULL для анонимных)
        result = db.execute(
            text(
                """
                INSERT INTO company_reviews
                    (company_id, reviewer_user_id, reviewer_name, reviewer_email,
                     rating, comment, is_verified, is_published, moderation_status,
                     created_at, updated_at)
                VALUES
                    (:cid, NULL, :rname, :remail,
                     :rating, :comment, false, true, 'approved',
                     NOW(), NOW())
                RETURNING id, rating, comment, created_at
            """
            ),
            {
                "cid": company_id,
                "rname": payload.reviewer_name or "Анонимный пользователь",
                "remail": None,
                "rating": payload.rating,
                "comment": payload.comment,
            },
        ).one()
        db.commit()

        return {
            "id": result.id,
            "rating": result.rating,
            "comment": result.comment,
            "created_at": result.created_at.isoformat() if result.created_at else None,
            "message": "Отзыв успешно опубликован",
        }

    def get_company_reviews_public(
        self, db: Session, limit, offset, company_id: int | None = None
    ):
        """🌐 Получить отзывы о компании."""
        from sqlalchemy import text

        company = db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Компания не найдена")

        avg_result = db.execute(
            text(
                "SELECT COALESCE(AVG(rating), 0) as avg_rating, COUNT(*) as total FROM company_reviews WHERE company_id = :cid AND is_published = true"
            ),
            {"cid": company_id},
        ).one()

        dist_result = db.execute(
            text(
                "SELECT rating, COUNT(*) as cnt FROM company_reviews WHERE company_id = :cid AND is_published = true GROUP BY rating"
            ),
            {"cid": company_id},
        ).all()
        distribution = {str(i): 0 for i in range(1, 6)}
        for row in dist_result:
            distribution[str(row.rating)] = row.cnt

        reviews_result = db.execute(
            text(
                """
                SELECT id, rating, comment, reviewer_name, is_verified, created_at
                FROM company_reviews
                WHERE company_id = :cid AND is_published = true
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """
            ),
            {"cid": company_id, "limit": limit, "offset": offset},
        ).all()

        items = [
            {
                "id": r.id,
                "rating": r.rating,
                "comment": r.comment,
                "reviewer_name": r.reviewer_name or "Аноним",
                "reviewer_contractor_name": r.reviewer_name or "Аноним",
                "is_verified": r.is_verified,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews_result
        ]

        return {
            "items": items,
            "total": int(avg_result.total or 0),
            "average_rating": float(avg_result.avg_rating or 0),
            "rating_distribution": distribution,
        }


# Singleton
public_service = PublicService()
