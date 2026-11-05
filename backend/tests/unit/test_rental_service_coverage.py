"""Coverage tests for rental_service."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_rental(rate_type="HOURLY", items=None, **kwargs):
    from app.models.rental import RateType as RT
    rt_map = {
        "HOURLY": RT.HOURLY, "SHIFT": RT.SHIFT, "TRIP": RT.TRIP,
        "VOLUME": RT.VOLUME, "MILEAGE": RT.MILEAGE, "COMBINED": RT.COMBINED,
    }
    rt_enum = rt_map.get(rate_type, RT.HOURLY) if isinstance(rate_type, str) else rate_type
    defaults = {
        "id": 1, "client_id": 10, "company_id": 7, "status": "draft",
        "rate_type": rt_enum,
        "start_date": datetime(2026, 11, 1, tzinfo=UTC),
        "end_date": datetime(2026, 11, 2, tzinfo=UTC),
        "actual_return_date": None,
        "discount": Decimal("0"), "mileage_rate": None,
        "items": items or [],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_item(unit_price=1000, quantity=1, **kwargs):
    defaults = {
        "vehicle_id": 1, "unit_price": unit_price, "quantity": quantity,
        "actual_moto_hours": None, "actual_trips": None,
        "actual_volume": None, "actual_mileage": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestCalculateDurationHours:
    """Cover _calculate_duration_hours (lines 39-49)."""

    def test_normal(self):
        from app.services.rental_service import RentalService
        start = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
        end = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
        result = RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("10.00")

    def test_min_hours(self):
        from app.services.rental_service import RentalService
        start = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
        end = datetime(2026, 11, 1, 0, 10, tzinfo=UTC)  # 10 min < 0.5h
        result = RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("0.50")

    def test_none_dates(self):
        from app.services.rental_service import RentalService
        assert RentalService._calculate_duration_hours(None, None) == Decimal("0")

    def test_naive_dates(self):
        from app.services.rental_service import RentalService
        start = datetime(2026, 11, 1, 0, 0)
        end = datetime(2026, 11, 1, 8, 0)
        result = RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("8.00")


class TestCalculateDays:
    """Cover _calculate_days (lines 51-57)."""

    def test_one_shift(self):
        from app.services.rental_service import RentalService
        start = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
        end = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        result = RentalService._calculate_days(start, end)
        assert result == Decimal("1")

    def test_two_shifts(self):
        from app.services.rental_service import RentalService
        start = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
        end = datetime(2026, 11, 2, 1, 0, tzinfo=UTC)  # 25h -> 3 shifts
        result = RentalService._calculate_days(start, end)
        assert result >= Decimal("2")


class TestCalculatePlanAmount:
    """Cover _calculate_plan_amount (lines 59-101)."""

    def test_hourly(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=1000)
        rental = _make_rental("HOURLY", items=[item])
        result = RentalService._calculate_plan_amount(rental)
        # 24h * 1000 = 24000
        assert result == Decimal("24000.00")

    def test_shift(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=5000)
        rental = _make_rental("SHIFT", items=[item])
        result = RentalService._calculate_plan_amount(rental)
        assert result > Decimal("0")

    def test_trip(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=3000)
        rental = _make_rental("TRIP", items=[item])
        result = RentalService._calculate_plan_amount(rental)
        assert result == Decimal("3000.00")

    def test_volume(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=2000)
        rental = _make_rental("VOLUME", items=[item])
        result = RentalService._calculate_plan_amount(rental)
        assert result == Decimal("2000.00")

    def test_mileage(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=1500)
        rental = _make_rental("MILEAGE", items=[item])
        result = RentalService._calculate_plan_amount(rental)
        assert result == Decimal("1500.00")

    def test_combined(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=1000)
        rental = _make_rental("COMBINED", items=[item])
        result = RentalService._calculate_plan_amount(rental)
        assert result > Decimal("0")


class TestCalculateActualAmount:
    """Cover _calculate_actual_amount (lines 103-161)."""

    def test_hourly_with_actual(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=1000, actual_moto_hours=5)
        rental = _make_rental("HOURLY", items=[item])
        result = RentalService._calculate_actual_amount(rental)
        assert result == Decimal("5000.00")

    def test_hourly_fallback_to_duration(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=1000, actual_moto_hours=0)
        rental = _make_rental("HOURLY", items=[item])
        result = RentalService._calculate_actual_amount(rental)
        assert result > Decimal("0")

    def test_trip(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=3000, actual_trips=3)
        rental = _make_rental("TRIP", items=[item])
        result = RentalService._calculate_actual_amount(rental)
        assert result == Decimal("9000.00")

    def test_volume(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=200, actual_volume=50)
        rental = _make_rental("VOLUME", items=[item])
        result = RentalService._calculate_actual_amount(rental)
        assert result == Decimal("10000.00")

    def test_mileage(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=10, actual_mileage=500)
        rental = _make_rental("MILEAGE", items=[item])
        result = RentalService._calculate_actual_amount(rental)
        assert result == Decimal("5000.00")

    def test_combined(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=1000, actual_moto_hours=5, actual_mileage=100)
        rental = _make_rental("COMBINED", items=[item], mileage_rate=10)
        result = RentalService._calculate_actual_amount(rental)
        # hourly: 5*1000=5000 + mileage: 100*10=1000 = 6000
        assert result == Decimal("6000.00")

    def test_shift(self):
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=5000)
        rental = _make_rental("SHIFT", items=[item])
        result = RentalService._calculate_actual_amount(rental)
        assert result > Decimal("0")


class TestCheckVehicleAvailability:
    """Cover _check_vehicle_availability (lines 163-194)."""

    def test_available(self, mock_db):
        from app.services.rental_service import RentalService
        q = MagicMock()
        q.join.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = q
        result = RentalService._check_vehicle_availability(
            mock_db, 1, datetime.now(UTC), datetime.now(UTC) + timedelta(days=1),
        )
        assert result is True

    def test_not_available(self, mock_db):
        from app.services.rental_service import RentalService
        q = MagicMock()
        q.join.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
        mock_db.query.return_value = q
        result = RentalService._check_vehicle_availability(
            mock_db, 1, datetime.now(UTC), datetime.now(UTC) + timedelta(days=1),
        )
        assert result is False

    def test_with_exclude(self, mock_db):
        from app.services.rental_service import RentalService
        q = MagicMock()
        q.join.return_value.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = q
        result = RentalService._check_vehicle_availability(
            mock_db, 1, datetime.now(UTC), datetime.now(UTC) + timedelta(days=1),
            exclude_rental_id=5,
        )
        assert result is True


class TestGetRental:
    """Cover get_rental (lines 278-291)."""

    def test_found(self, mock_db):
        from app.services.rental_service import RentalService
        rental = SimpleNamespace(id=1)
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q
        result = RentalService.get_rental(mock_db, 1, [7])
        assert result.id == 1

    def test_not_found_raises(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = q
        with pytest.raises(HTTPException) as exc_info:
            RentalService.get_rental(mock_db, 999, [7])
        assert exc_info.value.status_code == 404



class TestListRentals:
    """Cover list_rentals (lines 293-315)."""

    def test_basic(self, mock_db):
        from app.services.rental_service import RentalService
        rental = SimpleNamespace(id=1)
        q = MagicMock()
        q.options.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = [rental]
        mock_db.query.return_value = q
        result = RentalService.list_rentals(mock_db, [7])
        assert len(result) == 1

    def test_with_filters(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService
        q = MagicMock()
        q.options.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []
        mock_db.query.return_value = q
        result = RentalService.list_rentals(mock_db, [7], status=RentalStatus.ACTIVE, client_id=10)
        assert result == []


class TestUpdateRental:
    """Cover update_rental (lines 317-367)."""

    def test_success(self, mock_db):
        from app.schemas.rental import RentalUpdate
        from app.services.rental_service import RentalService
        rental = _make_rental("HOURLY")
        rental.comment = "old"
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q

        update_data = RentalUpdate(comment="new comment")
        result = RentalService.update_rental(mock_db, 1, [7], update_data)
        assert result.comment == "new comment"
        mock_db.commit.assert_called()

    def test_not_found_raises(self, mock_db):
        from fastapi import HTTPException

        from app.schemas.rental import RentalUpdate
        from app.services.rental_service import RentalService
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = q
        with pytest.raises(HTTPException) as exc_info:
            RentalService.update_rental(mock_db, 999, [7], RentalUpdate())
        assert exc_info.value.status_code == 404


class TestActivateRental:
    """Cover activate_rental (lines 456-488)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService
        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.DRAFT
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q

        result = RentalService.activate_rental(mock_db, 1, 7)
        assert result.status == RentalStatus.ACTIVE
        mock_db.commit.assert_called()

    def test_wrong_status_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService
        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.CLOSED
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q
        with pytest.raises(HTTPException):
            RentalService.activate_rental(mock_db, 1, 7)


