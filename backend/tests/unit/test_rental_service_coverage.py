"""Coverage tests for rental_service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_rental(rate_type="HOURLY", items=None, **kwargs):
    from app.models.rental import RateType as RT

    rt_map = {
        "HOURLY": RT.HOURLY,
        "SHIFT": RT.SHIFT,
        "TRIP": RT.TRIP,
        "VOLUME": RT.VOLUME,
        "MILEAGE": RT.MILEAGE,
        "COMBINED": RT.COMBINED,
    }
    rt_enum = (
        rt_map.get(rate_type, RT.HOURLY) if isinstance(rate_type, str) else rate_type
    )
    defaults = {
        "id": 1,
        "client_id": 10,
        "company_id": 7,
        "status": "draft",
        "rate_type": rt_enum,
        "start_date": datetime(2026, 11, 1, tzinfo=UTC),
        "end_date": datetime(2026, 11, 2, tzinfo=UTC),
        "actual_return_date": None,
        "discount": Decimal("0"),
        "mileage_rate": None,
        "items": items or [],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_item(unit_price=1000, quantity=1, **kwargs):
    defaults = {
        "vehicle_id": 1,
        "unit_price": unit_price,
        "quantity": quantity,
        "actual_moto_hours": None,
        "actual_trips": None,
        "actual_volume": None,
        "actual_mileage": None,
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
            mock_db,
            1,
            datetime.now(UTC),
            datetime.now(UTC) + timedelta(days=1),
        )
        assert result is True

    def test_not_available(self, mock_db):
        from app.services.rental_service import RentalService

        q = MagicMock()
        q.join.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id=1
        )
        mock_db.query.return_value = q
        result = RentalService._check_vehicle_availability(
            mock_db,
            1,
            datetime.now(UTC),
            datetime.now(UTC) + timedelta(days=1),
        )
        assert result is False

    def test_with_exclude(self, mock_db):
        from app.services.rental_service import RentalService

        q = MagicMock()
        q.join.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        mock_db.query.return_value = q
        result = RentalService._check_vehicle_availability(
            mock_db,
            1,
            datetime.now(UTC),
            datetime.now(UTC) + timedelta(days=1),
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
        # Chain: query(Rental).options(...).filter(...).order_by(...).offset(...).limit(...).all()
        q = MagicMock()
        opts = MagicMock()
        filt = MagicMock()
        ordered = MagicMock()
        offseted = MagicMock()
        limited = MagicMock()
        limited.all.return_value = [rental]
        offseted.limit.return_value = limited
        ordered.offset.return_value = offseted
        filt.order_by.return_value = ordered
        opts.filter.return_value = filt
        q.options.return_value = opts
        mock_db.query.return_value = q
        result = RentalService.list_rentals(mock_db, [7])
        assert len(result) == 1

    def test_with_status_filter(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        q = MagicMock()
        opts = MagicMock()
        filt1 = MagicMock()
        filt2 = MagicMock()
        ordered = MagicMock()
        offseted = MagicMock()
        limited = MagicMock()
        limited.all.return_value = []
        offseted.limit.return_value = limited
        ordered.offset.return_value = offseted
        filt2.order_by.return_value = ordered
        filt1.filter.return_value = filt2
        opts.filter.return_value = filt1
        q.options.return_value = opts
        mock_db.query.return_value = q
        result = RentalService.list_rentals(mock_db, [7], status=RentalStatus.ACTIVE)
        assert result == []

    def test_with_client_filter(self, mock_db):
        from app.services.rental_service import RentalService

        q = MagicMock()
        opts = MagicMock()
        filt1 = MagicMock()
        filt2 = MagicMock()
        ordered = MagicMock()
        offseted = MagicMock()
        limited = MagicMock()
        limited.all.return_value = []
        offseted.limit.return_value = limited
        ordered.offset.return_value = offseted
        filt2.order_by.return_value = ordered
        filt1.filter.return_value = filt2
        opts.filter.return_value = filt1
        q.options.return_value = opts
        mock_db.query.return_value = q
        result = RentalService.list_rentals(mock_db, [7], client_id=10)
        assert result == []


def _mock_get_rental(mock_db, rental):
    """Helper to mock get_rental query chain used by update/activate/cancel/close/add/remove."""
    q = MagicMock()
    opts = MagicMock()
    filt = MagicMock()
    filt.first.return_value = rental
    opts.filter.return_value = filt
    q.options.return_value = opts
    mock_db.query.return_value = q


class TestUpdateRental:
    """Cover update_rental (lines 317-367)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalUpdate
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000)
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.DRAFT
        rental.comment = "old"
        _mock_get_rental(mock_db, rental)

        update_data = RentalUpdate(comment="new comment")
        result = RentalService.update_rental(mock_db, 1, update_data, 7)
        assert result.comment == "new comment"
        mock_db.commit.assert_called()

    def test_not_draft_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalUpdate
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.ACTIVE
        _mock_get_rental(mock_db, rental)
        with pytest.raises(HTTPException) as exc_info:
            RentalService.update_rental(mock_db, 1, RentalUpdate(), 7)
        assert exc_info.value.status_code == 400

    def test_invalid_dates_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalUpdate
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.DRAFT
        _mock_get_rental(mock_db, rental)
        update_data = RentalUpdate(
            start_date=datetime(2026, 12, 1, tzinfo=UTC),
            end_date=datetime(2026, 11, 1, tzinfo=UTC),
        )
        with pytest.raises(HTTPException) as exc_info:
            RentalService.update_rental(mock_db, 1, update_data, 7)
        assert exc_info.value.status_code == 400


