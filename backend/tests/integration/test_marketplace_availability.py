"""PR-2: календарь доступности фильтрует аренду через RentalItem.vehicle_id.

У Rental нет vehicle_id (техника в RentalItem). Прежний код читал фантомное
Rental.vehicle_id под hasattr-guard и грузил все аренды компании. Фильтр через
фактическую связь items не теряет технику и не блокирует её чужими арендами.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.services.marketplace_service import marketplace_service


def _rental(db_session, company, client, vehicle, start, end, status):
    from app.models.rental import (
        PrepaymentStatus,
        RateType,
        Rental,
        RentalItem,
    )

    rental = Rental(
        client_id=client.id,
        company_id=company.id,
        status=status,
        start_date=start,
        end_date=end,
        rate_type=RateType.HOURLY,
        prepayment_status=PrepaymentStatus.NONE,
        base_price=Decimal("1000"),
        total_amount=Decimal("1000"),
    )
    db_session.add(rental)
    db_session.flush()
    item = RentalItem(
        rental_id=rental.id,
        vehicle_id=vehicle.id,
        quantity=1,
        unit_price=Decimal("1000"),
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(rental)
    return rental


def test_calendar_marks_vehicle_busy(
    db_session, company, sample_contractor, sample_vehicle
):
    from app.models.rental import RentalStatus

    start = datetime.now(UTC) + timedelta(days=1)
    end = datetime.now(UTC) + timedelta(days=3)
    rental = _rental(
        db_session,
        company,
        sample_contractor,
        sample_vehicle,
        start,
        end,
        RentalStatus.ACTIVE,
    )
    cal = marketplace_service.get_availability_calendar(
        db_session, sample_vehicle.id, start.date(), end.date()
    )
    busy = [d for d in cal if not d["available"]]
    assert busy, "техника не помечена занятой своей арендой"
    assert all(d["rental_id"] == rental.id for d in busy)


def test_other_vehicle_rental_does_not_block(
    db_session, company, sample_contractor, sample_vehicle
):
    from app.models.catalog import Vehicle
    from app.models.rental import RentalStatus

    other = Vehicle(
        name="Чужая техника",
        company_id=company.id,
        status="free",
        id_type="internal",
        id_value="MKT-OTHER-1",
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    start = datetime.now(UTC) + timedelta(days=1)
    end = datetime.now(UTC) + timedelta(days=3)
    _rental(
        db_session,
        company,
        sample_contractor,
        other,
        start,
        end,
        RentalStatus.ACTIVE,
    )
    cal = marketplace_service.get_availability_calendar(
        db_session, sample_vehicle.id, start.date(), end.date()
    )
    assert all(
        d["available"] for d in cal
    ), "чужая аренда не должна блокировать технику"


def test_no_rental_all_available(db_session, company, sample_vehicle):
    start = datetime.now(UTC).date() + timedelta(days=1)
    end = start + timedelta(days=5)
    cal = marketplace_service.get_availability_calendar(
        db_session, sample_vehicle.id, start, end
    )
    assert cal and all(d["available"] for d in cal)
