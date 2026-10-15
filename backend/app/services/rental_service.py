"""Сервис аренды техники — бизнес-логика."""

import logging
from datetime import UTC, datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from app.models.finance import Invoice, InvoiceItem, Act, DocumentStatus
from app.services.finance_service import generate_document_number
from app.core.constants import TaxSystem
from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session, selectinload
from app.models.catalog import Vehicle
from app.models.finance import Invoice, InvoiceItem, Act, Payout, DocumentStatus
from app.models.rental import (
    PrepaymentStatus,
    RateType,
    Rental,
    RentalItem,
    RentalStatus,
)
from app.schemas.rental import (
    RentalClose,
    RentalCreate,
    RentalItemAdd,
    RentalUpdate,
)

logger = logging.getLogger("spectech.rental_service")

# Минимальная длительность для тарификации (защита от деления на 0)
MIN_HOURS = Decimal("0.5")


class RentalService:
    """Сервис для управления договорами аренды."""

    # =====================================================================
    # Вспомогательные методы расчёта
    # =====================================================================

    @staticmethod
    def _calculate_duration_hours(start: datetime, end: datetime) -> Decimal:
        """Рассчитывает длительность в часах (с учётом timezone)."""
        if not start or not end:
            return Decimal("0")
        # Нормализуем таймзоны
        s = start if start.tzinfo else start.replace(tzinfo=UTC)
        e = end if end.tzinfo else end.replace(tzinfo=UTC)
        delta_seconds = (e - s).total_seconds()
        hours = Decimal(str(delta_seconds)) / Decimal("3600")
        return max(hours, MIN_HOURS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _calculate_days(start: datetime, end: datetime) -> Decimal:
        """Рассчитывает количество смен (1 смена = 24 часа)."""
        hours = RentalService._calculate_duration_hours(start, end)
        # Округляем вверх: 12 часов = 1 смена, 25 часов = 2 смены
        shifts = (hours / Decimal("8")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return max(shifts, Decimal("1"))

    @staticmethod
    def _calculate_plan_amount(rental: Rental) -> Decimal:
        """
        Рассчитывает плановую стоимость аренды на момент создания/обновления.
        Зависит от rate_type.
        """
        total = Decimal("0")

        for item in rental.items:
            quantity = Decimal(str(item.quantity or 1))
            price = Decimal(str(item.unit_price or 0))

            if rental.rate_type == RateType.HOURLY:
                hours = RentalService._calculate_duration_hours(
                    rental.start_date, rental.end_date
                )
                total += hours * price * quantity

            elif rental.rate_type == RateType.SHIFT:
                shifts = RentalService._calculate_days(
                    rental.start_date, rental.end_date
                )
                total += shifts * price * quantity

            elif rental.rate_type == RateType.TRIP:
                # При создании количество ходок неизвестно — используем unit_price как "минимальный платёж"
                total += price * quantity

            elif rental.rate_type == RateType.VOLUME:
                # При создании объём неизвестен — минимальный платёж
                total += price * quantity

            elif rental.rate_type == RateType.MILEAGE:
                # При создании пробег неизвестен — минимальный платёж
                total += price * quantity

            elif rental.rate_type == RateType.COMBINED:
                hours = RentalService._calculate_duration_hours(
                    rental.start_date, rental.end_date
                )
                total += hours * price * quantity

        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _calculate_actual_amount(rental: Rental) -> Decimal:
        """
        Рассчитывает фактическую стоимость по завершении аренды
        на основе фактических данных (моточасы, пробег, ходки, объём).
        """
        total = Decimal("0")

        for item in rental.items:
            quantity = Decimal(str(item.quantity or 1))
            price = Decimal(str(item.unit_price or 0))

            if rental.rate_type == RateType.HOURLY:
                hours = Decimal(str(item.actual_moto_hours or 0))
                if hours <= 0:
                    hours = RentalService._calculate_duration_hours(
                        rental.start_date,
                        rental.actual_return_date or rental.end_date,
                    )
                total += hours * price * quantity

            elif rental.rate_type == RateType.SHIFT:
                # Для смен — считаем по фактическому времени работы
                hours = RentalService._calculate_duration_hours(
                    rental.start_date,
                    rental.actual_return_date or rental.end_date,
                )
                shifts = (hours / Decimal("8")).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
                total += max(shifts, Decimal("1")) * price * quantity

            elif rental.rate_type == RateType.TRIP:
                trips = Decimal(str(item.actual_trips or 0))
                total += trips * price * quantity

            elif rental.rate_type == RateType.VOLUME:
                volume = Decimal(str(item.actual_volume or 0))
                total += volume * price * quantity

            elif rental.rate_type == RateType.MILEAGE:
                mileage = Decimal(str(item.actual_mileage or 0))
                total += mileage * price * quantity

            elif rental.rate_type == RateType.COMBINED:
                hours = Decimal(str(item.actual_moto_hours or 0))
                mileage = Decimal(str(item.actual_mileage or 0))
                # Для комбо: unit_price — это ставка за час,
                # а mileage_rate берём из rental
                hourly_part = hours * price * quantity
                mileage_rate = Decimal(str(rental.mileage_rate or 0))
                mileage_part = mileage * mileage_rate * quantity
                total += hourly_part + mileage_part

        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # =====================================================================
    # Проверка доступности техники
    # =====================================================================

    @staticmethod
    def _check_vehicle_availability(
        db: Session,
        vehicle_id: int,
        start: datetime,
        end: datetime,
        exclude_rental_id: int | None = None,
    ) -> bool:
        """Проверяет, что техника свободна в указанный период."""
        query = (
            db.query(RentalItem)
            .join(Rental)
            .filter(
                RentalItem.vehicle_id == vehicle_id,
                Rental.status.in_([
                    RentalStatus.DRAFT,
                    RentalStatus.ACTIVE,
                ]),
                Rental.start_date < end,
                Rental.end_date > start,
            )
        )
        if exclude_rental_id:
            query = query.filter(Rental.id != exclude_rental_id)

        return query.first() is None

    # =====================================================================
    # CRUD операции
    # =====================================================================

    @staticmethod
    def create_rental(
        db: Session,
        rental_in: RentalCreate,
        company_id: int,
        created_by: int,
    ) -> Rental:
        """Создаёт договор аренды в статусе DRAFT."""
        # Валидация дат
        if rental_in.start_date >= rental_in.end_date:
            raise HTTPException(
                status_code=400,
                detail="Дата начала должна быть раньше даты окончания",
            )

        # Создаём объект аренды (без items, чтобы сначала проставить rate_type)
        rental = Rental(
            client_id=rental_in.client_id,
            request_id=rental_in.request_id,
            company_id=company_id,
            created_by=created_by,
            start_date=rental_in.start_date,
            end_date=rental_in.end_date,
            rate_type=rental_in.rate_type or RateType.HOURLY,
            hourly_rate=rental_in.hourly_rate,
            shift_rate=rental_in.shift_rate,
            trip_rate=rental_in.trip_rate,
            volume_rate=rental_in.volume_rate,
            mileage_rate=rental_in.mileage_rate,
            discount=rental_in.discount or Decimal("0"),
            prepayment_status=rental_in.prepayment_status or PrepaymentStatus.NONE,
            prepayment_amount=rental_in.prepayment_amount,
            comment=rental_in.comment,
            status=RentalStatus.DRAFT,
        )
        db.add(rental)
        db.flush()  # Получаем rental.id

        # Добавляем позиции
        rental_items = []
        for item_in in rental_in.items:
            # Проверка доступности
            if not RentalService._check_vehicle_availability(
                db, item_in.vehicle_id, rental_in.start_date, rental_in.end_date
            ):
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=f"Техника {item_in.vehicle_id} уже забронирована на эти даты",
                )

            rental_items.append(
                RentalItem(
                    rental_id=rental.id,
                    vehicle_id=item_in.vehicle_id,
                    quantity=item_in.quantity or 1,
                    unit_price=item_in.unit_price,
                )
            )

        db.add_all(rental_items)
        db.flush()

        # Рассчитываем плановую стоимость
        rental.base_price = RentalService._calculate_plan_amount(rental)
        rental.total_amount = max(
            rental.base_price - (rental.discount or Decimal("0")),
            Decimal("0"),
        )

        db.commit()
        db.refresh(rental)

        logger.info(
            "Rental #%s created: client=%s, rate_type=%s, total=%s",
            rental.id, rental.client_id, rental.rate_type.value, rental.total_amount,
        )
        return rental

    @staticmethod
    def get_rental(db: Session, rental_id: int, company_id: int) -> Rental:
        """Получить аренду с учётом company_id (мультитенантность)."""
        rental = (
            db.query(Rental)
            .options(selectinload(Rental.items))
            .filter(Rental.id == rental_id, Rental.company_id.in_(company_ids))
            .first()
        )
        if not rental:
            raise HTTPException(status_code=404, detail="Аренда не найдена")
        return rental

    @staticmethod
    def list_rentals(
        db: Session,
        company_ids: list[int],
        status: RentalStatus | None = None,
        client_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Rental]:
        """Список аренд с фильтрами."""
        query = (
            db.query(Rental)
            .options(selectinload(Rental.items))
            .filter(Rental.company_id.in_(company_ids))
        )
        if status:
            query = query.filter(Rental.status == status)
        if client_id:
            query = query.filter(Rental.client_id == client_id)

        return (
            query.order_by(Rental.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_rental(
        db: Session,
        rental_id: int,
        data: RentalUpdate,
        company_id: int,
    ) -> Rental:
        """Обновить аренду (только в DRAFT)."""
        rental = RentalService.get_rental(db, rental_id, company_id)

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Нельзя редактировать аренду в статусе {rental.status.value}",
            )

        # Обновляем поля, если переданы
        if data.start_date is not None:
            rental.start_date = data.start_date
        if data.end_date is not None:
            rental.end_date = data.end_date
        if data.discount is not None:
            rental.discount = data.discount
        if data.comment is not None:
            rental.comment = data.comment
        if data.prepayment_status is not None:
            rental.prepayment_status = data.prepayment_status
        if data.prepayment_amount is not None:
            rental.prepayment_amount = data.prepayment_amount

        # Валидация дат
        if rental.start_date >= rental.end_date:
            raise HTTPException(
                status_code=400,
                detail="Дата начала должна быть раньше даты окончания",
            )

        # Пересчёт стоимости
        rental.base_price = RentalService._calculate_plan_amount(rental)
        rental.total_amount = max(
            rental.base_price - (rental.discount or Decimal("0")),
            Decimal("0"),
        )

        db.commit()
        db.refresh(rental)
        return rental

    # =====================================================================
    # Управление позициями
    # =====================================================================

    @staticmethod
    def add_rental_item(
        db: Session,
        rental_id: int,
        item_in: RentalItemAdd,
        company_id: int,
    ) -> RentalItem:
        """Добавить технику в аренду (только в DRAFT)."""
        rental = RentalService.get_rental(db, rental_id, company_id)

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Нельзя добавлять позиции в активную аренду",
            )

        # Проверка доступности
        if not RentalService._check_vehicle_availability(
            db,
            item_in.vehicle_id,
            rental.start_date,
            rental.end_date,
            exclude_rental_id=rental.id,
        ):
            raise HTTPException(
                status_code=409,
                detail=f"Техника {item_in.vehicle_id} уже забронирована на эти даты",
            )

        item = RentalItem(
            rental_id=rental.id,
            vehicle_id=item_in.vehicle_id,
            quantity=item_in.quantity or 1,
            unit_price=item_in.unit_price,
        )
        db.add(item)
        db.flush()

        # Пересчёт
        rental.base_price = RentalService._calculate_plan_amount(rental)
        rental.total_amount = max(
            rental.base_price - (rental.discount or Decimal("0")),
            Decimal("0"),
        )

        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def remove_rental_item(
        db: Session,
        rental_id: int,
        item_id: int,
        company_id: int,
    ) -> None:
        """Удалить позицию из аренды (только в DRAFT)."""
        rental = RentalService.get_rental(db, rental_id, company_id)

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Нельзя удалять позиции из активной аренды",
            )

        item = next((i for i in rental.items if i.id == item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="Позиция не найдена")

        db.delete(item)
        db.flush()

        # Пересчёт
        rental.base_price = RentalService._calculate_plan_amount(rental)
        rental.total_amount = max(
            rental.base_price - (rental.discount or Decimal("0")),
            Decimal("0"),
        )

        db.commit()

    # =====================================================================
    # Управление статусами (Workflow)
    # =====================================================================

    @staticmethod
    def activate_rental(db: Session, rental_id: int, company_id: int) -> Rental:
        """Активировать аренду (DRAFT → ACTIVE). Техника выдана."""
        rental = RentalService.get_rental(db, rental_id, company_id)

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Нельзя активировать аренду в статусе {rental.status.value}",
            )

        if not rental.items:
            raise HTTPException(
                status_code=400,
                detail="Нельзя активировать аренду без позиций",
            )

        # Проверка предоплаты
        if (
            rental.prepayment_status == PrepaymentStatus.REQUIRED
            and not rental.prepayment_paid_at
        ):
            raise HTTPException(
                status_code=400,
                detail="Требуется предоплата перед активацией",
            )

        rental.status = RentalStatus.ACTIVE
        db.commit()
        db.refresh(rental)

        logger.info("Rental #%s activated", rental.id)
        return rental

    @staticmethod
    def cancel_rental(db: Session, rental_id: int, company_id: int) -> Rental:
        """Отменить аренду (DRAFT/ACTIVE → CANCELLED)."""
        rental = RentalService.get_rental(db, rental_id, company_id)

        if rental.status not in [RentalStatus.DRAFT, RentalStatus.ACTIVE]:
            raise HTTPException(
                status_code=400,
                detail=f"Нельзя отменить аренду в статусе {rental.status.value}",
            )

        rental.status = RentalStatus.CANCELLED

        # Возврат предоплаты, если была
        if rental.prepayment_paid_at:
            rental.prepayment_status = PrepaymentStatus.REFUNDED

        db.commit()
        db.refresh(rental)

        logger.info("Rental #%s cancelled", rental.id)
        return rental

    @staticmethod
    def close_rental(
        db: Session,
        rental_id: int,
        data: RentalClose,
        company_id: int,
    ) -> Rental:
        """
        Завершить аренду (ACTIVE → COMPLETED).
        Принимает фактические данные, пересчитывает стоимость и создаёт Invoice.
        """
        rental = RentalService.get_rental(db, rental_id, company_id)

        if rental.status != RentalStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail=f"Нельзя завершить аренду в статусе {rental.status.value}",
            )

        # Нормализуем actual_return_date
        actual_return_dt = data.actual_return_date or datetime.now(UTC)
        if actual_return_dt.tzinfo is None:
            actual_return_dt = actual_return_dt.replace(tzinfo=UTC)
        rental.actual_return_date = actual_return_dt

        # Нормализуем end_date для безопасного сравнения
        end_date_norm = rental.end_date
        if end_date_norm.tzinfo is None:
            end_date_norm = end_date_norm.replace(tzinfo=UTC)

        # Обновляем фактические данные по позициям
        if data.items_actuals:
            items_map = {i.id: i for i in rental.items}
            for actual in data.items_actuals:
                item = items_map.get(actual.rental_item_id)
                if item:
                    if actual.actual_moto_hours is not None:
                        item.actual_moto_hours = actual.actual_moto_hours
                    if actual.actual_mileage is not None:
                        item.actual_mileage = actual.actual_mileage
                    if actual.actual_trips is not None:
                        item.actual_trips = actual.actual_trips
                    if actual.actual_volume is not None:
                        item.actual_volume = actual.actual_volume

        # Пересчёт по факту
        actual_amount = RentalService._calculate_actual_amount(rental)

        # Штраф за просрочку (сравниваем нормализованные даты!)
        overdue_penalty = Decimal("0")
        if rental.actual_return_date > end_date_norm:
            overdue_hours = RentalService._calculate_duration_hours(
                end_date_norm, rental.actual_return_date
            )
            # Штраф = 150% от часовой ставки за каждый час просрочки
            penalty_rate = Decimal("1.5")
            for item in rental.items:
                hourly_price = Decimal(str(item.unit_price or 0))
                qty = Decimal(str(item.quantity or 1))
                overdue_penalty += overdue_hours * hourly_price * qty * penalty_rate
            overdue_penalty = overdue_penalty.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Финальная сумма = факт + штраф - скидка
        rental.base_price = actual_amount
        rental.total_amount = max(
            actual_amount + overdue_penalty - (rental.discount or Decimal("0")),
            Decimal("0"),
        )
        rental.status = RentalStatus.COMPLETED

        db.commit()
        db.refresh(rental)

        logger.info(
            "Rental #%s closed: actual=%s, penalty=%s, total=%s",
            rental.id, actual_amount, overdue_penalty, rental.total_amount,
        )

        # 🆕 Автосоздание Invoice при завершении аренды
        try:
            RentalService._create_documents_from_rental(db, rental)
        except Exception as e:
            # Логируем ошибку, но не прерываем завершение аренды
            logger.error(
                "Failed to auto-create documents for Rental #%s: %s",
                rental.id, str(e), exc_info=True
            )

        return rental

    @staticmethod
    def _create_documents_from_rental(db: Session, rental: Rental) -> tuple:
        """
        Создаёт полный пакет документов при завершении аренды:
        - Invoice (счёт клиенту)
        - Act (акт выполненных работ)
        - Payout(s) (выплаты собственникам техники)
        
        Также отправляет уведомления по всем каналам.
        """
        invoice = RentalService._create_invoice_from_rental(db, rental)
        act = RentalService._create_act_from_rental(db, rental, invoice)
        payouts = RentalService._create_payouts_from_rental(db, rental)
        
        # 🆕 Отправляем уведомления асинхронно
        RentalService._send_rental_notifications(db, rental, invoice, payouts)
        
        return invoice, act, payouts

    @staticmethod
    def _create_invoice_from_rental(db: Session, rental: Rental) -> "Invoice":
        """Создаёт Invoice на основе завершённой аренды."""
        from app.models.finance import Invoice, InvoiceItem, DocumentStatus
        from app.services.finance_service import generate_document_number
        from app.core.constants import TaxSystem
        from datetime import date, timedelta
        
        vat_rate = Decimal("20.00")
        subtotal = rental.total_amount
        vat_amount = (subtotal * vat_rate / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        total = subtotal + vat_amount

        invoice = Invoice(
            document_number=generate_document_number(db, "INV"),
            rental_id=rental.id,
            request_id=rental.request_id,
            client_id=rental.client_id,
            company_id=rental.company_id,
            subtotal=subtotal,
            vat_amount=vat_amount,
            vat_rate=vat_rate,
            total=total,
            paid_amount=Decimal("0.00"),
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status=DocumentStatus.draft,
            tax_system=TaxSystem.OSNO.value,
            is_vat_included=False,
            comment=f"Автосоздан при завершении аренды #{rental.id}",
        )
        db.add(invoice)
        db.flush()

        rate_type_desc = {
            RateType.HOURLY: "Аренда техники (почасовая)",
            RateType.SHIFT: "Аренда техники (посменная)",
            RateType.TRIP: "Аренда техники (за ходку)",
            RateType.VOLUME: "Аренда техники (за объём)",
            RateType.MILEAGE: "Аренда техники (по пробегу)",
            RateType.COMBINED: "Аренда техники (комбинированная)",
        }
        description = rate_type_desc.get(rental.rate_type, "Аренда техники")

        unit_map = {
            RateType.HOURLY: "моточас",
            RateType.SHIFT: "смена",
            RateType.TRIP: "ходка",
            RateType.VOLUME: "м³",
            RateType.MILEAGE: "км",
            RateType.COMBINED: "усл.",
        }
        unit = unit_map.get(rental.rate_type, "усл.")

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            description=f"{description} (Договор аренды #{rental.id})",
            quantity=Decimal("1"),
            unit=unit,
            unit_price=rental.total_amount,
            amount=rental.total_amount,
        )
        db.add(invoice_item)
        db.flush()

        logger.info(
            "Auto-created Invoice #%s (%s) for Rental #%s: total=%s",
            invoice.id, invoice.document_number, rental.id, total,
        )
        return invoice

    @staticmethod
    def _create_act_from_rental(db: Session, rental: Rental, invoice: "Invoice") -> "Act":
        """Создаёт Act на основе завершённой аренды."""
        from app.models.finance import Act, DocumentStatus
        from app.services.finance_service import generate_document_number
        from app.core.constants import TaxSystem
        from datetime import date
        
        act = Act(
            document_number=generate_document_number(db, "ACT"),
            rental_id=rental.id,
            request_id=rental.request_id,
            client_id=rental.client_id,
            company_id=rental.company_id,
            total_amount=invoice.total,
            vat_amount=invoice.vat_amount,
            vat_rate=invoice.vat_rate,
            tax_system=TaxSystem.OSNO.value,
            is_vat_included=True,
            act_date=date.today(),
            status=DocumentStatus.sent,
            comment=f"Автосоздан при завершении аренды #{rental.id}",
        )
        db.add(act)
        db.flush()

        logger.info(
            "Auto-created Act #%s (%s) for Rental #%s: total=%s",
            act.id, act.document_number, rental.id, act.total_amount,
        )
        return act

    @staticmethod
    def _create_payouts_from_rental(db: Session, rental: Rental) -> list:
        """Создаёт Payout для каждого собственника техники в аренде."""
        from app.models.catalog import Vehicle
        from app.models.finance import Payout, DocumentStatus
        from app.services.finance_service import generate_document_number
        from datetime import date
        from collections import defaultdict
        
        total_items_cost = Decimal("0")
        for item in rental.items:
            item_cost = Decimal(str(item.unit_price or 0)) * Decimal(str(item.quantity or 1))
            total_items_cost += item_cost
        
        if total_items_cost == Decimal("0"):
            logger.warning(f"Rental #{rental.id} has zero total, skipping payouts")
            return []
        
        owner_data = defaultdict(lambda: {
            "gross": Decimal("0"),
            "vehicle_ids": [],
        })
        
        total_rental_amount = rental.total_amount
        
        for item in rental.items:
            vehicle = db.get(Vehicle, item.vehicle_id)
            if not vehicle:
                logger.warning(f"Vehicle {item.vehicle_id} not found, skipping")
                continue
            
            if not vehicle.owner_id:
                logger.warning(f"Vehicle {item.vehicle_id} has no owner, skipping payout")
                continue
            
            item_cost = Decimal(str(item.unit_price or 0)) * Decimal(str(item.quantity or 1))
            share = item_cost / total_items_cost
            owner_share = total_rental_amount * share
            
            owner_data[vehicle.owner_id]["gross"] += owner_share
            owner_data[vehicle.owner_id]["vehicle_ids"].append(vehicle.id)
        
        payouts = []
        commission_rate = rental.commission_rate or Decimal("10.00")
        
        base_doc_number = generate_document_number(db, "PAY")
        base_number_part = base_doc_number.replace("PAY-", "")
        
        for idx, (owner_id, data) in enumerate(owner_data.items(), start=1):
            gross_amount = data["gross"].quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            commission = (gross_amount * commission_rate / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            net_amount = gross_amount - commission
            
            unique_doc_number = f"PAY-{base_number_part}-{idx}"
            
            payout = Payout(
                document_number=unique_doc_number,
                rental_id=rental.id,
                owner_id=owner_id,
                vehicle_id=data["vehicle_ids"][0] if data["vehicle_ids"] else None,
                request_id=rental.request_id,
                company_id=rental.company_id,
                gross_amount=gross_amount,
                platform_commission=commission,
                net_amount=net_amount,
                commission_rate=commission_rate,
                payout_date=date.today(),
                status=DocumentStatus.draft,
                calculation_details={
                    "rental_id": rental.id,
                    "source": "auto_from_rental",
                    "formula": f"gross × {commission_rate}% commission",
                    "gross_amount": str(gross_amount),
                    "commission_rate": str(commission_rate),
                    "commission": str(commission),
                    "net_amount": str(net_amount),
                    "vehicle_ids": data["vehicle_ids"],
                },
                comment=f"Автосоздан при завершении аренды #{rental.id}",
            )
            db.add(payout)
            payouts.append(payout)
        
        if payouts:
            db.commit()
            for p in payouts:
                db.refresh(p)
            
            logger.info(
                "Auto-created %d Payout(s) for Rental #%s (commission_rate=%s%%)",
                len(payouts), rental.id, commission_rate,
            )
        
        return payouts

    @staticmethod
    def _send_rental_notifications(
        db: Session, rental: Rental, invoice, payouts: list
    ) -> None:
        """Отправляет уведомления о завершении аренды."""
        try:
            from app.services.notification_dispatcher import notification_dispatcher
            from app.models.contractor import Contractor
            
            # Получаем email клиента
            client = db.get(Contractor, rental.client_id)
            if not client:
                logger.warning(f"Client {rental.client_id} not found for notifications")
                return
            
            # В реальной системе email нужно брать из связанного User или contact_email
            # Пока используем заглушку
            client_email = getattr(client, 'email', None) or f"client_{client.id}@spectech.dev"
            client_name = client.name
            
            # Получаем client_user_id (если есть связь contractor -> user)
            client_user_id = getattr(client, 'user_id', None)
            
            # Асинхронно отправляем уведомления клиенту
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # В event loop — создаём задачу
                loop.create_task(
                    notification_dispatcher.notify_rental_completed(
                        db=db,
                        rental=rental,
                        invoice=invoice,
                        client_email=client_email,
                        client_name=client_name,
                        client_user_id=client_user_id,
                    )
                )
            except RuntimeError:
                # Нет event loop — пропускаем (будет отправлено позже)
                logger.info("No event loop, skipping async notifications")
            
            # Уведомления собственникам (по каждому payout)
            for payout in payouts:
                owner = db.get(Contractor, payout.owner_id)
                if not owner:
                    continue
                
                owner_email = getattr(owner, 'email', None) or f"owner_{owner.id}@spectech.dev"
                owner_name = owner.name
                owner_user_id = getattr(owner, 'user_id', None)
                
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        notification_dispatcher.notify_payout_created(
                            db=db,
                            payout=payout,
                            owner_email=owner_email,
                            owner_name=owner_name,
                            owner_user_id=owner_user_id,
                        )
                    )
                except RuntimeError:
                    logger.info("No event loop, skipping payout notification")
        
        except Exception as e:
            # Не ломаем основной процесс при ошибке уведомлений
            logger.error(f"Failed to send rental notifications: {e}", exc_info=True)


rental_service = RentalService()