class TestActivateRental:
    """Cover activate_rental (lines 456-488)."""

    def test_success(self, mock_db):
        from app.models.rental import PrepaymentStatus, RentalStatus
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000)
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.DRAFT
        rental.prepayment_status = PrepaymentStatus.NONE
        rental.prepayment_paid_at = None
        _mock_get_rental(mock_db, rental)

        result = RentalService.activate_rental(mock_db, 1, 7)
        assert result.status == RentalStatus.ACTIVE
        mock_db.commit.assert_called()

    def test_wrong_status_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.COMPLETED
        _mock_get_rental(mock_db, rental)
        with pytest.raises(HTTPException):
            RentalService.activate_rental(mock_db, 1, 7)

    def test_no_items_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY", items=[])
        rental.status = RentalStatus.DRAFT
        _mock_get_rental(mock_db, rental)
        with pytest.raises(HTTPException):
            RentalService.activate_rental(mock_db, 1, 7)

    def test_prepayment_required_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import PrepaymentStatus, RentalStatus
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000)
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.DRAFT
        rental.prepayment_status = PrepaymentStatus.REQUIRED
        rental.prepayment_paid_at = None
        _mock_get_rental(mock_db, rental)
        with pytest.raises(HTTPException):
            RentalService.activate_rental(mock_db, 1, 7)


class TestCancelRental:
    """Cover cancel_rental (lines 490-511)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.DRAFT
        rental.prepayment_paid_at = None
        _mock_get_rental(mock_db, rental)

        result = RentalService.cancel_rental(mock_db, 1, 7)
        assert result.status == RentalStatus.CANCELLED
        mock_db.commit.assert_called()

    def test_with_prepayment_refund(self, mock_db):
        from app.models.rental import PrepaymentStatus, RentalStatus
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.ACTIVE
        rental.prepayment_paid_at = datetime.now(UTC)
        rental.prepayment_status = PrepaymentStatus.PAID
        _mock_get_rental(mock_db, rental)

        result = RentalService.cancel_rental(mock_db, 1, 7)
        assert result.prepayment_status == PrepaymentStatus.REFUNDED

    def test_wrong_status_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.COMPLETED
        _mock_get_rental(mock_db, rental)
        with pytest.raises(HTTPException):
            RentalService.cancel_rental(mock_db, 1, 7)


class TestCloseRental:
    """Cover close_rental (lines 513-608)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalClose
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000, actual_moto_hours=8)
        item.id = 1
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.ACTIVE
        rental.actual_return_date = None
        _mock_get_rental(mock_db, rental)

        close_data = RentalClose(actual_return_date=datetime(2026, 11, 2, tzinfo=UTC))

        with patch.object(
            RentalService, "_create_documents_from_rental", return_value=(None, None)
        ):
            result = RentalService.close_rental(mock_db, 1, close_data, 7)

        assert result.status == RentalStatus.COMPLETED
        mock_db.commit.assert_called()

    def test_wrong_status_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalClose
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.DRAFT
        _mock_get_rental(mock_db, rental)
        close_data = RentalClose(actual_return_date=datetime(2026, 11, 2, tzinfo=UTC))
        with pytest.raises(HTTPException):
            RentalService.close_rental(mock_db, 1, close_data, 7)

    def test_doc_creation_error_logged(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalClose
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000, actual_moto_hours=8)
        item.id = 1
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.ACTIVE
        rental.actual_return_date = None
        _mock_get_rental(mock_db, rental)

        close_data = RentalClose(actual_return_date=datetime(2026, 11, 2, tzinfo=UTC))

        with patch.object(
            RentalService,
            "_create_documents_from_rental",
            side_effect=Exception("DB fail"),
        ):
            result = RentalService.close_rental(mock_db, 1, close_data, 7)

        # Should still complete despite doc creation error
        assert result.status == RentalStatus.COMPLETED


