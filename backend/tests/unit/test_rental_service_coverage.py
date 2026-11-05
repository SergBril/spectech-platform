"""Tests for RentalService - batch 1: calculations + CRUD + status transitions."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestCalculateDurationHours:
    """Cover _calculate_duration_hours (lines 39-50)."""

    def test_normal_duration(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 11, 1, 16, 0, tzinfo=UTC)
        RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("8.00")

    def test_none_dates(self):
        from app.services.rental_service import RentalService

        assert RentalService._calculate_duration_hours(None, None) == Decimal("0")

    def test_min_hours_enforced(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 11, 1, 8, 10, tzinfo=UTC)  # 10 min < 0.5h
        RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("0.50")

    def test_naive_dates_get_utc(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 1, 8, 0)
        end = datetime(2026, 11, 1, 20, 0)
        RentalService._calculate_duration_hours(start, end)
        assert result == Decimal("12.00")


class TestCalculateDays:
    """Cover _calculate_days (lines 51-57)."""

    def test_one_shift(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        end = datetime(2026, 11, 1, 16, 0, tzinfo=UTC)  # 8h = 1 shift
        RentalService._calculate_days(start, end)
        assert result == Decimal("1")

    def test_multiple_shifts(self):
        from app.services.rental_service import RentalService

        start = datetime(2026, 11, 1, 0, 0, tzinfo=UTC)
        end = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)  # 24h = 3 shifts
        RentalService._calculate_days(start, end)
        assert result == Decimal("3")


class TestCalculatePlanAmount:
    """Cover _calculate_plan_amount (lines 59-101)."""

    def _make_rental(self, rate_type, items, **kwargs):
        return SimpleNamespace(
            rate_type=rate_type,
            start_date=datetime(2026, 11, 1, 8, 0, tzinfo=UTC),
            end_date=datetime(2026, 11, 1, 16, 0, tzinfo=UTC),
            items=items,
            mileage_rate=0,
            **kwargs,
        )

    def test_hourly(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=1, unit_price=1000)
        rental = self._make_rental(RateType.HOURLY, [item])
        RentalService._calculate_plan_amount(rental)
        assert result == Decimal("8000.00")  # 8h * 1000

    def test_shift(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=1, unit_price=5000)
        rental = self._make_rental(RateType.SHIFT, [item])
        RentalService._calculate_plan_amount(rental)
        assert result == Decimal("5000.00")  # 1 shift * 5000

    def test_trip(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=2, unit_price=3000)
        rental = self._make_rental(RateType.TRIP, [item])
        RentalService._calculate_plan_amount(rental)
        assert result == Decimal("6000.00")

    def test_volume(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=1, unit_price=2000)
        rental = self._make_rental(RateType.VOLUME, [item])
        assert RentalService._calculate_plan_amount(rental) == Decimal("2000.00")

    def test_mileage(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=1, unit_price=1500)
        rental = self._make_rental(RateType.MILEAGE, [item])
        assert RentalService._calculate_plan_amount(rental) == Decimal("1500.00")

    def test_combined(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(quantity=1, unit_price=1000)
        rental = self._make_rental(RateType.COMBINED, [item])
        assert RentalService._calculate_plan_amount(rental) == Decimal("8000.00")


class TestCalculateActualAmount:
    """Cover _calculate_actual_amount (lines 103-162)."""

    def _make_rental(self, rate_type, items, **kwargs):
        return SimpleNamespace(
            rate_type=rate_type,
            start_date=datetime(2026, 11, 1, 8, 0, tzinfo=UTC),
            end_date=datetime(2026, 11, 1, 16, 0, tzinfo=UTC),
            actual_return_date=None,
            items=items,
            mileage_rate=50,
            **kwargs,
        )

    def test_hourly_with_actual(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            quantity=1,
            unit_price=1000,
            actual_moto_hours=10,
            actual_mileage=0,
            actual_trips=0,
            actual_volume=0,
        )
        rental = self._make_rental(RateType.HOURLY, [item])
        assert RentalService._calculate_actual_amount(rental) == Decimal("10000.00")

    def test_hourly_fallback_to_duration(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            quantity=1,
            unit_price=1000,
            actual_moto_hours=0,
            actual_mileage=0,
            actual_trips=0,
            actual_volume=0,
        )
        rental = self._make_rental(RateType.HOURLY, [item])
        assert RentalService._calculate_actual_amount(rental) == Decimal("8000.00")

    def test_trip_actual(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            quantity=1,
            unit_price=3000,
            actual_moto_hours=0,
            actual_mileage=0,
            actual_trips=5,
            actual_volume=0,
        )
        rental = self._make_rental(RateType.TRIP, [item])
        assert RentalService._calculate_actual_amount(rental) == Decimal("15000.00")

    def test_combined(self):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            quantity=1,
            unit_price=1000,
            actual_moto_hours=8,
            actual_mileage=100,
            actual_trips=0,
            actual_volume=0,
        )
        rental = self._make_rental(RateType.COMBINED, [item])
        # 8*1000 + 100*50 = 8000 + 5000 = 13000
        assert RentalService._calculate_actual_amount(rental) == Decimal("13000.00")


class TestActivateRental:
    """Cover activate_rental (lines 456-489)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.DRAFT,
            items=[SimpleNamespace()],
            prepayment_status=None,
            prepayment_paid_at=None,
        )
        with patch.object(RentalService, "get_rental", return_value=rental):
            RentalService.activate_rental(mock_db, 1, 1)
        assert result.status == RentalStatus.ACTIVE

    def test_wrong_status_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.ACTIVE, items=[])
        with patch.object(RentalService, "get_rental", return_value=rental):
            with pytest.raises(HTTPException) as exc:
                RentalService.activate_rental(mock_db, 1, 1)
            assert exc.value.status_code == 400

    def test_no_items_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.DRAFT, items=[])
        with patch.object(RentalService, "get_rental", return_value=rental):
            with pytest.raises(HTTPException) as exc:
                RentalService.activate_rental(mock_db, 1, 1)
            assert exc.value.status_code == 400


