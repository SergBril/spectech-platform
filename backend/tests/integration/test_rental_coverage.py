"""Tests for rental_service coverage improvement."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


class TestCalculatePlanAmount:
    """Cover _calculate_plan_amount branches (lines 82-98)."""

    def _make_rental(self, rate_type, unit_price=Decimal("1000"), quantity=1):
        item = SimpleNamespace(quantity=quantity, unit_price=unit_price)
        return SimpleNamespace(
            rate_type=rate_type,
            unit_price=unit_price,
            quantity=quantity,
            start_date=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc),
            items=[item],
        )

    def test_shift_rate(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_plan_amount(self._make_rental(RateType.SHIFT))
        assert result > 0

    def test_trip_rate(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_plan_amount(self._make_rental(RateType.TRIP))
        assert result == Decimal("1000")

    def test_volume_rate(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_plan_amount(self._make_rental(RateType.VOLUME))
        assert result == Decimal("1000")

    def test_mileage_rate(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_plan_amount(self._make_rental(RateType.MILEAGE))
        assert result == Decimal("1000")

    def test_combined_rate(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_plan_amount(self._make_rental(RateType.COMBINED))
        assert result > 0


class TestCalculateActualAmount:
    """Cover _calculate_actual_amount branches (lines 123-154)."""

    def _make_rental_with_items(self, rate_type, **item_fields):
        item = SimpleNamespace(
            quantity=item_fields.get("quantity", 1),
            unit_price=item_fields.get("unit_price", Decimal("1000")),
            actual_trips=item_fields.get("trips", 5),
            actual_volume=item_fields.get("volume", Decimal("10")),
            actual_mileage=item_fields.get("mileage", Decimal("100")),
            actual_moto_hours=item_fields.get("moto_hours", Decimal("16")),
        )
        return SimpleNamespace(
            rate_type=rate_type,
            unit_price=Decimal("1000"),
            quantity=1,
            mileage_rate=Decimal("50"),
            start_date=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc),
            actual_return_date=None,
            items=[item],
        )

    def test_shift_actual(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_actual_amount(
            self._make_rental_with_items(RateType.SHIFT)
        )
        assert result > 0

    def test_trip_actual(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_actual_amount(
            self._make_rental_with_items(RateType.TRIP, trips=3)
        )
        assert result == Decimal("3000")

    def test_volume_actual(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_actual_amount(
            self._make_rental_with_items(RateType.VOLUME, volume=Decimal("5"))
        )
        assert result == Decimal("5000")

    def test_mileage_actual(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_actual_amount(
            self._make_rental_with_items(RateType.MILEAGE, mileage=Decimal("200"))
        )
        assert result == Decimal("200000")

    def test_combined_actual(self):
        from app.services.rental_service import RentalService
        from app.models.rental import RateType
        result = RentalService._calculate_actual_amount(
            self._make_rental_with_items(
                RateType.COMBINED, moto_hours=Decimal("8"), mileage=Decimal("50")
            )
        )
        # hourly_part = 8 * 1000 * 1 = 8000
        # mileage_part = 50 * 50 * 1 = 2500
        assert result == Decimal("10500")


class TestUpdateRental:
    """Cover update_rental method (lines 324-362)."""

    def test_update_draft_rental(self, db_session, sample_rental, company):
        from app.services.rental_service import RentalService
        from app.models.rental import RentalStatus

        sample_rental.status = RentalStatus.DRAFT
        db_session.commit()
        db_session.refresh(sample_rental)

        data = SimpleNamespace(
            start_date=sample_rental.start_date,
            end_date=sample_rental.end_date + timedelta(hours=8),
            discount=Decimal("500"),
            comment="Updated comment",
            prepayment_status=None,
            prepayment_amount=None,
        )

        result = RentalService.update_rental(
            db_session, sample_rental.id, data, company.id
        )
        assert result.comment == "Updated comment"
        assert result.discount == Decimal("500")

    def test_update_non_draft_raises(self, db_session, sample_rental, company):
        from app.services.rental_service import RentalService
        from app.models.rental import RentalStatus
        from fastapi import HTTPException

        sample_rental.status = RentalStatus.ACTIVE
        db_session.commit()
        db_session.refresh(sample_rental)

        data = SimpleNamespace(
            start_date=None, end_date=None, discount=None,
            comment="test", prepayment_status=None, prepayment_amount=None,
        )

        with pytest.raises(HTTPException) as exc_info:
            RentalService.update_rental(
                db_session, sample_rental.id, data, company.id
            )
        assert exc_info.value.status_code == 400

    def test_update_invalid_dates_raises(self, db_session, sample_rental, company):
        from app.services.rental_service import RentalService
        from app.models.rental import RentalStatus
        from fastapi import HTTPException

        sample_rental.status = RentalStatus.DRAFT
        db_session.commit()
        db_session.refresh(sample_rental)

        data = SimpleNamespace(
            start_date=sample_rental.end_date + timedelta(days=1),
            end_date=sample_rental.start_date - timedelta(days=1),
            discount=None, comment=None,
            prepayment_status=None, prepayment_amount=None,
        )

        with pytest.raises(HTTPException) as exc_info:
            RentalService.update_rental(
                db_session, sample_rental.id, data, company.id
            )
        assert exc_info.value.status_code == 400