class TestAddRentalItem:
    """Cover add_rental_item (lines 369-416)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalItemAdd
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.DRAFT
        _mock_get_rental(mock_db, rental)

        # Mock _check_vehicle_availability to return True (available)
        with patch.object(
            RentalService, "_check_vehicle_availability", return_value=True
        ):
            item_in = RentalItemAdd(vehicle_id=2, unit_price=2000, quantity=1)
            RentalService.add_rental_item(mock_db, 1, item_in, 7)

        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_not_draft_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalItemAdd
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.ACTIVE
        _mock_get_rental(mock_db, rental)
        item_in = RentalItemAdd(vehicle_id=2, unit_price=2000)
        with pytest.raises(HTTPException):
            RentalService.add_rental_item(mock_db, 1, item_in, 7)

    def test_vehicle_unavailable_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalItemAdd
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.DRAFT
        _mock_get_rental(mock_db, rental)
        with patch.object(
            RentalService, "_check_vehicle_availability", return_value=False
        ):
            item_in = RentalItemAdd(vehicle_id=2, unit_price=2000)
            with pytest.raises(HTTPException) as exc_info:
                RentalService.add_rental_item(mock_db, 1, item_in, 7)
            assert exc_info.value.status_code == 409


class TestRemoveRentalItem:
    """Cover remove_rental_item (lines 418-454)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        item = SimpleNamespace(id=5, unit_price=1000, quantity=1)
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.DRAFT
        _mock_get_rental(mock_db, rental)

        RentalService.remove_rental_item(mock_db, 1, 5, 7)
        mock_db.delete.assert_called()
        mock_db.commit.assert_called()

    def test_item_not_found_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY", items=[])
        rental.status = RentalStatus.DRAFT
        _mock_get_rental(mock_db, rental)
        with pytest.raises(HTTPException) as exc_info:
            RentalService.remove_rental_item(mock_db, 1, 999, 7)
        assert exc_info.value.status_code == 404

    def test_not_draft_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.status = RentalStatus.ACTIVE
        _mock_get_rental(mock_db, rental)
        with pytest.raises(HTTPException):
            RentalService.remove_rental_item(mock_db, 1, 5, 7)