class TestCancelRental:
    """Cover cancel_rental (lines 490-512)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(
            id=1, status=RentalStatus.DRAFT, prepayment_paid_at=None
        )
        with patch.object(RentalService, "get_rental", return_value=rental):
            RentalService.cancel_rental(mock_db, 1, 1)
        assert result.status == RentalStatus.CANCELLED

    def test_wrong_status_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.COMPLETED)
        with patch.object(RentalService, "get_rental", return_value=rental):
            with pytest.raises(HTTPException):
                RentalService.cancel_rental(mock_db, 1, 1)


class TestCloseRental:
    """Cover close_rental (lines 513-609)."""

    def test_success_no_penalty(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        item = SimpleNamespace(
            id=1,
            unit_price=1000,
            quantity=1,
            actual_moto_hours=8,
            actual_mileage=0,
            actual_trips=0,
            actual_volume=0,
        )
        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.ACTIVE,
            items=[item],
            end_date=datetime(2026, 11, 1, 16, 0, tzinfo=UTC),
            actual_return_date=None,
            discount=Decimal("0"),
            rate_type=MagicMock(),
            mileage_rate=0,
        )
        close_data = SimpleNamespace(
            actual_return_date=datetime(2026, 11, 1, 16, 0, tzinfo=UTC),
            items_actuals=None,
        )

        with (
            patch.object(RentalService, "get_rental", return_value=rental),
            patch.object(
                RentalService, "_calculate_actual_amount", return_value=Decimal("8000")
            ),
            patch.object(RentalService, "_create_documents_from_rental"),
        ):
            RentalService.close_rental(mock_db, 1, close_data, 1)

        assert result.status == RentalStatus.COMPLETED
        assert result.total_amount == Decimal("8000")

    def test_wrong_status_raises(self, mock_db):
        from fastapi import HTTPException

        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(status=RentalStatus.DRAFT)
        close_data = SimpleNamespace(actual_return_date=None, items_actuals=None)
        with patch.object(RentalService, "get_rental", return_value=rental):
            with pytest.raises(HTTPException):
                RentalService.close_rental(mock_db, 1, close_data, 1)


class TestGetRental:
    """Cover get_rental (lines 278-292)."""

    def test_success(self, mock_db):
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(id=1)
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = rental
        mock_db.query.return_value = mock_query

        RentalService.get_rental(mock_db, 1, [1])
        assert result == rental

    def test_not_found_raises(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService

        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc:
            RentalService.get_rental(mock_db, 999, [1])
        assert exc.value.status_code == 404


class TestCreateRental:
    """Cover create_rental (lines 196-277)."""

    def test_invalid_dates_raises(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService

        rental_in = SimpleNamespace(
            start_date=datetime(2026, 11, 5, tzinfo=UTC),
            end_date=datetime(2026, 11, 1, tzinfo=UTC),
        )
        with pytest.raises(HTTPException) as exc:
            RentalService.create_rental(mock_db, rental_in, 1, 1)
        assert exc.value.status_code == 400

    def test_vehicle_unavailable_raises(self, mock_db):
        from fastapi import HTTPException

        from app.services.rental_service import RentalService

        rental_in = SimpleNamespace(
            start_date=datetime(2026, 11, 1, tzinfo=UTC),
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
            items=[SimpleNamespace(vehicle_id=1, quantity=1, unit_price=1000)],
        )

        # flush assigns id
        def mock_flush():
            pass

        mock_db.flush.side_effect = mock_flush

        with patch.object(
            RentalService, "_check_vehicle_availability", return_value=False
        ):
            with pytest.raises(HTTPException) as exc:
                RentalService.create_rental(mock_db, rental_in, 1, 1)
            assert exc.value.status_code == 409


class TestCheckVehicleAvailability:
    """Cover _check_vehicle_availability (lines 163-195)."""

    def test_available(self, mock_db):
        from app.services.rental_service import RentalService

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        RentalService._check_vehicle_availability(
            mock_db,
            1,
            datetime(2026, 11, 1, tzinfo=UTC),
            datetime(2026, 11, 5, tzinfo=UTC),
        )
        assert result is True

    def test_not_available(self, mock_db):
        from app.services.rental_service import RentalService

        existing = SimpleNamespace(id=1)
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.first.return_value = existing
        mock_db.query.return_value = mock_query
        RentalService._check_vehicle_availability(
            mock_db,
            1,
            datetime(2026, 11, 1, tzinfo=UTC),
            datetime(2026, 11, 5, tzinfo=UTC),
        )
        assert result is False


class TestAddRentalItem:
    """Cover add_rental_item (lines 369-417)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.DRAFT,
            items=[],
            start_date=datetime(2026, 11, 1, tzinfo=UTC),
            end_date=datetime(2026, 11, 5, tzinfo=UTC),
            rate_type=MagicMock(),
            discount=Decimal("0"),
        )
        item_in = SimpleNamespace(vehicle_id=1, quantity=1, unit_price=1000)

        with (
            patch.object(RentalService, "get_rental", return_value=rental),
            patch.object(
                RentalService, "_check_vehicle_availability", return_value=True
            ),
            patch.object(
                RentalService, "_calculate_plan_amount", return_value=Decimal("5000")
            ),
        ):
            RentalService.add_rental_item(mock_db, 1, item_in, 1)

        mock_db.add.assert_called()
        mock_db.commit.assert_called()


