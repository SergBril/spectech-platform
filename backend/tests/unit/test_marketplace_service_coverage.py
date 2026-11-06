"""Coverage tests for marketplace_service."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestPublishVehicle:
    """Cover publish_vehicle (lines 24-95)."""

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(
            id=1, company_id=7, is_deleted=False,
            is_published=False, hourly_rate=None, shift_rate=None,
        )
        mock_db.get.return_value = vehicle
        result = MarketplaceService.publish_vehicle(
            mock_db, vehicle_id=1, company_id=7,
            hourly_rate=Decimal("1500"), description="Test",
        )
        assert result.is_published is True
        mock_db.commit.assert_called()

    def test_vehicle_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            MarketplaceService.publish_vehicle(mock_db, vehicle_id=999, company_id=7, hourly_rate=Decimal("100"))

    def test_wrong_company(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, company_id=99, is_deleted=False)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="another company"):
            MarketplaceService.publish_vehicle(mock_db, vehicle_id=1, company_id=7, hourly_rate=Decimal("100"))

    def test_no_rates(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, company_id=7, is_deleted=False)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="rate"):
            MarketplaceService.publish_vehicle(mock_db, vehicle_id=1, company_id=7)


class TestUnpublishVehicle:
    """Cover unpublish_vehicle (lines 97-113)."""

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, company_id=7, is_published=True)
        mock_db.get.return_value = vehicle
        result = MarketplaceService.unpublish_vehicle(mock_db, vehicle_id=1, company_id=7)
        assert result.is_published is False
        mock_db.commit.assert_called()

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError):
            MarketplaceService.unpublish_vehicle(mock_db, vehicle_id=999, company_id=7)


class TestUpdateListing:
    """Cover update_listing (lines 115-147)."""

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, company_id=7, is_published=True)
        mock_db.get.return_value = vehicle
        result = MarketplaceService.update_listing(
            mock_db, vehicle_id=1, company_id=7,
            hourly_rate=Decimal("2000"), description="Updated",
        )
        mock_db.commit.assert_called()

    def test_not_published(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, company_id=7, is_published=False)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError):
            MarketplaceService.update_listing(mock_db, vehicle_id=1, company_id=7, hourly_rate=Decimal("100"))


class TestSearchVehicles:
    """Cover search_vehicles (lines 149-240)."""

    def test_empty(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.search_vehicles(mock_db, company_id=7)
        assert isinstance(result, list)

    def test_with_filters(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.search_vehicles(
            mock_db, company_id=7, category_id=1,
            min_hourly_rate=Decimal("1000"), max_hourly_rate=Decimal("5000"),
            lat=55.75, lon=37.62, radius_km=50,
        )
        assert isinstance(result, list)


class TestGetVehicleDetails:
    """Cover get_vehicle_details (lines 242-250)."""

    def test_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, is_published=True, is_deleted=False)
        mock_db.get.return_value = vehicle
        result = MarketplaceService.get_vehicle_details(mock_db, vehicle_id=1)
        assert result == vehicle

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        result = MarketplaceService.get_vehicle_details(mock_db, vehicle_id=999)
        assert result is None


class TestGetAvailabilityCalendar:
    """Cover get_availability_calendar (lines 252-320)."""

    def test_empty(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1)
        mock_db.get.return_value = vehicle
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = MarketplaceService.get_availability_calendar(
            mock_db, vehicle_id=1, month_start=date(2026, 11, 1),
        )
        assert isinstance(result, list)


class TestCreateRequestFromListing:
    """Cover create_request_from_listing (lines 322-409)."""

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(
            id=1, company_id=7, is_published=True, is_deleted=False,
            hourly_rate=Decimal("1500"), shift_rate=None,
        )
        mock_db.get.return_value = vehicle
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = MarketplaceService.create_request_from_listing(
            mock_db, vehicle_id=1, requester_company_id=5,
            start_date=date(2026, 12, 1), end_date=date(2026, 12, 5),
        )
        mock_db.add.assert_called()
        mock_db.commit.assert_called()


class TestFilterAvailable:
    """Cover _filter_available (lines 441-481)."""

    def test_filter(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1)
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = MarketplaceService._filter_available(
            mock_db, [vehicle], date(2026, 12, 1), date(2026, 12, 5),
        )
        assert isinstance(result, list)


class TestHaversine:
    """Cover _haversine (lines 483-end)."""

    def test_same_point(self):
        from app.services.marketplace_service import MarketplaceService
        result = MarketplaceService._haversine(55.75, 37.62, 55.75, 37.62)
        assert result == 0.0

    def test_different_points(self):
        from app.services.marketplace_service import MarketplaceService
        result = MarketplaceService._haversine(55.75, 37.62, 59.93, 30.32)
        assert result > 0