class TestCreateRental:
    """Cover create_rental (lines 196-275)."""

    def test_success(self, mock_db):
        from app.models.rental import RateType
        from app.schemas.rental import RentalCreate, RentalItemCreate
        from app.services.rental_service import RentalService

        item_in = RentalItemCreate(vehicle_id=1, unit_price=1000, quantity=1)
        rental_in = RentalCreate(
            client_id=10,
            request_id=None,
            start_date=datetime(2026, 11, 1, tzinfo=UTC),
            end_date=datetime(2026, 11, 2, tzinfo=UTC),
            rate_type=RateType.HOURLY,
            items=[item_in],
        )

        # Mock flush to set rental.id
        call_count = {"n": 0}

        def mock_flush():
            call_count["n"] += 1

        mock_db.flush.side_effect = mock_flush
        mock_db.refresh.side_effect = lambda r: (
            setattr(r, "id", 1) if not hasattr(r, "id") or r.id is None else None
        )

        added_objects = []

        def mock_add(obj):
            added_objects.append(obj)
            if hasattr(obj, "client_id") and not hasattr(obj, "vehicle_id"):
                obj.id = 1
                obj.items = []

        mock_db.add.side_effect = mock_add
        mock_db.add_all.side_effect = lambda items: None

        with patch.object(
            RentalService, "_check_vehicle_availability", return_value=True
        ):
            result = RentalService.create_rental(mock_db, rental_in, 7, 1)

        mock_db.commit.assert_called()
        assert result is not None

    def test_invalid_dates_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RateType
        from app.schemas.rental import RentalCreate, RentalItemCreate
        from app.services.rental_service import RentalService

        item_in = RentalItemCreate(vehicle_id=1, unit_price=1000)
        rental_in = RentalCreate(
            client_id=10,
            request_id=None,
            start_date=datetime(2026, 11, 2, tzinfo=UTC),
            end_date=datetime(2026, 11, 1, tzinfo=UTC),
            rate_type=RateType.HOURLY,
            items=[item_in],
        )
        with pytest.raises(HTTPException) as exc_info:
            RentalService.create_rental(mock_db, rental_in, 7, 1)
        assert exc_info.value.status_code == 400

    def test_vehicle_unavailable_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RateType
        from app.schemas.rental import RentalCreate, RentalItemCreate
        from app.services.rental_service import RentalService

        item_in = RentalItemCreate(vehicle_id=1, unit_price=1000)
        rental_in = RentalCreate(
            client_id=10,
            request_id=None,
            start_date=datetime(2026, 11, 1, tzinfo=UTC),
            end_date=datetime(2026, 11, 2, tzinfo=UTC),
            rate_type=RateType.HOURLY,
            items=[item_in],
        )

        mock_db.flush.side_effect = lambda: None
        added = []

        def mock_add(obj):
            added.append(obj)
            if hasattr(obj, "client_id") and not hasattr(obj, "vehicle_id"):
                obj.id = 1

        mock_db.add.side_effect = mock_add

        with patch.object(
            RentalService, "_check_vehicle_availability", return_value=False
        ):
            with pytest.raises(HTTPException) as exc_info:
                RentalService.create_rental(mock_db, rental_in, 7, 1)
            assert exc_info.value.status_code == 409
        mock_db.rollback.assert_called()


