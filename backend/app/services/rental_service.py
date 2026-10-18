"""РЎРµСЂРІРёСЃ Р°СЂРµРЅРґС‹ С‚РµС…РЅРёРєРё вЂ” Р±РёР·РЅРµСЃ-Р»РѕРіРёРєР°."""

import logging
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Act, Invoice
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

# РњРёРЅРёРјР°Р»СЊРЅР°СЏ РґР»РёС‚РµР»СЊРЅРѕСЃС‚СЊ РґР»СЏ С‚Р°СЂРёС„РёРєР°С†РёРё (Р·Р°С‰РёС‚Р° РѕС‚ РґРµР»РµРЅРёСЏ РЅР° 0)
MIN_HOURS = Decimal("0.5")


class RentalService:
    """РЎРµСЂРІРёСЃ РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ РґРѕРіРѕРІРѕСЂР°РјРё Р°СЂРµРЅРґС‹."""

    # =====================================================================
    # Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅС‹Рµ РјРµС‚РѕРґС‹ СЂР°СЃС‡С‘С‚Р°
    # =====================================================================

    @staticmethod
    def _calculate_duration_hours(start: datetime, end: datetime) -> Decimal:
        """Р Р°СЃСЃС‡РёС‚С‹РІР°РµС‚ РґР»РёС‚РµР»СЊРЅРѕСЃС‚СЊ РІ С‡Р°СЃР°С… (СЃ СѓС‡С‘С‚РѕРј timezone)."""
        if not start or not end:
            return Decimal("0")
        # РќРѕСЂРјР°Р»РёР·СѓРµРј С‚Р°Р№РјР·РѕРЅС‹
        s = start if start.tzinfo else start.replace(tzinfo=UTC)
        e = end if end.tzinfo else end.replace(tzinfo=UTC)
        delta_seconds = (e - s).total_seconds()
        hours = Decimal(str(delta_seconds)) / Decimal("3600")
        return max(hours, MIN_HOURS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _calculate_days(start: datetime, end: datetime) -> Decimal:
        """Р Р°СЃСЃС‡РёС‚С‹РІР°РµС‚ РєРѕР»РёС‡РµСЃС‚РІРѕ СЃРјРµРЅ (1 СЃРјРµРЅР° = 24 С‡Р°СЃР°)."""
        hours = RentalService._calculate_duration_hours(start, end)
        # РћРєСЂСѓРіР»СЏРµРј РІРІРµСЂС…: 12 С‡Р°СЃРѕРІ = 1 СЃРјРµРЅР°, 25 С‡Р°СЃРѕРІ = 2 СЃРјРµРЅС‹
        shifts = (hours / Decimal("8")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return max(shifts, Decimal("1"))

    @staticmethod
    def _calculate_plan_amount(rental: Rental) -> Decimal:
        """
        Р Р°СЃСЃС‡РёС‚С‹РІР°РµС‚ РїР»Р°РЅРѕРІСѓСЋ СЃС‚РѕРёРјРѕСЃС‚СЊ Р°СЂРµРЅРґС‹ РЅР° РјРѕРјРµРЅС‚ СЃРѕР·РґР°РЅРёСЏ/РѕР±РЅРѕРІР»РµРЅРёСЏ.
        Р—Р°РІРёСЃРёС‚ РѕС‚ rate_type.
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
                # РџСЂРё СЃРѕР·РґР°РЅРёРё РєРѕР»РёС‡РµСЃС‚РІРѕ С…РѕРґРѕРє РЅРµРёР·РІРµСЃС‚РЅРѕ вЂ” РёСЃРїРѕР»СЊР·СѓРµРј unit_price РєР°Рє "РјРёРЅРёРјР°Р»СЊРЅС‹Р№ РїР»Р°С‚С‘Р¶"
                total += price * quantity

            elif rental.rate_type == RateType.VOLUME:
                # РџСЂРё СЃРѕР·РґР°РЅРёРё РѕР±СЉС‘Рј РЅРµРёР·РІРµСЃС‚РµРЅ вЂ” РјРёРЅРёРјР°Р»СЊРЅС‹Р№ РїР»Р°С‚С‘Р¶
                total += price * quantity

            elif rental.rate_type == RateType.MILEAGE:
                # РџСЂРё СЃРѕР·РґР°РЅРёРё РїСЂРѕР±РµРі РЅРµРёР·РІРµСЃС‚РµРЅ вЂ” РјРёРЅРёРјР°Р»СЊРЅС‹Р№ РїР»Р°С‚С‘Р¶
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
        Р Р°СЃСЃС‡РёС‚С‹РІР°РµС‚ С„Р°РєС‚РёС‡РµСЃРєСѓСЋ СЃС‚РѕРёРјРѕСЃС‚СЊ РїРѕ Р·Р°РІРµСЂС€РµРЅРёРё Р°СЂРµРЅРґС‹
        РЅР° РѕСЃРЅРѕРІРµ С„Р°РєС‚РёС‡РµСЃРєРёС… РґР°РЅРЅС‹С… (РјРѕС‚РѕС‡Р°СЃС‹, РїСЂРѕР±РµРі, С…РѕРґРєРё, РѕР±СЉС‘Рј).
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
                # Р”Р»СЏ СЃРјРµРЅ вЂ” СЃС‡РёС‚Р°РµРј РїРѕ С„Р°РєС‚РёС‡РµСЃРєРѕРјСѓ РІСЂРµРјРµРЅРё СЂР°Р±РѕС‚С‹
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
                # Р”Р»СЏ РєРѕРјР±Рѕ: unit_price вЂ” СЌС‚Рѕ СЃС‚Р°РІРєР° Р·Р° С‡Р°СЃ,
                # Р° mileage_rate Р±РµСЂС‘Рј РёР· rental
                hourly_part = hours * price * quantity
                mileage_rate = Decimal(str(rental.mileage_rate or 0))
                mileage_part = mileage * mileage_rate * quantity
                total += hourly_part + mileage_part

        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # =====================================================================
    # РџСЂРѕРІРµСЂРєР° РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё С‚РµС…РЅРёРєРё
    # =====================================================================

    @staticmethod
    def _check_vehicle_availability(
        db: Session,
        vehicle_id: int,
        start: datetime,
        end: datetime,
        exclude_rental_id: int | None = None,
    ) -> bool:
        """РџСЂРѕРІРµСЂСЏРµС‚, С‡С‚Рѕ С‚РµС…РЅРёРєР° СЃРІРѕР±РѕРґРЅР° РІ СѓРєР°Р·Р°РЅРЅС‹Р№ РїРµСЂРёРѕРґ."""
        query = (
            db.query(RentalItem)
            .join(Rental)
            .filter(
                RentalItem.vehicle_id == vehicle_id,
                Rental.status.in_(
                    [
                        RentalStatus.DRAFT,
                        RentalStatus.ACTIVE,
                    ]
                ),
                Rental.start_date < end,
                Rental.end_date > start,
            )
        )
        if exclude_rental_id:
            query = query.filter(Rental.id != exclude_rental_id)

        return query.first() is None

    # =====================================================================
    # CRUD РѕРїРµСЂР°С†РёРё
    # =====================================================================

    @staticmethod
    def create_rental(
        db: Session,
        rental_in: RentalCreate,
        company_id: int,
        created_by: int,
    ) -> Rental:
        """РЎРѕР·РґР°С‘С‚ РґРѕРіРѕРІРѕСЂ Р°СЂРµРЅРґС‹ РІ СЃС‚Р°С‚СѓСЃРµ DRAFT."""
        # Р’Р°Р»РёРґР°С†РёСЏ РґР°С‚
        if rental_in.start_date >= rental_in.end_date:
            raise HTTPException(
                status_code=400,
                detail="Р”Р°С‚Р° РЅР°С‡Р°Р»Р° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ СЂР°РЅСЊС€Рµ РґР°С‚С‹ РѕРєРѕРЅС‡Р°РЅРёСЏ",
            )

        # РЎРѕР·РґР°С‘Рј РѕР±СЉРµРєС‚ Р°СЂРµРЅРґС‹ (Р±РµР· items, С‡С‚РѕР±С‹ СЃРЅР°С‡Р°Р»Р° РїСЂРѕСЃС‚Р°РІРёС‚СЊ rate_type)
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
        db.flush()  # РџРѕР»СѓС‡Р°РµРј rental.id

        # Р”РѕР±Р°РІР»СЏРµРј РїРѕР·РёС†РёРё
        rental_items = []
        for item_in in rental_in.items:
            # РџСЂРѕРІРµСЂРєР° РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё
            if not RentalService._check_vehicle_availability(
                db, item_in.vehicle_id, rental_in.start_date, rental_in.end_date
            ):
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=f"РўРµС…РЅРёРєР° {item_in.vehicle_id} СѓР¶Рµ Р·Р°Р±СЂРѕРЅРёСЂРѕРІР°РЅР° РЅР° СЌС‚Рё РґР°С‚С‹",
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

        # Р Р°СЃСЃС‡РёС‚С‹РІР°РµРј РїР»Р°РЅРѕРІСѓСЋ СЃС‚РѕРёРјРѕСЃС‚СЊ
        rental.base_price = RentalService._calculate_plan_amount(rental)
        rental.total_amount = max(
            rental.base_price - (rental.discount or Decimal("0")),
            Decimal("0"),
        )

        db.commit()
        db.refresh(rental)

        logger.info(
            "Rental #%s created: client=%s, rate_type=%s, total=%s",
            rental.id,
            rental.client_id,
            rental.rate_type.value,
            rental.total_amount,
        )
        return rental

    @staticmethod
    def get_rental(db: Session, rental_id: int, company_ids: list[int]) -> Rental:
        """РџРѕР»СѓС‡РёС‚СЊ Р°СЂРµРЅРґСѓ СЃ СѓС‡С‘С‚РѕРј company_id (РјСѓР»СЊС‚РёС‚РµРЅР°РЅС‚РЅРѕСЃС‚СЊ)."""
        rental = (
            db.query(Rental)
            .options(selectinload(Rental.items))
            .filter(Rental.id == rental_id, Rental.company_id.in_(company_ids))
            .first()
        )
        if not rental:
            raise HTTPException(
                status_code=404, detail="РђСЂРµРЅРґР° РЅРµ РЅР°Р№РґРµРЅР°"
            )
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
        """РЎРїРёСЃРѕРє Р°СЂРµРЅРґ СЃ С„РёР»СЊС‚СЂР°РјРё."""
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
            query.order_by(Rental.created_at.desc()).offset(offset).limit(limit).all()
        )

    @staticmethod
    def update_rental(
        db: Session,
        rental_id: int,
        data: RentalUpdate,
        company_id: int,
    ) -> Rental:
        """РћР±РЅРѕРІРёС‚СЊ Р°СЂРµРЅРґСѓ (С‚РѕР»СЊРєРѕ РІ DRAFT)."""
        rental = RentalService.get_rental(db, rental_id, [company_id])

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"РќРµР»СЊР·СЏ СЂРµРґР°РєС‚РёСЂРѕРІР°С‚СЊ Р°СЂРµРЅРґСѓ РІ СЃС‚Р°С‚СѓСЃРµ {rental.status.value}",
            )

        # РћР±РЅРѕРІР»СЏРµРј РїРѕР»СЏ, РµСЃР»Рё РїРµСЂРµРґР°РЅС‹
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

        # Р’Р°Р»РёРґР°С†РёСЏ РґР°С‚
        if rental.start_date >= rental.end_date:
            raise HTTPException(
                status_code=400,
                detail="Р”Р°С‚Р° РЅР°С‡Р°Р»Р° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ СЂР°РЅСЊС€Рµ РґР°С‚С‹ РѕРєРѕРЅС‡Р°РЅРёСЏ",
            )

        # РџРµСЂРµСЃС‡С‘С‚ СЃС‚РѕРёРјРѕСЃС‚Рё
        rental.base_price = RentalService._calculate_plan_amount(rental)
        rental.total_amount = max(
            rental.base_price - (rental.discount or Decimal("0")),
            Decimal("0"),
        )

        db.commit()
        db.refresh(rental)
        return rental

    # =====================================================================
    # РЈРїСЂР°РІР»РµРЅРёРµ РїРѕР·РёС†РёСЏРјРё
    # =====================================================================

    @staticmethod
    def add_rental_item(
        db: Session,
        rental_id: int,
        item_in: RentalItemAdd,
        company_id: int,
    ) -> RentalItem:
        """Р”РѕР±Р°РІРёС‚СЊ С‚РµС…РЅРёРєСѓ РІ Р°СЂРµРЅРґСѓ (С‚РѕР»СЊРєРѕ РІ DRAFT)."""
        rental = RentalService.get_rental(db, rental_id, [company_id])

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="РќРµР»СЊР·СЏ РґРѕР±Р°РІР»СЏС‚СЊ РїРѕР·РёС†РёРё РІ Р°РєС‚РёРІРЅСѓСЋ Р°СЂРµРЅРґСѓ",
            )

        # РџСЂРѕРІРµСЂРєР° РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё
        if not RentalService._check_vehicle_availability(
            db,
            item_in.vehicle_id,
            rental.start_date,
            rental.end_date,
            exclude_rental_id=rental.id,
        ):
            raise HTTPException(
                status_code=409,
                detail=f"РўРµС…РЅРёРєР° {item_in.vehicle_id} СѓР¶Рµ Р·Р°Р±СЂРѕРЅРёСЂРѕРІР°РЅР° РЅР° СЌС‚Рё РґР°С‚С‹",
            )

        item = RentalItem(
            rental_id=rental.id,
            vehicle_id=item_in.vehicle_id,
            quantity=item_in.quantity or 1,
            unit_price=item_in.unit_price,
        )
        db.add(item)
        db.flush()

        # РџРµСЂРµСЃС‡С‘С‚
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
        """РЈРґР°Р»РёС‚СЊ РїРѕР·РёС†РёСЋ РёР· Р°СЂРµРЅРґС‹ (С‚РѕР»СЊРєРѕ РІ DRAFT)."""
        rental = RentalService.get_rental(db, rental_id, [company_id])

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="РќРµР»СЊР·СЏ СѓРґР°Р»СЏС‚СЊ РїРѕР·РёС†РёРё РёР· Р°РєС‚РёРІРЅРѕР№ Р°СЂРµРЅРґС‹",
            )

        item = next((i for i in rental.items if i.id == item_id), None)
        if not item:
            raise HTTPException(
                status_code=404, detail="РџРѕР·РёС†РёСЏ РЅРµ РЅР°Р№РґРµРЅР°"
            )

        db.delete(item)
        db.flush()

        # РџРµСЂРµСЃС‡С‘С‚
        rental.base_price = RentalService._calculate_plan_amount(rental)
        rental.total_amount = max(
            rental.base_price - (rental.discount or Decimal("0")),
            Decimal("0"),
        )

        db.commit()

    # =====================================================================
    # РЈРїСЂР°РІР»РµРЅРёРµ СЃС‚Р°С‚СѓСЃР°РјРё (Workflow)
    # =====================================================================

    @staticmethod
    def activate_rental(db: Session, rental_id: int, company_id: int) -> Rental:
        """РђРєС‚РёРІРёСЂРѕРІР°С‚СЊ Р°СЂРµРЅРґСѓ (DRAFT в†’ ACTIVE). РўРµС…РЅРёРєР° РІС‹РґР°РЅР°."""
        rental = RentalService.get_rental(db, rental_id, [company_id])

        if rental.status != RentalStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"РќРµР»СЊР·СЏ Р°РєС‚РёРІРёСЂРѕРІР°С‚СЊ Р°СЂРµРЅРґСѓ РІ СЃС‚Р°С‚СѓСЃРµ {rental.status.value}",
            )

        if not rental.items:
            raise HTTPException(
                status_code=400,
                detail="РќРµР»СЊР·СЏ Р°РєС‚РёРІРёСЂРѕРІР°С‚СЊ Р°СЂРµРЅРґСѓ Р±РµР· РїРѕР·РёС†РёР№",
            )

        # РџСЂРѕРІРµСЂРєР° РїСЂРµРґРѕРїР»Р°С‚С‹
        if (
            rental.prepayment_status == PrepaymentStatus.REQUIRED
            and not rental.prepayment_paid_at
        ):
            raise HTTPException(
                status_code=400,
                detail="РўСЂРµР±СѓРµС‚СЃСЏ РїСЂРµРґРѕРїР»Р°С‚Р° РїРµСЂРµРґ Р°РєС‚РёРІР°С†РёРµР№",
            )

        rental.status = RentalStatus.ACTIVE
        db.commit()
        db.refresh(rental)

        logger.info("Rental #%s activated", rental.id)
        return rental

    @staticmethod
    def cancel_rental(db: Session, rental_id: int, company_id: int) -> Rental:
        """РћС‚РјРµРЅРёС‚СЊ Р°СЂРµРЅРґСѓ (DRAFT/ACTIVE в†’ CANCELLED)."""
        rental = RentalService.get_rental(db, rental_id, [company_id])

        if rental.status not in [RentalStatus.DRAFT, RentalStatus.ACTIVE]:
            raise HTTPException(
                status_code=400,
                detail=f"РќРµР»СЊР·СЏ РѕС‚РјРµРЅРёС‚СЊ Р°СЂРµРЅРґСѓ РІ СЃС‚Р°С‚СѓСЃРµ {rental.status.value}",
            )

        rental.status = RentalStatus.CANCELLED

        # Р’РѕР·РІСЂР°С‚ РїСЂРµРґРѕРїР»Р°С‚С‹, РµСЃР»Рё Р±С‹Р»Р°
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
        Р—Р°РІРµСЂС€РёС‚СЊ Р°СЂРµРЅРґСѓ (ACTIVE в†’ COMPLETED).
        РџСЂРёРЅРёРјР°РµС‚ С„Р°РєС‚РёС‡РµСЃРєРёРµ РґР°РЅРЅС‹Рµ, РїРµСЂРµСЃС‡РёС‚С‹РІР°РµС‚ СЃС‚РѕРёРјРѕСЃС‚СЊ Рё СЃРѕР·РґР°С‘С‚ Invoice.
        """
        rental = RentalService.get_rental(db, rental_id, [company_id])

        if rental.status != RentalStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail=f"РќРµР»СЊР·СЏ Р·Р°РІРµСЂС€РёС‚СЊ Р°СЂРµРЅРґСѓ РІ СЃС‚Р°С‚СѓСЃРµ {rental.status.value}",
            )

        # РќРѕСЂРјР°Р»РёР·СѓРµРј actual_return_date
        actual_return_dt = data.actual_return_date or datetime.now(UTC)
        if actual_return_dt.tzinfo is None:
            actual_return_dt = actual_return_dt.replace(tzinfo=UTC)
        rental.actual_return_date = actual_return_dt

        # РќРѕСЂРјР°Р»РёР·СѓРµРј end_date РґР»СЏ Р±РµР·РѕРїР°СЃРЅРѕРіРѕ СЃСЂР°РІРЅРµРЅРёСЏ
        end_date_norm = rental.end_date
        if end_date_norm.tzinfo is None:
            end_date_norm = end_date_norm.replace(tzinfo=UTC)

        # РћР±РЅРѕРІР»СЏРµРј С„Р°РєС‚РёС‡РµСЃРєРёРµ РґР°РЅРЅС‹Рµ РїРѕ РїРѕР·РёС†РёСЏРј
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

        # РџРµСЂРµСЃС‡С‘С‚ РїРѕ С„Р°РєС‚Сѓ
        actual_amount = RentalService._calculate_actual_amount(rental)

        # РЁС‚СЂР°С„ Р·Р° РїСЂРѕСЃСЂРѕС‡РєСѓ (СЃСЂР°РІРЅРёРІР°РµРј РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Рµ РґР°С‚С‹!)
        overdue_penalty = Decimal("0")
        if rental.actual_return_date > end_date_norm:
            overdue_hours = RentalService._calculate_duration_hours(
                end_date_norm, rental.actual_return_date
            )
            # РЁС‚СЂР°С„ = 150% РѕС‚ С‡Р°СЃРѕРІРѕР№ СЃС‚Р°РІРєРё Р·Р° РєР°Р¶РґС‹Р№ С‡Р°СЃ РїСЂРѕСЃСЂРѕС‡РєРё
            penalty_rate = Decimal("1.5")
            for item in rental.items:
                hourly_price = Decimal(str(item.unit_price or 0))
                qty = Decimal(str(item.quantity or 1))
                overdue_penalty += overdue_hours * hourly_price * qty * penalty_rate
            overdue_penalty = overdue_penalty.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Р¤РёРЅР°Р»СЊРЅР°СЏ СЃСѓРјРјР° = С„Р°РєС‚ + С€С‚СЂР°С„ - СЃРєРёРґРєР°
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
            rental.id,
            actual_amount,
            overdue_penalty,
            rental.total_amount,
        )

        # рџ†• РђРІС‚РѕСЃРѕР·РґР°РЅРёРµ Invoice РїСЂРё Р·Р°РІРµСЂС€РµРЅРёРё Р°СЂРµРЅРґС‹
        try:
            RentalService._create_documents_from_rental(db, rental)
        except Exception as e:
            # Р›РѕРіРёСЂСѓРµРј РѕС€РёР±РєСѓ, РЅРѕ РЅРµ РїСЂРµСЂС‹РІР°РµРј Р·Р°РІРµСЂС€РµРЅРёРµ Р°СЂРµРЅРґС‹
            logger.error(
                "Failed to auto-create documents for Rental #%s: %s",
                rental.id,
                str(e),
                exc_info=True,
            )

        return rental

    @staticmethod
    def _create_documents_from_rental(db: Session, rental: Rental) -> tuple:
        """
        РЎРѕР·РґР°С‘С‚ РїРѕР»РЅС‹Р№ РїР°РєРµС‚ РґРѕРєСѓРјРµРЅС‚РѕРІ РїСЂРё Р·Р°РІРµСЂС€РµРЅРёРё Р°СЂРµРЅРґС‹:
        - Invoice (СЃС‡С‘С‚ РєР»РёРµРЅС‚Сѓ)
        - Act (Р°РєС‚ РІС‹РїРѕР»РЅРµРЅРЅС‹С… СЂР°Р±РѕС‚)
        - Payout(s) (РІС‹РїР»Р°С‚С‹ СЃРѕР±СЃС‚РІРµРЅРЅРёРєР°Рј С‚РµС…РЅРёРєРё)

        РўР°РєР¶Рµ РѕС‚РїСЂР°РІР»СЏРµС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ РїРѕ РІСЃРµРј РєР°РЅР°Р»Р°Рј.
        """
        invoice = RentalService._create_invoice_from_rental(db, rental)
        act = RentalService._create_act_from_rental(db, rental, invoice)
        payouts = RentalService._create_payouts_from_rental(db, rental)

        # рџ†• РћС‚РїСЂР°РІР»СЏРµРј СѓРІРµРґРѕРјР»РµРЅРёСЏ Р°СЃРёРЅС…СЂРѕРЅРЅРѕ
        RentalService._send_rental_notifications(db, rental, invoice, payouts)

        return invoice, act, payouts

    @staticmethod
    def _create_invoice_from_rental(db: Session, rental: Rental) -> "Invoice":
        """РЎРѕР·РґР°С‘С‚ Invoice РЅР° РѕСЃРЅРѕРІРµ Р·Р°РІРµСЂС€С‘РЅРЅРѕР№ Р°СЂРµРЅРґС‹."""
        from datetime import date, timedelta

        from app.core.constants import TaxSystem
        from app.models.finance import DocumentStatus, Invoice, InvoiceItem
        from app.services.finance_service import generate_document_number

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
            comment=f"РђРІС‚РѕСЃРѕР·РґР°РЅ РїСЂРё Р·Р°РІРµСЂС€РµРЅРёРё Р°СЂРµРЅРґС‹ #{rental.id}",
        )
        db.add(invoice)
        db.flush()

        rate_type_desc = {
            RateType.HOURLY: "РђСЂРµРЅРґР° С‚РµС…РЅРёРєРё (РїРѕС‡Р°СЃРѕРІР°СЏ)",
            RateType.SHIFT: "РђСЂРµРЅРґР° С‚РµС…РЅРёРєРё (РїРѕСЃРјРµРЅРЅР°СЏ)",
            RateType.TRIP: "РђСЂРµРЅРґР° С‚РµС…РЅРёРєРё (Р·Р° С…РѕРґРєСѓ)",
            RateType.VOLUME: "РђСЂРµРЅРґР° С‚РµС…РЅРёРєРё (Р·Р° РѕР±СЉС‘Рј)",
            RateType.MILEAGE: "РђСЂРµРЅРґР° С‚РµС…РЅРёРєРё (РїРѕ РїСЂРѕР±РµРіСѓ)",
            RateType.COMBINED: "РђСЂРµРЅРґР° С‚РµС…РЅРёРєРё (РєРѕРјР±РёРЅРёСЂРѕРІР°РЅРЅР°СЏ)",
        }
        description = rate_type_desc.get(
            rental.rate_type, "РђСЂРµРЅРґР° С‚РµС…РЅРёРєРё"
        )

        unit_map = {
            RateType.HOURLY: "РјРѕС‚РѕС‡Р°СЃ",
            RateType.SHIFT: "СЃРјРµРЅР°",
            RateType.TRIP: "С…РѕРґРєР°",
            RateType.VOLUME: "РјВі",
            RateType.MILEAGE: "РєРј",
            RateType.COMBINED: "СѓСЃР».",
        }
        unit = unit_map.get(rental.rate_type, "СѓСЃР».")

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            description=f"{description} (Р”РѕРіРѕРІРѕСЂ Р°СЂРµРЅРґС‹ #{rental.id})",
            quantity=Decimal("1"),
            unit=unit,
            unit_price=rental.total_amount,
            amount=rental.total_amount,
        )
        db.add(invoice_item)
        db.flush()

        logger.info(
            "Auto-created Invoice #%s (%s) for Rental #%s: total=%s",
            invoice.id,
            invoice.document_number,
            rental.id,
            total,
        )
        return invoice

    @staticmethod
    def _create_act_from_rental(
        db: Session, rental: Rental, invoice: "Invoice"
    ) -> "Act":
        """РЎРѕР·РґР°С‘С‚ Act РЅР° РѕСЃРЅРѕРІРµ Р·Р°РІРµСЂС€С‘РЅРЅРѕР№ Р°СЂРµРЅРґС‹."""
        from datetime import date

        from app.core.constants import TaxSystem
        from app.models.finance import Act, DocumentStatus
        from app.services.finance_service import generate_document_number

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
            comment=f"РђРІС‚РѕСЃРѕР·РґР°РЅ РїСЂРё Р·Р°РІРµСЂС€РµРЅРёРё Р°СЂРµРЅРґС‹ #{rental.id}",
        )
        db.add(act)
        db.flush()

        logger.info(
            "Auto-created Act #%s (%s) for Rental #%s: total=%s",
            act.id,
            act.document_number,
            rental.id,
            act.total_amount,
        )
        return act

    @staticmethod
    def _create_payouts_from_rental(db: Session, rental: Rental) -> list:
        """РЎРѕР·РґР°С‘С‚ Payout РґР»СЏ РєР°Р¶РґРѕРіРѕ СЃРѕР±СЃС‚РІРµРЅРЅРёРєР° С‚РµС…РЅРёРєРё РІ Р°СЂРµРЅРґРµ."""
        from collections import defaultdict
        from datetime import date

        from app.models.catalog import Vehicle
        from app.models.finance import DocumentStatus, Payout
        from app.services.finance_service import generate_document_number

        total_items_cost = Decimal("0")
        for item in rental.items:
            item_cost = Decimal(str(item.unit_price or 0)) * Decimal(
                str(item.quantity or 1)
            )
            total_items_cost += item_cost

        if total_items_cost == Decimal("0"):
            logger.warning(f"Rental #{rental.id} has zero total, skipping payouts")
            return []

        owner_data: dict[int, dict[str, object]] = defaultdict(
            lambda: {
                "gross": Decimal("0"),
                "vehicle_ids": [],
            }
        )

        total_rental_amount = rental.total_amount

        for item in rental.items:
            vehicle = db.get(Vehicle, item.vehicle_id)
            if not vehicle:
                logger.warning(f"Vehicle {item.vehicle_id} not found, skipping")
                continue

            if not vehicle.owner_id:
                logger.warning(
                    f"Vehicle {item.vehicle_id} has no owner, skipping payout"
                )
                continue

            item_cost = Decimal(str(item.unit_price or 0)) * Decimal(
                str(item.quantity or 1)
            )
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
                    "formula": f"gross Г— {commission_rate}% commission",
                    "gross_amount": str(gross_amount),
                    "commission_rate": str(commission_rate),
                    "commission": str(commission),
                    "net_amount": str(net_amount),
                    "vehicle_ids": data["vehicle_ids"],
                },
                comment=f"РђРІС‚РѕСЃРѕР·РґР°РЅ РїСЂРё Р·Р°РІРµСЂС€РµРЅРёРё Р°СЂРµРЅРґС‹ #{rental.id}",
            )
            db.add(payout)
            payouts.append(payout)

        if payouts:
            db.commit()
            for p in payouts:
                db.refresh(p)

            logger.info(
                "Auto-created %d Payout(s) for Rental #%s (commission_rate=%s%%)",
                len(payouts),
                rental.id,
                commission_rate,
            )

        return payouts

    @staticmethod
    def _send_rental_notifications(
        db: Session, rental: Rental, invoice, payouts: list
    ) -> None:
        """РћС‚РїСЂР°РІР»СЏРµС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ Рѕ Р·Р°РІРµСЂС€РµРЅРёРё Р°СЂРµРЅРґС‹."""
        try:
            from app.models.contractor import Contractor
            from app.services.notification_dispatcher import notification_dispatcher

            # РџРѕР»СѓС‡Р°РµРј email РєР»РёРµРЅС‚Р°
            client = db.get(Contractor, rental.client_id)
            if not client:
                logger.warning(f"Client {rental.client_id} not found for notifications")
                return

            # Р’ СЂРµР°Р»СЊРЅРѕР№ СЃРёСЃС‚РµРјРµ email РЅСѓР¶РЅРѕ Р±СЂР°С‚СЊ РёР· СЃРІСЏР·Р°РЅРЅРѕРіРѕ User РёР»Рё contact_email
            # РџРѕРєР° РёСЃРїРѕР»СЊР·СѓРµРј Р·Р°РіР»СѓС€РєСѓ
            client_email = (
                getattr(client, "email", None) or f"client_{client.id}@spectech.dev"
            )
            client_name = client.name

            # РџРѕР»СѓС‡Р°РµРј client_user_id (РµСЃР»Рё РµСЃС‚СЊ СЃРІСЏР·СЊ contractor -> user)
            client_user_id = getattr(client, "user_id", None)

            # РђСЃРёРЅС…СЂРѕРЅРЅРѕ РѕС‚РїСЂР°РІР»СЏРµРј СѓРІРµРґРѕРјР»РµРЅРёСЏ РєР»РёРµРЅС‚Сѓ
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                # Р’ event loop вЂ” СЃРѕР·РґР°С‘Рј Р·Р°РґР°С‡Сѓ
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
                # РќРµС‚ event loop вЂ” РїСЂРѕРїСѓСЃРєР°РµРј (Р±СѓРґРµС‚ РѕС‚РїСЂР°РІР»РµРЅРѕ РїРѕР·Р¶Рµ)
                logger.info("No event loop, skipping async notifications")

            # РЈРІРµРґРѕРјР»РµРЅРёСЏ СЃРѕР±СЃС‚РІРµРЅРЅРёРєР°Рј (РїРѕ РєР°Р¶РґРѕРјСѓ payout)
            for payout in payouts:
                owner = db.get(Contractor, payout.owner_id)
                if not owner:
                    continue

                owner_email = (
                    getattr(owner, "email", None) or f"owner_{owner.id}@spectech.dev"
                )
                owner_name = owner.name
                owner_user_id = getattr(owner, "user_id", None)

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
            # РќРµ Р»РѕРјР°РµРј РѕСЃРЅРѕРІРЅРѕР№ РїСЂРѕС†РµСЃСЃ РїСЂРё РѕС€РёР±РєРµ СѓРІРµРґРѕРјР»РµРЅРёР№
            logger.error(f"Failed to send rental notifications: {e}", exc_info=True)


rental_service = RentalService()