class TestRemoveRentalItem:
    """Cover remove_rental_item (lines 418-455)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        item = SimpleNamespace(id=10, rental_id=1)
        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.DRAFT,
            items=[item],
            rate_type=MagicMock(),
            discount=Decimal("0"),
        )

        with (
            patch.object(RentalService, "get_rental", return_value=rental),
            patch.object(
                RentalService, "_calculate_plan_amount", return_value=Decimal("0")
            ),
        ):
            RentalService.remove_rental_item(mock_db, 1, 10, 1)

        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called()


class TestListRentals:
    """Cover list_rentals (lines 293-316)."""

    def test_returns_list(self, mock_db):
        from app.services.rental_service import RentalService

        rentals = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = (
            rentals
        )
        mock_db.query.return_value = mock_query

        RentalService.list_rentals(mock_db, [1], limit=50, offset=0)
        assert len(result) == 2


class TestUpdateRental:
    """Cover update_rental (lines 317-368)."""

    def test_success(self, mock_db):
        from app.models.rental import RentalStatus
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(
            id=1,
            status=RentalStatus.DRAFT,
            items=[],
            start_date=datetime(2026, 11, 1, tzinfo=UTC),
            end_date=datetime(2026, 11, 5, tzinfo=UTC),
            rate_type=MagicMock(),
            discount=Decimal("0"),
            comment=None,
            base_price=None,
            total_amount=None,
        )
        update_data = SimpleNamespace(
            start_date=None,
            end_date=None,
            discount=None,
            comment="Updated",
            prepayment_status=None,
            prepayment_amount=None,
        )

        with (
            patch.object(RentalService, "get_rental", return_value=rental),
            patch.object(
                RentalService, "_calculate_plan_amount", return_value=Decimal("5000")
            ),
        ):
            RentalService.update_rental(mock_db, 1, update_data, 1)

        mock_db.commit.assert_called()


class TestCreateDocumentsFromRental:
    """Cover _create_documents_from_rental (lines 610-628)."""

    def test_calls_all_sub_methods(self, mock_db):
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(id=1)
        invoice = SimpleNamespace(id=10)
        act = SimpleNamespace(id=20)
        payouts = [SimpleNamespace(id=30)]

        with (
            patch.object(
                RentalService, "_create_invoice_from_rental", return_value=invoice
            ),
            patch.object(RentalService, "_create_act_from_rental", return_value=act),
            patch.object(
                RentalService, "_create_payouts_from_rental", return_value=payouts
            ),
            patch.object(RentalService, "_send_rental_notifications"),
        ):
            RentalService._create_documents_from_rental(mock_db, rental)

        assert result == (invoice, act, payouts)


class TestCreateInvoiceFromRental:
    """Cover _create_invoice_from_rental (lines 629-705)."""

    def test_success(self, mock_db):
        from app.models.rental import RateType
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(
            id=1,
            request_id=None,
            client_id=10,
            company_id=1,
            total_amount=Decimal("10000"),
            rate_type=RateType.HOURLY,
        )

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="INV-001",
        ):
            RentalService._create_invoice_from_rental(mock_db, rental)

        # Invoice and InvoiceItem added
        assert mock_db.add.call_count == 2
        assert mock_db.flush.call_count == 2


class TestCreateActFromRental:
    """Cover _create_act_from_rental (lines 706-743)."""

    def test_success(self, mock_db):
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(id=1, request_id=None, client_id=10, company_id=1)
        invoice = SimpleNamespace(
            total=Decimal("12000"), vat_amount=Decimal("2000"), vat_rate=Decimal("20")
        )

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="ACT-001",
        ):
            RentalService._create_act_from_rental(mock_db, rental, invoice)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()


class TestCreatePayoutsFromRental:
    """Cover _create_payouts_from_rental (lines 744-853)."""

    def test_zero_total_returns_empty(self, mock_db):
        from app.services.rental_service import RentalService

        item = SimpleNamespace(unit_price=0, quantity=1, vehicle_id=1)
        rental = SimpleNamespace(
            id=1, items=[item], total_amount=Decimal("0"), commission_rate=None
        )

        RentalService._create_payouts_from_rental(mock_db, rental)
        assert result == []

    def test_creates_payouts(self, mock_db):
        from app.services.rental_service import RentalService

        item = SimpleNamespace(unit_price=10000, quantity=1, vehicle_id=1)
        vehicle = SimpleNamespace(id=1, owner_id=20)
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
            return_value="PAY-001",
        ):
            payouts = RentalService._create_payouts_from_rental(mock_db, rental)

        assert len(payouts) == 1
        mock_db.commit.assert_called_once()

    def test_vehicle_not_found_skipped(self, mock_db):
        from app.services.rental_service import RentalService

        item = SimpleNamespace(unit_price=10000, quantity=1, vehicle_id=999)
        rental = SimpleNamespace(
            id=1,
            items=[item],
            total_amount=Decimal("10000"),
            commission_rate=Decimal("10"),
            request_id=None,
            company_id=1,
        )
        mock_db.get.return_value = None

        with patch(
            "app.services.finance_service.generate_document_number",
            return_value="PAY-001",
        ):
            payouts = RentalService._create_payouts_from_rental(mock_db, rental)

        assert payouts == []


class TestSendRentalNotifications:
    """Cover _send_rental_notifications (lines 854-end)."""

    def test_client_not_found_returns(self, mock_db):
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(id=1, client_id=999)
        mock_db.get.return_value = None

        # Should not raise
        RentalService._send_rental_notifications(mock_db, rental, None, [])

    def test_no_event_loop_skips(self, mock_db):
        from app.services.rental_service import RentalService

        client = SimpleNamespace(id=10, name="Client", email="c@test.com", user_id=5)
        rental = SimpleNamespace(id=1, client_id=10)
        invoice = SimpleNamespace(id=100)
        payout = SimpleNamespace(owner_id=20)
        owner = SimpleNamespace(id=20, name="Owner", email="o@test.com", user_id=6)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return client
            return owner

        mock_db.get.side_effect = mock_get

        # No event loop → RuntimeError caught gracefully
        RentalService._send_rental_notifications(mock_db, rental, invoice, [payout])

    def test_exception_handled(self, mock_db):
        from app.services.rental_service import RentalService

        rental = SimpleNamespace(id=1, client_id=10)
        mock_db.get.side_effect = Exception("DB error")

        # Should not raise
        RentalService._send_rental_notifications(mock_db, rental, None, [])