class TestCreateDocumentsFromRental:
    """Cover _create_documents_from_rental (lines 610-626)."""

    def test_calls_all_sub_methods(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        invoice = SimpleNamespace(id=1)
        act = SimpleNamespace(id=2)

        with (
            patch.object(
                RentalService, "_create_invoice_from_rental", return_value=invoice
            ) as m_inv,
            patch.object(
                RentalService, "_create_act_from_rental", return_value=act
            ) as m_act,
            patch.object(
                RentalService, "_create_payouts_from_rental", return_value=[]
            ) as m_pay,
            patch.object(RentalService, "_send_rental_notifications") as m_notif,
        ):
            result = RentalService._create_documents_from_rental(mock_db, rental)

        m_inv.assert_called_once()
        m_act.assert_called_once()
        m_pay.assert_called_once()
        m_notif.assert_called_once()
        assert result == (invoice, act, [])


class TestCreateInvoiceFromRental:
    """Cover _create_invoice_from_rental (lines 629-703)."""

    def test_success(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.total_amount = Decimal("10000")
        rental.request_id = None

        added = []

        def mock_add(obj):
            added.append(obj)
            obj.id = len(added)

        mock_db.add.side_effect = mock_add
        mock_db.flush.side_effect = lambda: None

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="INV-2026-0001",
        ):
            result = RentalService._create_invoice_from_rental(mock_db, rental)

        assert result is not None
        assert mock_db.add.call_count == 2  # invoice + invoice_item


class TestCreateActFromRental:
    """Cover _create_act_from_rental (lines 706-741)."""

    def test_success(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        rental.request_id = None
        invoice = SimpleNamespace(
            total=Decimal("12000"), vat_amount=Decimal("2000"), vat_rate=Decimal("20")
        )

        added = []

        def mock_add(obj):
            added.append(obj)
            obj.id = len(added)

        mock_db.add.side_effect = mock_add
        mock_db.flush.side_effect = lambda: None

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="ACT-2026-0001",
        ):
            result = RentalService._create_act_from_rental(mock_db, rental, invoice)

        assert result is not None
        mock_db.add.assert_called_once()


class TestCreatePayoutsFromRental:
    """Cover _create_payouts_from_rental (lines 744-851)."""

    def test_zero_total_returns_empty(self, mock_db):
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=0, quantity=1)
        rental = _make_rental("HOURLY", items=[item])
        rental.commission_rate = Decimal("10")
        result = RentalService._create_payouts_from_rental(mock_db, rental)
        assert result == []

    def test_with_vehicles_and_owners(self, mock_db):
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=10000, quantity=1)
        item.vehicle_id = 1
        rental = _make_rental("HOURLY", items=[item])
        rental.total_amount = Decimal("10000")
        rental.commission_rate = Decimal("10")
        rental.request_id = None

        vehicle = SimpleNamespace(id=1, owner_id=100)
        mock_db.get.return_value = vehicle

        added = []

        def mock_add(obj):
            added.append(obj)
            obj.id = len(added)

        mock_db.add.side_effect = mock_add
        mock_db.refresh.side_effect = lambda p: None

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="PAY-2026-0001",
        ):
            result = RentalService._create_payouts_from_rental(mock_db, rental)

        assert len(result) == 1
        mock_db.commit.assert_called()

    def test_vehicle_not_found_skipped(self, mock_db):
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=10000, quantity=1)
        rental = _make_rental("HOURLY", items=[item])
        rental.total_amount = Decimal("10000")
        rental.commission_rate = Decimal("10")
        mock_db.get.return_value = None

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="PAY-2026-0001",
        ):
            result = RentalService._create_payouts_from_rental(mock_db, rental)
        assert result == []

    def test_vehicle_no_owner_skipped(self, mock_db):
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=10000, quantity=1)
        rental = _make_rental("HOURLY", items=[item])
        rental.total_amount = Decimal("10000")
        rental.commission_rate = Decimal("10")
        vehicle = SimpleNamespace(id=1, owner_id=None)
        mock_db.get.return_value = vehicle

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="PAY-2026-0001",
        ):
            result = RentalService._create_payouts_from_rental(mock_db, rental)
        assert result == []


