"""Coverage tests for rental_service."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.refresh = MagicMock()
    db.delete = MagicMock()
    return db


class TestCalculateDurationHours:
    """Cover _calculate_duration_hours (lines 39-49)."""

    def test_normal(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
        end = datetime(2026, 11, 5, 16, 0, tzinfo=UTC)
        result = RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("8.00")

    def test_none_returns_zero(self):
        from app.services.rental_service import RentalService

        assert RentalService._calculate_duration_hours(None, None) == Decimal("0")

    def test_min_hours(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
        end = datetime(2026, 11, 5, 8, 10, tzinfo=UTC)  # 10 min < MIN_HOURS
        result = RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("0.50")


class TestCalculateDays:
    """Cover _calculate_days (lines 51-57)."""

    def test_one_shift(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
        end = datetime(2026, 11, 5, 16, 0, tzinfo=UTC)
        result = RentalService._calculate_days(start, end)
        assert result == Decimal("1")

    def test_two_shifts(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)
        end = datetime(2026, 11, 6, 16, 0, tzinfo=UTC)  # 32 hours
        result = RentalService._calculate_days(start, end)
        assert result == Decimal("4")


class TestCalculatePlanAmount:
    """Cover _calculate_plan_amount (lines 59-101)."""

    def test_hourly(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=1, unit_price=Decimal("1500"))
        rental = SimpleNamespace(
            rate_type=RateType.HOURLY,
            items=[item],
            start_date=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            end_date=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
        )
        result = RentalService._calculate_plan_amount(rental)
        assert result == Decimal("12000.00")  # 8h * 1500

    def test_shift(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=1, unit_price=Decimal("10000"))
        rental = SimpleNamespace(
            rate_type=RateType.SHIFT,
            items=[item],
            start_date=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            end_date=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
        )
        result = RentalService._calculate_plan_amount(rental)
        assert result == Decimal("10000.00")  # 1 shift * 10000

    def test_trip(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=2, unit_price=Decimal("5000"))
        rental = SimpleNamespace(rate_type=RateType.TRIP, items=[item])
        result = RentalService._calculate_plan_amount(rental)
        assert result == Decimal("10000.00")


class TestCalculateActualAmount:
    """Cover _calculate_actual_amount (lines 103-161)."""

    def test_hourly_with_actual(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            quantity=1, unit_price=Decimal("1500"), actual_moto_hours=Decimal("10")
        )
        rental = SimpleNamespace(
            rate_type=RateType.HOURLY,
            items=[item],
            start_date=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            end_date=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
            actual_return_date=None,
        )
        result = RentalService._calculate_actual_amount(rental)
        assert result == Decimal("15000.00")  # 10h * 1500

    def test_combined(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            quantity=1,
            unit_price=Decimal("1000"),
            actual_moto_hours=Decimal("8"),
            actual_mileage=Decimal("100"),
        )
        rental = SimpleNamespace(
            rate_type=RateType.COMBINED,
            items=[item],
            mileage_rate=Decimal("50"),
            start_date=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            end_date=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
            actual_return_date=None,
        )
        result = RentalService._calculate_actual_amount(rental)
        # hourly: 8*1000=8000, mileage: 100*50=5000
        assert result == Decimal("13000.00")


class TestCheckVehicleAvailability:
    """Cover _check_vehicle_availability (lines 163-194)."""

    def test_available(self, mock_db):
        from app.services.rental_service import RentalService

        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = (
            None
        )
        result = RentalService._check_vehicle_availability(
            mock_db, 1, datetime.now(UTC), datetime.now(UTC)
        )
        assert result is True

    def test_not_available(self, mock_db):
        from app.services.rental_service import RentalService

        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id=1
        )
        result = RentalService._check_vehicle_availability(
            mock_db, 1, datetime.now(UTC), datetime.now(UTC)
        )
        assert result is False


class TestCreateRental:
    """Cover create_rental (lines 196-276)."""

    def test_invalid_dates(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService

        rental_in = SimpleNamespace(
            start_date=datetime(2026, 11, 6, tzinfo=UTC),
            end_date=datetime(2026, 11, 5, tzinfo=UTC),
            client_id=1,
            request_id=None,
            rate_type=None,
            hourly_rate=None,
            shift_rate=None,
            trip_rate=None,
            volume_rate=None,
            mileage_rate=None,
            discount=None,
            prepayment_status=None,
            prepayment_amount=None,
            comment=None,
            items=[],
        )
        with pytest.raises(HTTPException) as exc:
            RentalService.create_rental(mock_db, rental_in, 1, 1)
        assert exc.value.status_code == 400

    def test_vehicle_unavailable(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService

        rental_in = SimpleNamespace(
            start_date=datetime(2026, 11, 5, tzinfo=UTC),
            end_date=datetime(2026, 11, 6, tzinfo=UTC),
            client_id=1,
            request_id=None,
            rate_type=None,
            hourly_rate=None,
            shift_rate=None,
            trip_rate=None,
            volume_rate=None,
            mileage_rate=None,
            discount=None,
            prepayment_status=None,
            prepayment_amount=None,
            comment=None,
            items=[
                SimpleNamespace(vehicle_id=1, quantity=1, unit_price=Decimal("1000"))
            ],
        )
        # Vehicle not available
        mock_db.query.return_value.join.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id=1
        )

        with pytest.raises(HTTPException) as exc:
            RentalService.create_rental(mock_db, rental_in, 1, 1)
        assert exc.value.status_code == 409


class TestGetRental:
    """Cover get_rental (lines 278-291)."""

    def test_not_found(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService

        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            None
        )
        with pytest.raises(HTTPException) as exc:
            RentalService.get_rental(mock_db, 999, [1])
        assert exc.value.status_code == 404

    def test_success(self, mock_db):
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(id=1, company_id=1)
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            rental
        )
        result = RentalService.get_rental(mock_db, 1, [1])
        assert result.id == 1


class TestActivateRental:
    """Cover activate_rental (lines 456-488)."""

    def test_wrong_status(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.ACTIVE, items=[])
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            rental
        )
        with pytest.raises(HTTPException) as exc:
            RentalService.activate_rental(mock_db, 1, 1)
        assert exc.value.status_code == 400

    def test_no_items(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.DRAFT, items=[])
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            rental
        )
        with pytest.raises(HTTPException) as exc:
            RentalService.activate_rental(mock_db, 1, 1)
        assert exc.value.status_code == 400


class TestCancelRental:
    """Cover cancel_rental (lines 490-511)."""

    def test_wrong_status(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.COMPLETED, prepayment_paid_at=None)
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            rental
        )
        with pytest.raises(HTTPException) as exc:
            RentalService.cancel_rental(mock_db, 1, 1)
        assert exc.value.status_code == 400

    def test_success_with_prepayment(self, mock_db):
        from app.models.rental import PrepaymentStatus, RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.DRAFT,
            prepayment_paid_at=datetime.now(UTC),
            prepayment_status=PrepaymentStatus.PAID,
        )
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            rental
        )
        result = RentalService.cancel_rental(mock_db, 1, 1)
        assert result.status == RentalStatus.CANCELLED
        assert result.prepayment_status == PrepaymentStatus.REFUNDED


class TestCloseRental:
    """Cover close_rental (lines 513-608)."""

    def test_wrong_status(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.DRAFT)
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            rental
        )
        with pytest.raises(HTTPException) as exc:
            RentalService.close_rental(
                mock_db,
                1,
                SimpleNamespace(actual_return_date=None, items_actuals=None),
                1,
            )
        assert exc.value.status_code == 400

    def test_success(self, mock_db):
        from app.models.rental import RateType, RentalStatus
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            id=1,
            unit_price=Decimal("1000"),
            quantity=1,
            actual_moto_hours=None,
            actual_mileage=None,
            actual_trips=None,
            actual_volume=None,
        )
        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.ACTIVE,
            items=[item],
            start_date=datetime(2026, 11, 5, 8, 0, tzinfo=UTC),
            end_date=datetime(2026, 11, 6, tzinfo=UTC),
            actual_return_date=None,
            discount=Decimal("0"),
            rate_type=RateType.HOURLY,
            mileage_rate=None,
            total_amount=Decimal("0"),
            base_price=Decimal("0"),
        )
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            rental
        )

        close_data = SimpleNamespace(
            actual_return_date=datetime(2026, 11, 6, 18, 0, tzinfo=UTC),
            items_actuals=None,
        )

        with patch.object(RentalService, "_create_documents_from_rental"):
            result = RentalService.close_rental(mock_db, 1, close_data, 1)

        assert result.status == RentalStatus.COMPLETED
        mock_db.commit.assert_called()


class TestCreateInvoiceFromRental:
    """Cover _create_invoice_from_rental (lines 629-704)."""

    def test_success(self, mock_db):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(
            id=1,
            request_id=None,
            client_id=1,
            company_id=1,
            total_amount=Decimal("10000"),
            rate_type=RateType.HOURLY,
        )
        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="INV-2026-0001",
        ):
            invoice = RentalService._create_invoice_from_rental(mock_db, rental)
        assert invoice.total > Decimal("0")
        mock_db.add.assert_called()


class TestCreatePayoutsFromRental:
    """Cover _create_payouts_from_rental (lines 744-852)."""

    def test_zero_total(self, mock_db):
        from app.services.rental_service import RentalService

        item = SimpleNamespace(unit_price=Decimal("0"), quantity=1)
        rental = SimpleNamespace(
            id=1, items=[item], total_amount=Decimal("0"), commission_rate=None
        )
        result = RentalService._create_payouts_from_rental(mock_db, rental)
        assert result == []

    def test_with_owners(self, mock_db):
        from app.services.rental_service import RentalService

        item = SimpleNamespace(vehicle_id=1, unit_price=Decimal("10000"), quantity=1)
        vehicle = SimpleNamespace(id=1, owner_id=5)
        rental = SimpleNamespace(
            id=1,
            items=[item],
            total_amount=Decimal("10000"),
            commission_rate=Decimal("10"),
            request_id=None,
            company_id=1,
        )

        mock_db.get.return_value = vehicle
        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="PAY-2026-0001",
        ):
            payouts = RentalService._create_payouts_from_rental(mock_db, rental)

        assert len(payouts) == 1
        assert payouts[0].gross_amount == Decimal("10000.00")
        assert payouts[0].net_amount == Decimal("9000.00")