class TestCancelRental:
    """Cover cancel_rental (lines 490-511)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService
        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.DRAFT
        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q

        result = RentalService.cancel_rental(mock_db, 1, 7)
        assert result.status == RentalStatus.CANCELLED
        mock_db.commit.assert_called()


class TestCloseRental:
    """Cover close_rental (lines 513-608)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalClose
        from app.services.rental_service import RentalService
        item = _make_item(unit_price=1000, actual_moto_hours=8)
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.ACTIVE
        rental.actual_return_date = None

        q = MagicMock()
        q.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q

        close_data = RentalClose(actual_return_date=datetime(2026, 11, 2, tzinfo=UTC))

        with patch.object(RentalService, "_create_documents_from_rental", return_value=(None, None)), \
             patch.object(RentalService, "_create_payouts_from_rental", return_value=[]), \
             patch.object(RentalService, "_send_rental_notifications", return_value=None):
            result = RentalService.close_rental(mock_db, 1, 7, close_data)

        assert result.status == RentalStatus.CLOSED
        mock_db.commit.assert_called()


class TestAddRentalItem:
    """Cover add_rental_item (lines 369-416)."""

    def test_success(self, mock_db):
        from app.schemas.rental import RentalItemAdd
        from app.services.rental_service import RentalService
        rental = _make_rental("HOURLY")
        rental.status = SimpleNamespace(value="draft")

        q_rental = MagicMock()
        q_rental.options.return_value.filter.return_value.first.return_value = rental
        q_avail = MagicMock()
        q_avail.join.return_value.filter.return_value.first.return_value = None

        call_count = {"n": 0}
        def mock_query(model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return q_rental
            return q_avail

        mock_db.query.side_effect = mock_query

        item_in = RentalItemAdd(vehicle_id=2, unit_price=2000, quantity=1)
        RentalService.add_rental_item(mock_db, 1, [7], item_in)
        mock_db.add.assert_called()
        mock_db.commit.assert_called()


class TestRemoveRentalItem:
    """Cover remove_rental_item (lines 418-454)."""

    def test_success(self, mock_db):
        from app.services.rental_service import RentalService
        rental = _make_rental("HOURLY")
        rental.status = SimpleNamespace(value="draft")
        item = SimpleNamespace(id=5, rental_id=1)
        rental.items = [item]

        q_rental = MagicMock()
        q_rental.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q_rental

        RentalService.remove_rental_item(mock_db, 1, [7], 5)
        mock_db.delete.assert_called()
        mock_db.commit.assert_called()

    def test_item_not_found_raises(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService
        rental = _make_rental("HOURLY")
        rental.status = SimpleNamespace(value="draft")
        rental.items = []

        q_rental = MagicMock()
        q_rental.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = q_rental

        with pytest.raises(HTTPException):
            RentalService.remove_rental_item(mock_db, 1, [7], 999)
