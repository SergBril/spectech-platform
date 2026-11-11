"""Сервис маркетплейс API эндпоинтов."""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.catalog import Vehicle
from app.models.company import Company
from app.models.dispatch import Request, RequestStatus
from app.models.marketplace import MarketplaceOffer
from app.schemas.marketplace import OfferRead, PublishRequestResponse
from app.schemas.request import MarketplaceRequestRead

logger = logging.getLogger("spectech.marketplace")


class MarketplaceRouteService:
    """Бизнес-логика маркетплейс эндпоинтов."""

    def create_offer_on_request(
        self, db: Session, company_id: int, request_id, data, current_company_id
    ):
        """
        🎯 Владелец техники предлагает свою технику на заявку.

        Может создать только владелец техники (компания, которой принадлежит техника).
        """
        # 1. Проверить заявку
        request_obj = db.get(Request, request_id)
        if not request_obj:
            raise HTTPException(status_code=404, detail="Request not found")

        # Проверить, что заявка в статусе, допускающем отклики
        allowed_statuses = [
            RequestStatus.new,
            RequestStatus.processing,
            RequestStatus.assigned,
        ]
        if request_obj.status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot create offer for request with status '{request_obj.status}'",
            )

        # 2. Проверить технику
        vehicle = db.get(Vehicle, data.vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        # 2.5 Проверить согласие на комиссию маркетплейса
        if not getattr(vehicle, "marketplace_commission_agreed", False):
            raise HTTPException(
                status_code=400,
                detail="Vehicle must agree to marketplace commission before creating offers",
            )

        # 3. Проверить, что техника принадлежит текущей компании
        if vehicle.company_id != current_company_id:
            raise HTTPException(
                status_code=403,
                detail="You can only offer vehicles owned by your company",
            )

        # 4. Проверить дубликаты (один владелец — один отклик на заявку)
        existing_offer = (
            db.query(MarketplaceOffer)
            .filter(
                MarketplaceOffer.request_id == request_id,
                MarketplaceOffer.owner_company_id == current_company_id,
                MarketplaceOffer.status == "pending",
            )
            .first()
        )
        if existing_offer:
            raise HTTPException(
                status_code=400,
                detail="Your company already has a pending offer for this request",
            )

        # 5. Создать отклик
        offer = MarketplaceOffer(
            request_id=request_id,
            owner_company_id=current_company_id,
            vehicle_id=data.vehicle_id,
            offered_price=data.offered_price,
            price_type=data.price_type,
            currency=data.currency,
            estimated_arrival_minutes=data.estimated_arrival_minutes,
            distance_km=data.distance_km,
            message=data.message,
            status="pending",
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)
        # MAX notification to request owner about new offer
        try:
            from app.services.max_messenger_service import (
                max_messenger_service,
                notification_templates,
            )

            title, body = notification_templates.offer_received(
                request_id=request_obj.id,
                vehicle_name=vehicle.name if vehicle else "N/A",
                offered_price=float(data.offered_price),
                price_type=data.price_type,
            )
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    max_messenger_service.notify_company_dispatchers(
                        db, request_obj.company_id, title, body
                    )
                )
            except RuntimeError:
                pass
        except Exception as max_err:
            logger.warning("MAX offer notification failed: %s", max_err)

        logger.info(
            "Offer created: id=%s, request=%s, company=%s, vehicle=%s, price=%s",
            offer.id,
            request_id,
            current_company_id,
            data.vehicle_id,
            data.offered_price,
        )

        return self._build_offer_response(offer, db)

    def list_offers_for_request(
        self, db: Session, request_id, status, current_company_id
    ):
        """
        🎯 Список откликов на заявку.

        Доступен всем участникам: заказчику, владельцам, диспетчерам.
        """
        # 1. Проверить заявку
        request_obj = db.get(Request, request_id)
        if not request_obj:
            raise HTTPException(status_code=404, detail="Request not found")

        # 2. Запросить отклики
        stmt = (
            select(MarketplaceOffer)
            .options(
                joinedload(MarketplaceOffer.owner_company),
                joinedload(MarketplaceOffer.vehicle),
            )
            .where(MarketplaceOffer.request_id == request_id)
            .order_by(MarketplaceOffer.created_at.desc())
        )

        if status:
            stmt = stmt.where(MarketplaceOffer.status == status)

        offers = db.scalars(stmt).unique().all()

        return [self._build_offer_response(offer, db) for offer in offers]

    def get_offer_details(self, db: Session, offer_id):
        """
        🎯 Детали конкретного отклика.

        Доступен всем участникам заявки.
        """
        offer = (
            db.query(MarketplaceOffer)
            .options(
                joinedload(MarketplaceOffer.owner_company),
                joinedload(MarketplaceOffer.vehicle),
            )
            .filter(MarketplaceOffer.id == offer_id)
            .first()
        )
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")

        return self._build_offer_response(offer, db)

    def accept_offer(
        self,
        db: Session,
        company_id: int,
        offer_id,
        current_company_id,
        current_user=None,
    ):
        """
        🎯 Заказчик принимает отклик.

        Может принять только создатель заявки (компания-заказчик).
        После принятия:
        - Отклик переходит в статус "accepted"
        - Заявка переводится в статус "assigned"
        - Техника и оператор назначаются на заявку
        - Все остальные отклики автоматически отклоняются
        """
        # 1. Найти отклик
        offer = (
            db.query(MarketplaceOffer)
            .options(joinedload(MarketplaceOffer.request))
            .filter(MarketplaceOffer.id == offer_id)
            .first()
        )
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")

        # 2. Проверить статус отклика
        if offer.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot accept offer with status '{offer.status}'",
            )

        # 3. Проверить права (только заказчик может принять)
        request_obj = offer.request
        # Заказчик — это contractor с id = request.client_id
        # Проверяем через company_id пользователя
        # В нашей модели client_id ссылается на contractors, а не companies
        # Но можно проверить через созданного заявку пользователя
        if request_obj.created_by != current_user.id:
            # Альтернативно: проверить через company_id
            # Для простоты пока разрешим всем в компании заказчика
            if request_obj.company_id != current_company_id:
                raise HTTPException(
                    status_code=403,
                    detail="Only the request creator can accept offers",
                )

        # 4. Принять отклик
        offer.status = "accepted"
        offer.reviewed_by_id = current_user.id
        offer.reviewed_at = datetime.utcnow()

        # 5. Обновить заявку
        request_obj.status = RequestStatus.assigned
        request_obj.assigned_vehicle_id = offer.vehicle_id
        request_obj.assigned_owner_id = offer.owner_company_id

        # 6. Отклонить все остальные отклики на эту заявку
        other_offers = (
            db.query(MarketplaceOffer)
            .filter(
                MarketplaceOffer.request_id == offer.request_id,
                MarketplaceOffer.id != offer_id,
                MarketplaceOffer.status == "pending",
            )
            .all()
        )
        for other in other_offers:
            other.status = "rejected"
            other.reviewed_at = datetime.utcnow()
            other.rejection_reason = "Another offer was accepted"

        db.commit()
        db.refresh(offer)

        logger.info(
            "Offer accepted: id=%s, request=%s, vehicle=%s",
            offer.id,
            offer.request_id,
            offer.vehicle_id,
        )

        return self._build_offer_response(offer, db)

    def reject_offer(
        self,
        db: Session,
        company_id: int,
        offer_id,
        data,
        current_company_id,
        current_user=None,
    ):
        """
        🎯 Заказчик отклоняет отклик.

        Может отклонить только создатель заявки.
        """
        # 1. Найти отклик
        offer = (
            db.query(MarketplaceOffer)
            .options(joinedload(MarketplaceOffer.request))
            .filter(MarketplaceOffer.id == offer_id)
            .first()
        )
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")

        # 2. Проверить статус
        if offer.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject offer with status '{offer.status}'",
            )

        # 3. Проверить права
        request_obj = offer.request
        if request_obj.created_by != current_user.id:
            if request_obj.company_id != current_company_id:
                raise HTTPException(
                    status_code=403,
                    detail="Only the request creator can reject offers",
                )

        # 4. Отклонить отклик
        offer.status = "rejected"
        offer.reviewed_by_id = current_user.id
        offer.reviewed_at = datetime.utcnow()
        offer.rejection_reason = data.rejection_reason

        db.commit()
        db.refresh(offer)

        logger.info(
            "Offer rejected: id=%s, request=%s, reason=%s",
            offer.id,
            offer.request_id,
            data.rejection_reason,
        )

        return self._build_offer_response(offer, db)

    def get_matching_vehicles_for_request(
        self, db: Session, company_id: int, request_id
    ):
        """
        Возвращает список техники текущей компании, подходящей для заявки.
        Использует VehicleMatcherService для скоринга по атрибутам и категориям.
        """
        request_obj = db.get(Request, request_id)
        if not request_obj:
            raise HTTPException(status_code=404, detail="Request not found")

        from app.services.marketplace.vehicle_matcher import vehicle_matcher

        matches = vehicle_matcher.find_matching_vehicles(
            db=db, request_id=request_id, company_id=company_id
        )

        return {
            "request_id": request_id,
            "total_matches": len(matches),
            "vehicles": matches,
        }

    def create_surplus_request(
        self, db: Session, company_id: int, data, current_user=None
    ):
        """
        Владелец техники создаёт заявку на свою свободную технику.
        Комиссия: dispatcher_commission_pct% диспетчеру, остальное — исполнителю.
        Заявка автоматически публикуется в маркетплейсе.
        """
        # Validate vehicle ownership
        vehicle = db.get(Vehicle, data.vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if vehicle.company_id != company_id:
            raise HTTPException(
                status_code=403, detail="Vehicle belongs to another company"
            )

        # Calculate commission split
        performer_pct = 100 - data.dispatcher_commission_pct
        estimated_amount = float(data.offered_price)
        if data.price_type == "per_hour" and data.shift_duration_hours:
            estimated_amount = float(data.offered_price) * data.shift_duration_hours

        dispatcher_fee = round(
            estimated_amount * data.dispatcher_commission_pct / 100, 2
        )
        performer_pay = round(estimated_amount * performer_pct / 100, 2)

        # Create request with marketplace_mode = owner_dispatcher
        request_obj = Request(
            company_id=company_id,
            created_by=current_user.id,
            work_type=data.work_type,
            object_address=data.object_address,
            region=data.region,
            planned_start=data.planned_start,
            planned_end=data.planned_end,
            shift_duration_hours=data.shift_duration_hours,
            client_rate=float(data.offered_price),
            rate_type=data.price_type,
            estimated_amount=estimated_amount,
            source_channel="marketplace",
            marketplace_mode="owner_dispatcher",
            is_published=True,
            published_at=datetime.now(UTC),
            comment=(
                f"{data.comment or ''}\n\n"
                f"[Surplus] Техника: {vehicle.name}. "
                f"Комиссия: {data.dispatcher_commission_pct}% диспетчеру ({dispatcher_fee} ₽), "
                f"{performer_pct}% исполнителю ({performer_pay} ₽)"
            ),
            priority="normal",
        )

        # Set vehicle category from the vehicle
        if vehicle.category_id:
            request_obj.vehicle_category_id = vehicle.category_id

        db.add(request_obj)
        db.flush()

        # Log status
        from app.models.dispatch import RequestStatusLog

        db.add(
            RequestStatusLog(
                request_id=request_obj.id,
                from_status=None,
                to_status="new",
                changed_by_user_id=current_user.id,
                comment="Surplus заявка создана владельцем техники",
            )
        )

        db.commit()
        db.refresh(request_obj)

        logger.info(
            f"Surplus request #{request_obj.id} created by company #{company_id}, "
            f"vehicle={vehicle.name}, commission={data.dispatcher_commission_pct}%"
        )

        return {
            "id": request_obj.id,
            "vehicle_name": vehicle.name,
            "work_type": request_obj.work_type,
            "estimated_amount": estimated_amount,
            "dispatcher_commission_pct": data.dispatcher_commission_pct,
            "dispatcher_fee": dispatcher_fee,
            "performer_pay": performer_pay,
            "is_published": True,
            "marketplace_mode": "owner_dispatcher",
        }

    def _build_offer_response(self, offer, db: Session):
        """Построение полного ответа для отклика."""
        # Получить связанные объекты
        owner_company = (
            db.get(Company, offer.owner_company_id) if offer.owner_company_id else None
        )
        vehicle = db.get(Vehicle, offer.vehicle_id) if offer.vehicle_id else None

        # Получить категорию техники
        vehicle_category_name = None
        if vehicle and vehicle.category_id:
            category = db.get(
                __import__("app.models.catalog", fromlist=["Category"]).Category,
                vehicle.category_id,
            )
            if category:
                vehicle_category_name = category.name

        return OfferRead(
            id=offer.id,
            request_id=offer.request_id,
            owner_company_id=offer.owner_company_id,
            owner_company_name=owner_company.name if owner_company else None,
            vehicle_id=offer.vehicle_id,
            vehicle_name=vehicle.name if vehicle else None,
            vehicle_category_name=vehicle_category_name,
            operator_id=offer.operator_id,
            offered_price=offer.offered_price,
            price_type=offer.price_type,
            currency=offer.currency,
            estimated_arrival_minutes=offer.estimated_arrival_minutes,
            distance_km=offer.distance_km,
            message=offer.message,
            status=offer.status,
            reviewed_by_id=offer.reviewed_by_id,
            reviewed_at=offer.reviewed_at,
            rejection_reason=offer.rejection_reason,
            created_at=offer.created_at,
            updated_at=offer.updated_at,
        )

    def publish_request(
        self, db: Session, company_id: int, request_id, current_user=None
    ):
        """
        Публикует заявку в маркетплейсе.
        Другие компании смогут видеть заявку и предлагать свою технику.
        """
        request = db.get(Request, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Заявка не найдена")

        if request.company_id != company_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")

        if request.status in (
            RequestStatus.completed,
            RequestStatus.closed,
            RequestStatus.cancelled,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Нельзя опубликовать заявку в статусе '{request.status.value}'",
            )

        if request.is_published:
            return PublishRequestResponse(
                request_id=request.id,
                is_published=True,
                published_at=(
                    request.published_at.isoformat() if request.published_at else None
                ),
                message="Заявка уже опубликована",
            )

        from datetime import UTC, datetime

        request.is_published = True
        request.published_at = datetime.now(UTC)
        db.commit()
        db.refresh(request)

        logger.info(
            "Request #%s published to marketplace by user #%s",
            request_id,
            current_user.id,
        )

        return PublishRequestResponse(
            request_id=request.id,
            is_published=True,
            published_at=(
                request.published_at.isoformat() if request.published_at else None
            ),
            message="Заявка успешно опубликована в маркетплейсе",
        )

    def unpublish_request(
        self, db: Session, company_id: int, request_id, current_user=None
    ):
        """Снимает публикацию заявки из маркетплейса."""
        request = db.get(Request, request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Заявка не найдена")

        if request.company_id != company_id:
            raise HTTPException(status_code=403, detail="Нет доступа к этой заявке")

        if not request.is_published:
            return PublishRequestResponse(
                request_id=request.id,
                is_published=False,
                published_at=None,
                message="Заявка не опубликована",
            )

        request.is_published = False
        request.published_at = None
        db.commit()

        logger.info(
            "Request #%s unpublished from marketplace by user #%s",
            request_id,
            current_user.id,
        )

        return PublishRequestResponse(
            request_id=request.id,
            is_published=False,
            published_at=None,
            message="Заявка снята с маркетплейса",
        )

    def list_marketplace_requests(
        self, db: Session, company_id: int, skip, limit, category_id, region
    ):
        """
        Список опубликованных заявок от ДРУГИХ компаний.
        Текущая компания видит чужие заявки и может предложить свою технику.
        """
        # my vehicle categories lookup
        my_vehicle_categories = (
            db.query(Vehicle.category_id)
            .filter(
                Vehicle.company_id == company_id,
                Vehicle.category_id.isnot(None),
                Vehicle.is_deleted == False,  # noqa: E711
            )
            .distinct()
            .all()
        )
        my_category_ids = {row[0] for row in my_vehicle_categories if row[0]}

        query = (
            select(Request)
            .where(
                Request.is_published == True,
                Request.company_id != company_id,  # Только чужие заявки
                Request.status.notin_(
                    [
                        RequestStatus.completed,
                        RequestStatus.closed,
                        RequestStatus.cancelled,
                    ]
                ),
            )
            .order_by(Request.published_at.desc())
            .offset(skip)
            .limit(limit)
        )

        if category_id:
            query = query.where(Request.vehicle_category_id == category_id)

        if region:
            query = query.where(Request.region == region)

        # Filter: only show requests matching company vehicles
        if my_category_ids:
            query = query.where(
                (Request.vehicle_category_id.is_(None))
                | (Request.vehicle_category_id.in_(my_category_ids))
            )

        requests = db.execute(query).scalars().all()

        result = []
        for req in requests:
            # Подсчёт откликов
            offers_count = (
                db.query(MarketplaceOffer)
                .filter(
                    MarketplaceOffer.request_id == req.id,
                    MarketplaceOffer.status != "withdrawn",
                )
                .count()
            )

            # Название категории
            cat_name = None
            if req.vehicle_category_id:
                cat = db.get(
                    __import__("app.models.catalog", fromlist=["Category"]).Category,
                    req.vehicle_category_id,
                )
                if cat:
                    cat_name = cat.name

            result.append(
                MarketplaceRequestRead(
                    id=req.id,
                    work_type=req.work_type,
                    object_address=req.object_address,
                    planned_start=req.planned_start,
                    planned_end=req.planned_end,
                    shift_duration_hours=(
                        float(req.shift_duration_hours)
                        if req.shift_duration_hours
                        else None
                    ),
                    client_rate=float(req.client_rate) if req.client_rate else None,
                    rate_type=req.rate_type,
                    estimated_amount=(
                        float(req.estimated_amount) if req.estimated_amount else None
                    ),
                    priority=req.priority,
                    vehicle_category_id=req.vehicle_category_id,
                    vehicle_category_name=cat_name,
                    offers_count=offers_count,
                    published_at=req.published_at,
                    marketplace_mode=getattr(req, "marketplace_mode", None),
                    is_surplus="[Surplus]" in (getattr(req, "comment", "") or ""),
                )
            )

        return result


# Singleton
marketplace_route_service = MarketplaceRouteService()
