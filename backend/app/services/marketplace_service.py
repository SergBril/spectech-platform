"""Сервис маркетплейса: витрина техники, заявки, доступность."""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.dispatch import Request, RequestStatus
from app.models.rental import Rental, RentalStatus

logger = logging.getLogger("spectech.marketplace_service")


class MarketplaceService:
    """Сервис публичной витрины техники."""

    # === ПУБЛИКАЦИЯ / СНЯТИЕ ===

    @staticmethod
    def publish_vehicle(
        db: Session,
        vehicle_id: int,
        company_id: int,
        hourly_rate: Decimal | None = None,
        shift_rate: Decimal | None = None,
        downtime_hourly_rate: Decimal | None = None,
        description: str | None = None,
        photos: list[str] | None = None,
        base_location_lat: float | None = None,
        base_location_lon: float | None = None,
    ) -> Vehicle:
        """
        Публикует технику на маркетплейсе.

        Требования:
        - Техника принадлежит текущей компании
        - Указана хотя бы одна ставка (hourly или shift)
        - Техника не удалена
        """
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        if vehicle.company_id != company_id:
            raise ValueError("Cannot publish vehicle from another company")

        if vehicle.is_deleted:
            raise ValueError("Cannot publish deleted vehicle")

        # Хотя бы одна ставка должна быть указана
        effective_hourly = (
            hourly_rate if hourly_rate is not None else vehicle.hourly_rate
        )
        effective_shift = shift_rate if shift_rate is not None else vehicle.shift_rate

        if not effective_hourly and not effective_shift:
            raise ValueError(
                "At least one rate must be specified (hourly_rate or shift_rate)"
            )

        # Применяем обновления
        if hourly_rate is not None:
            vehicle.hourly_rate = hourly_rate
        if shift_rate is not None:
            vehicle.shift_rate = shift_rate
        if downtime_hourly_rate is not None:
            vehicle.downtime_hourly_rate = downtime_hourly_rate
        if description is not None:
            vehicle.marketplace_description = description
        if photos is not None:
            vehicle.photos = photos
        if base_location_lat is not None:
            vehicle.base_location_lat = base_location_lat
        if base_location_lon is not None:
            vehicle.base_location_lon = base_location_lon

        # Публикуем: устанавливаем оба флага для публичного каталога
        vehicle.is_available_for_rent = True
        vehicle.marketplace_commission_agreed = True

        db.commit()
        db.refresh(vehicle)

        logger.info(
            "Vehicle #%s (%s) published on marketplace by company #%s",
            vehicle.id,
            vehicle.name,
            company_id,
        )
        return vehicle

    @staticmethod
    def unpublish_vehicle(db: Session, vehicle_id: int, company_id: int) -> Vehicle:
        """Снимает технику с публикации."""
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        if vehicle.company_id != company_id:
            raise ValueError("Cannot unpublish vehicle from another company")

        vehicle.is_available_for_rent = False
        vehicle.marketplace_commission_agreed = False
        db.commit()
        db.refresh(vehicle)

        logger.info("Vehicle #%s unpublished from marketplace", vehicle.id)
        return vehicle

    @staticmethod
    def update_listing(
        db: Session, vehicle_id: int, company_id: int, **updates
    ) -> Vehicle:
        """Обновляет параметры публикации."""
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        if vehicle.company_id != company_id:
            raise ValueError("Cannot update vehicle from another company")

        allowed_fields = {
            "hourly_rate",
            "shift_rate",
            "downtime_hourly_rate",
            "marketplace_description",
            "photos",
            "base_location_lat",
            "base_location_lon",
            "is_available_for_rent",
            "marketplace_commission_agreed",
        }

        for key, value in updates.items():
            if key in allowed_fields:
                setattr(vehicle, key, value)

        db.commit()
        db.refresh(vehicle)
        return vehicle

    # === ПОИСК / ВИТРИНА ===

    @staticmethod
    def search_vehicles(
        db: Session,
        category_id: int | None = None,
        search: str | None = None,
        min_hourly_rate: float | None = None,
        max_hourly_rate: float | None = None,
        lat: float | None = None,
        lon: float | None = None,
        radius_km: float | None = None,
        available_from: date | None = None,
        available_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Vehicle]:
        """
        Поиск доступной техники с фильтрами.

        Поддерживает:
        - Категорию
        - Текстовый поиск (название, марка, модель)
        - Диапазон цены
        - Геолокацию (поиск в радиусе)
        - Даты доступности (пересечение с Rental)
        """
        stmt = (
            select(Vehicle)
            .join(Company, Vehicle.company_id == Company.id)
            .where(
                Vehicle.is_available_for_rent == True,
                Vehicle.marketplace_commission_agreed == True,
                Vehicle.is_deleted == False,
                Company.is_active == True,
            )
        )

        # Категория
        if category_id:
            stmt = stmt.where(Vehicle.category_id == category_id)

        # Текстовый поиск
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Vehicle.name.ilike(pattern),
                    Vehicle.make.ilike(pattern),
                    Vehicle.model_name.ilike(pattern),
                    Vehicle.marketplace_description.ilike(pattern),
                )
            )

        # Цена
        if min_hourly_rate is not None:
            stmt = stmt.where(Vehicle.hourly_rate >= min_hourly_rate)
        if max_hourly_rate is not None:
            stmt = stmt.where(Vehicle.hourly_rate <= max_hourly_rate)

        # Геолокация (грубый фильтр по bounding box + точный расчёт)
        if lat is not None and lon is not None and radius_km:
            # 1 градус ≈ 111 км
            delta = radius_km / 111.0
            stmt = stmt.where(
                and_(
                    Vehicle.base_location_lat.between(lat - delta, lat + delta),
                    Vehicle.base_location_lon.between(lon - delta, lon + delta),
                )
            )

        vehicles = list(db.scalars(stmt.offset(offset).limit(limit * 2)).all())

        # Точный расчёт расстояния (Haversine) — Python-side
        if lat is not None and lon is not None and radius_km:
            vehicles = [
                v
                for v in vehicles
                if v.base_location_lat
                and v.base_location_lon
                and MarketplaceService._haversine(
                    lat, lon, v.base_location_lat, v.base_location_lon
                )
                <= radius_km
            ]

        # Фильтр по доступности (пересечение с Rental)
        if available_from and available_to:
            available_ids = MarketplaceService._filter_available(
                db, [v.id for v in vehicles], available_from, available_to
            )
            vehicles = [v for v in vehicles if v.id in available_ids]

        return vehicles[:limit]

    @staticmethod
    def get_vehicle_details(db: Session, vehicle_id: int) -> Vehicle | None:
        """Детальная страница техники (только опубликованная)."""
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle:
            return None
        if not vehicle.is_available_for_rent or vehicle.is_deleted:
            return None
        return vehicle

    @staticmethod
    def get_availability_calendar(
        db: Session,
        vehicle_id: int,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """
        Календарь занятости техники на основе Rental.

        Возвращает список периодов:
        [{"date": "2026-10-10", "available": True, "rental_id": None}, ...]
        """
        if not from_date:
            from_date = date.today()
        if not to_date:
            to_date = from_date + timedelta(days=30)

        # Активные и будущие аренды
        stmt = select(Rental).where(
            (
                Rental.vehicle_id == vehicle_id
                if hasattr(Rental, "vehicle_id")
                else Rental.id > 0
            ),
            Rental.status.in_(
                [
                    RentalStatus.DRAFT,
                    RentalStatus.ACTIVE,
                    RentalStatus.OVERDUE,
                ]
            ),
        )
        rentals = list(db.scalars(stmt).all())

        # Собираем занятые даты
        busy_dates = set()
        rental_map = {}
        for rental in rentals:
            if hasattr(rental, "items"):
                for item in rental.items:
                    if item.vehicle_id != vehicle_id:
                        continue
                    start = rental.start_date.date() if rental.start_date else None
                    end = rental.end_date.date() if rental.end_date else None
                    if start and end:
                        current = start
                        while current <= end:
                            busy_dates.add(current)
                            rental_map[current] = rental.id
                            current += timedelta(days=1)

        # Строим календарь
        calendar = []
        current = from_date
        while current <= to_date:
            calendar.append(
                {
                    "date": current.isoformat(),
                    "available": current not in busy_dates,
                    "rental_id": rental_map.get(current),
                    "is_past": current < date.today(),
                }
            )
            current += timedelta(days=1)

        return calendar

    # === ЗАЯВКА ИЗ ВИТРИНЫ ===

    @staticmethod
    def create_request_from_listing(
        db: Session,
        vehicle_id: int,
        client_contractor_id: int,
        company_id: int,
        work_type: str,
        planned_start: datetime,
        planned_end: datetime,
        comment: str | None = None,
        created_by: int | None = None,
    ) -> Request:
        """
        Создаёт заявку (Request) из публичной витрины.

        Отправляет уведомление собственнику техники.
        """
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle:
            raise ValueError(f"Vehicle {vehicle_id} not found")

        if not vehicle.is_available_for_rent:
            raise ValueError("Vehicle is not available for rent")

        # Проверяем доступность в выбранные даты
        available_ids = MarketplaceService._filter_available(
            db,
            [vehicle_id],
            planned_start.date(),
            planned_end.date(),
        )
        if vehicle_id not in available_ids:
            raise ValueError(
                f"Vehicle is not available for the selected period "
                f"({planned_start.date()} - {planned_end.date()})"
            )

        # Создаём заявку
        request = Request(
            client_id=client_contractor_id,
            status=RequestStatus.new,
            request_type="one_time",
            work_type=work_type,
            planned_start=planned_start,
            planned_end=planned_end,
            company_id=company_id,
            created_by=created_by,
            comment=comment
            or f"Заявка из маркетплейса на технику #{vehicle_id} ({vehicle.name})",
        )
        db.add(request)
        db.commit()
        db.refresh(request)

        logger.info(
            "Request #%s created from marketplace for vehicle #%s by client #%s",
            request.id,
            vehicle_id,
            client_contractor_id,
        )

        # Уведомление собственнику (асинхронно, через notification_dispatcher)
        try:
            import asyncio

            from app.models.contractor import Contractor

            owner = db.get(Contractor, vehicle.owner_id) if vehicle.owner_id else None
            if owner:
                owner_email = owner.email or f"owner_{owner.id}@spectech.dev"
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        MarketplaceService._notify_owner_new_request(
                            owner_email=owner_email,
                            owner_name=owner.name,
                            vehicle=vehicle,
                            request=request,
                        )
                    )
                except RuntimeError:
                    logger.info("No event loop, skipping owner notification")
        except Exception as e:
            logger.error(f"Failed to notify owner: {e}")

        return request

    # === ВНУТРЕННИЕ МЕТОДЫ ===

    @staticmethod
    async def _notify_owner_new_request(
        owner_email: str, owner_name: str, vehicle: Vehicle, request: Request
    ) -> None:
        """Отправляет email собственнику о новой заявке."""
        from app.services.email_service import email_service

        subject = f"🚜 Новая заявка на вашу технику {vehicle.name}"
        body = f"""
        <h2>Здравствуйте, {owner_name}!</h2>
        <p>На вашу технику <b>{vehicle.name}</b> поступила новая заявка из маркетплейса.</p>
        <h3>Детали заявки #{request.id}:</h3>
        <ul>
            <li><b>Тип работ:</b> {request.work_type}</li>
            <li><b>Начало:</b> {request.planned_start.strftime('%d.%m.%Y %H:%M')}</li>
            <li><b>Окончание:</b> {request.planned_end.strftime('%d.%m.%Y %H:%M')}</li>
        </ul>
        <p>Зайдите в личный кабинет, чтобы принять или отклонить заявку.</p>
        """

        try:
            email_service.send_email(
                to_email=owner_email,
                subject=subject,
                html_body=body,
            )
            logger.info(f"Owner notification sent to {owner_email}")
        except Exception as e:
            logger.error(f"Failed to send owner email: {e}")

    @staticmethod
    def _filter_available(
        db: Session,
        vehicle_ids: list[int],
        from_date: date,
        to_date: date,
    ) -> set[int]:
        """Возвращает ID машин, доступных в указанный период."""
        if not vehicle_ids:
            return set()

        # Ищем все Rentals с пересечением дат
        stmt = select(Rental).where(
            Rental.status.in_(
                [
                    RentalStatus.DRAFT,
                    RentalStatus.ACTIVE,
                    RentalStatus.OVERDUE,
                ]
            ),
            Rental.start_date <= datetime.combine(to_date, datetime.max.time()),
            Rental.end_date >= datetime.combine(from_date, datetime.min.time()),
        )
        rentals = list(db.scalars(stmt).all())

        # Собираем занятые vehicle_id
        busy_vehicle_ids = set()
        for rental in rentals:
            if hasattr(rental, "items"):
                for item in rental.items:
                    if item.vehicle_id in vehicle_ids:
                        busy_vehicle_ids.add(item.vehicle_id)

        return set(vehicle_ids) - busy_vehicle_ids

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Расстояние между двумя точками в км (Haversine)."""
        import math

        R = 6371.0  # Радиус Земли в км
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c


# Singleton
marketplace_service = MarketplaceService()