class TestSendRentalNotifications:
    """Cover _send_rental_notifications (lines 854-end)."""

    def test_client_not_found(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        mock_db.get.return_value = None
        # Should not raise
        RentalService._send_rental_notifications(mock_db, rental, None, [])

    def test_success_no_loop(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        client = SimpleNamespace(
            id=10, name="TestClient", email="test@test.com", user_id=1
        )
        mock_db.get.return_value = client

        payout = SimpleNamespace(owner_id=100)
        owner = SimpleNamespace(id=100, name="Owner", email="owner@test.com", user_id=2)

        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return client
            return owner

        mock_db.get.side_effect = mock_get

        # No event loop - should handle gracefully
        RentalService._send_rental_notifications(mock_db, rental, None, [payout])

    def test_exception_handled(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        mock_db.get.side_effect = Exception("DB error")
        # Should not raise
        RentalService._send_rental_notifications(mock_db, rental, None, [])


class TestUpdateRentalAllFields:
    """Cover update_rental remaining fields (lines 338, 342, 344)."""

    def test_update_discount_prepayment(self, mock_db):
        from app.models.rental import PrepaymentStatus, RentalStatus
        from app.schemas.rental import RentalUpdate
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000)
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.DRAFT
        rental.discount = Decimal("0")
        rental.prepayment_status = PrepaymentStatus.NONE
        rental.prepayment_amount = None
        _mock_get_rental(mock_db, rental)

        update_data = RentalUpdate(
            discount=Decimal("500"),
            prepayment_status=PrepaymentStatus.PAID,
            prepayment_amount=Decimal("3000"),
        )
        result = RentalService.update_rental(mock_db, 1, update_data, 7)
        assert result.discount == Decimal("500")
        assert result.prepayment_status == PrepaymentStatus.PAID
        assert result.prepayment_amount == Decimal("3000")


class TestCloseRentalOverdue:
    """Cover close_rental overdue penalty and items_actuals (lines 534-572)."""

    def test_overdue_penalty(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalClose
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000, actual_moto_hours=8)
        item.id = 1
        # end_date = Nov 2, actual_return = Nov 3 -> 24h overdue
        rental = _make_rental(
            "HOURLY",
            items=[item],
            start_date=datetime(2026, 11, 1, tzinfo=UTC),
            end_date=datetime(2026, 11, 2, tzinfo=UTC),
        )
        rental.status = RentalStatus.ACTIVE
        rental.actual_return_date = None
        _mock_get_rental(mock_db, rental)

        close_data = RentalClose(actual_return_date=datetime(2026, 11, 3, tzinfo=UTC))

        with patch.object(
            RentalService, "_create_documents_from_rental", return_value=(None, None)
        ):
            result = RentalService.close_rental(mock_db, 1, close_data, 7)

        assert result.status == RentalStatus.COMPLETED
        # Should have overdue penalty > 0
        assert result.total_amount > Decimal("0")

    def test_with_items_actuals(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalClose, RentalItemActual
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000)
        item.id = 1
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.ACTIVE
        rental.actual_return_date = None
        _mock_get_rental(mock_db, rental)

        actual = RentalItemActual(
            rental_item_id=1,
            actual_moto_hours=10,
            actual_mileage=500,
            actual_trips=3,
            actual_volume=50,
        )
        close_data = RentalClose(
            actual_return_date=datetime(2026, 11, 2, tzinfo=UTC),
            items_actuals=[actual],
        )

        with patch.object(
            RentalService, "_create_documents_from_rental", return_value=(None, None)
        ):
            result = RentalService.close_rental(mock_db, 1, close_data, 7)

        assert result.status == RentalStatus.COMPLETED
        # Item should have updated actuals
        assert item.actual_moto_hours == 10
        assert item.actual_mileage == 500

    def test_naive_actual_return_date(self, mock_db):
        from app.models.rental import RentalStatus
        from app.schemas.rental import RentalClose
        from app.services.rental_service import RentalService

        item = _make_item(unit_price=1000, actual_moto_hours=8)
        item.id = 1
        rental = _make_rental("HOURLY", items=[item])
        rental.status = RentalStatus.ACTIVE
        rental.actual_return_date = None
        rental.end_date = datetime(2026, 11, 2)  # naive
        _mock_get_rental(mock_db, rental)

        close_data = RentalClose(
            actual_return_date=datetime(2026, 11, 2, 12, 0)
        )  # naive

        with patch.object(
            RentalService, "_create_documents_from_rental", return_value=(None, None)
        ):
            result = RentalService.close_rental(mock_db, 1, close_data, 7)

        assert result.status == RentalStatus.COMPLETED


class TestSendNotificationsWithLoop:
    """Cover _send_rental_notifications with event loop (lines 884, 902, 912)."""

    @pytest.mark.asyncio
    async def test_with_event_loop(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        client = SimpleNamespace(id=10, name="Client", email="c@test.com", user_id=1)
        # Owner without email -> triggers fallback on line 902
        owner = SimpleNamespace(id=100, name="Owner", email=None, user_id=2)
        payout = SimpleNamespace(owner_id=100)

        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return client
            return owner

        mock_db.get.side_effect = mock_get

        mock_dispatcher = MagicMock()
        mock_dispatcher.notify_rental_completed = AsyncMock()
        mock_dispatcher.notify_payout_created = AsyncMock()

        with patch(
            "app.services.notification_dispatcher.notification_dispatcher",
            mock_dispatcher,
        ):
            RentalService._send_rental_notifications(mock_db, rental, None, [payout])

        import asyncio

        await asyncio.sleep(0.01)


class TestSendNotificationsOwnerNotFound:
    """Cover line 902: continue when owner not found."""

    def test_payout_owner_not_found(self, mock_db):
        from app.services.rental_service import RentalService

        rental = _make_rental("HOURLY")
        client = SimpleNamespace(id=10, name="Client", email="c@test.com", user_id=1)
        payout = SimpleNamespace(owner_id=999)

        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return client
            # Owner not found for payout
            return None

        mock_db.get.side_effect = mock_get

        # Should not raise, just skip the payout notification
        RentalService._send_rental_notifications(mock_db, rental, None, [payout])
