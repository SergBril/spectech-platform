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
        vehicle = MagicMock()
        vehicle.id = 1
        vehicle.company_id = 7
        vehicle.is_deleted = False
        vehicle.hourly_rate = None
        vehicle.shift_rate = None
        vehicle.name = "KAMAZ"
        mock_db.get.return_value = vehicle
        result = MarketplaceService.publish_vehicle(
            mock_db, vehicle_id=1, company_id=7,
            hourly_rate=Decimal("1500"), description="Test",
        )
        assert vehicle.is_available_for_rent is True
        assert vehicle.marketplace_commission_agreed is True
        mock_db.commit.assert_called()
        mock_db.refresh.assert_called()

    def test_vehicle_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            MarketplaceService.publish_vehicle(mock_db, vehicle_id=999, company_id=7, hourly_rate=Decimal("100"))

    def test_wrong_company(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 99
        vehicle.is_deleted = False
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="another company"):
            MarketplaceService.publish_vehicle(mock_db, vehicle_id=1, company_id=7, hourly_rate=Decimal("100"))

    def test_deleted_vehicle(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.is_deleted = True
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="deleted"):
            MarketplaceService.publish_vehicle(mock_db, vehicle_id=1, company_id=7, hourly_rate=Decimal("100"))

    def test_no_rates(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.is_deleted = False
        vehicle.hourly_rate = None
        vehicle.shift_rate = None
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="rate"):
            MarketplaceService.publish_vehicle(mock_db, vehicle_id=1, company_id=7)

    def test_existing_vehicle_rate(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.is_deleted = False
        vehicle.hourly_rate = Decimal("1000")
        vehicle.shift_rate = None
        vehicle.name = "KAMAZ"
        mock_db.get.return_value = vehicle
        # No new rate passed, but vehicle already has hourly_rate
        result = MarketplaceService.publish_vehicle(mock_db, vehicle_id=1, company_id=7)
        assert vehicle.is_available_for_rent is True

    def test_with_all_params(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.is_deleted = False
        vehicle.hourly_rate = None
        vehicle.shift_rate = None
        vehicle.name = "KAMAZ"
        mock_db.get.return_value = vehicle
        result = MarketplaceService.publish_vehicle(
            mock_db, vehicle_id=1, company_id=7,
            hourly_rate=Decimal("1500"), shift_rate=Decimal("12000"),
            downtime_hourly_rate=Decimal("500"), description="Full",
            photos=["url1"], base_location_lat=55.75, base_location_lon=37.62,
        )
        assert vehicle.downtime_hourly_rate == Decimal("500")
        assert vehicle.base_location_lat == 55.75


class TestUnpublishVehicle:
    """Cover unpublish_vehicle (lines 97-113)."""

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.id = 1
        vehicle.company_id = 7
        vehicle.is_available_for_rent = True
        mock_db.get.return_value = vehicle
        result = MarketplaceService.unpublish_vehicle(mock_db, vehicle_id=1, company_id=7)
        assert vehicle.is_available_for_rent is False
        mock_db.commit.assert_called()

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError):
            MarketplaceService.unpublish_vehicle(mock_db, vehicle_id=999, company_id=7)

    def test_wrong_company(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 99
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="another company"):
            MarketplaceService.unpublish_vehicle(mock_db, vehicle_id=1, company_id=7)


class TestUpdateListing:
    """Cover update_listing (lines 115-147)."""

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.is_available_for_rent = True
        vehicle.name = "KAMAZ"
        mock_db.get.return_value = vehicle
        result = MarketplaceService.update_listing(
            mock_db, vehicle_id=1, company_id=7,
            hourly_rate=Decimal("2000"), description="Updated",
        )
        mock_db.commit.assert_called()

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError):
            MarketplaceService.update_listing(mock_db, vehicle_id=999, company_id=7)

    def test_wrong_company(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.company_id = 99
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="another company"):
            MarketplaceService.update_listing(mock_db, vehicle_id=1, company_id=7, hourly_rate=Decimal("100"))


class TestSearchVehicles:
    """Cover search_vehicles (lines 149-240)."""

    def test_empty(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.search_vehicles(mock_db)
        assert isinstance(result, list)

    def test_with_all_filters(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.search_vehicles(
            mock_db, category_id=1, search="kama",
            min_hourly_rate=1000, max_hourly_rate=5000,
            lat=55.75, lon=37.62, radius_km=50,
            available_from=date(2026, 12, 1), available_to=date(2026, 12, 5),
            limit=10, offset=0,
        )
        assert isinstance(result, list)


class TestGetVehicleDetails:
    """Cover get_vehicle_details (lines 242-250)."""

    def test_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.is_available_for_rent = True
        vehicle.is_deleted = False
        mock_db.get.return_value = vehicle
        result = MarketplaceService.get_vehicle_details(mock_db, vehicle_id=1)
        assert result == vehicle

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        result = MarketplaceService.get_vehicle_details(mock_db, vehicle_id=999)
        assert result is None

    def test_not_available(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.is_available_for_rent = False
        vehicle.is_deleted = False
        mock_db.get.return_value = vehicle
        result = MarketplaceService.get_vehicle_details(mock_db, vehicle_id=1)
        assert result is None


class TestGetAvailabilityCalendar:
    """Cover get_availability_calendar (lines 252-320)."""

    def test_empty(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.get_availability_calendar(
            mock_db, vehicle_id=1, from_date=date(2026, 11, 1), to_date=date(2026, 11, 30),
        )
        assert isinstance(result, list)

    def test_default_dates(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.get_availability_calendar(mock_db, vehicle_id=1)
        assert isinstance(result, list)


class TestCreateRequestFromListing:
    """Cover create_request_from_listing (lines 322-409)."""

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.id = 1
        vehicle.company_id = 7
        vehicle.is_available_for_rent = True
        vehicle.is_deleted = False
        vehicle.hourly_rate = Decimal("1500")
        vehicle.shift_rate = None
        mock_db.get.return_value = vehicle
        # _filter_available returns {1} (available)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.create_request_from_listing(
            mock_db, vehicle_id=1, client_contractor_id=5, company_id=5,
            work_type="excavation", planned_start=datetime(2026, 12, 1),
            planned_end=datetime(2026, 12, 5), comment="Need excavator",
        )
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_vehicle_not_available(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.is_available_for_rent = False
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="not available"):
            MarketplaceService.create_request_from_listing(
                mock_db, vehicle_id=1, client_contractor_id=5, company_id=5,
                work_type="test", planned_start=datetime(2026, 12, 1),
                planned_end=datetime(2026, 12, 5),
            )


class TestFilterAvailable:
    """Cover _filter_available (lines 441-481)."""

    def test_empty_ids(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        result = MarketplaceService._filter_available(mock_db, [], date(2026, 12, 1), date(2026, 12, 5))
        assert result == set()

    def test_all_available(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService._filter_available(mock_db, [1, 2, 3], date(2026, 12, 1), date(2026, 12, 5))
        assert result == {1, 2, 3}

    def test_some_busy(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        rental = MagicMock()
        item = MagicMock()
        item.vehicle_id = 2
        rental.items = [item]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [rental]
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService._filter_available(mock_db, [1, 2, 3], date(2026, 12, 1), date(2026, 12, 5))
        assert result == {1, 3}


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



class TestAvailabilityCalendarWithRentals:
    """Cover lines 290-301: rental items loop in calendar."""

    def test_with_busy_dates(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        rental = MagicMock()
        rental.start_date = datetime(2026, 11, 5)
        rental.end_date = datetime(2026, 11, 7)
        rental.id = 42
        item = MagicMock()
        item.vehicle_id = 1
        rental.items = [item]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [rental]
        mock_db.scalars.return_value = mock_scalars
        result = MarketplaceService.get_availability_calendar(
            mock_db, vehicle_id=1, from_date=date(2026, 11, 1), to_date=date(2026, 11, 30),
        )
        assert isinstance(result, list)
        # Should have some busy dates
        busy = [d for d in result if not d["available"]]
        assert len(busy) >= 3


class TestCreateRequestExtraBranches:
    """Cover remaining create_request branches."""

    def test_vehicle_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            MarketplaceService.create_request_from_listing(
                mock_db, vehicle_id=999, client_contractor_id=5, company_id=5,
                work_type="test", planned_start=datetime(2026, 12, 1),
                planned_end=datetime(2026, 12, 5),
            )

    def test_not_available_period(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.id = 1
        vehicle.is_available_for_rent = True
        mock_db.get.return_value = vehicle
        # _filter_available returns empty set (vehicle busy)
        mock_scalars = MagicMock()
        rental = MagicMock()
        item = MagicMock()
        item.vehicle_id = 1
        rental.items = [item]
        mock_scalars.all.return_value = [rental]
        mock_db.scalars.return_value = mock_scalars
        with pytest.raises(ValueError, match="not available for the selected period"):
            MarketplaceService.create_request_from_listing(
                mock_db, vehicle_id=1, client_contractor_id=5, company_id=5,
                work_type="test", planned_start=datetime(2026, 12, 1),
                planned_end=datetime(2026, 12, 5),
            )


class TestNotifyOwnerNewRequest:
    """Cover _notify_owner_new_request (lines 415-438)."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.name = "KAMAZ"
        request = MagicMock()
        request.id = 1
        request.work_type = "excavation"
        request.planned_start = datetime(2026, 12, 1, 9, 0)
        request.planned_end = datetime(2026, 12, 5, 18, 0)

        with patch("app.services.marketplace_service.email_service") as mock_email:
            await MarketplaceService._notify_owner_new_request(
                vehicle=vehicle, request=request,
                owner_name="Ivan", owner_email="ivan@test.com",
            )
            mock_email.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_failure(self):
        from app.services.marketplace_service import MarketplaceService
        vehicle = MagicMock()
        vehicle.name = "KAMAZ"
        request = MagicMock()
        request.id = 1
        request.work_type = "test"
        request.planned_start = datetime(2026, 12, 1)
        request.planned_end = datetime(2026, 12, 5)

        with patch("app.services.marketplace_service.email_service") as mock_email:
            mock_email.send_email.side_effect = Exception("SMTP error")
            # Should not raise, just log error
            await MarketplaceService._notify_owner_new_request(
                vehicle=vehicle, request=request,
                owner_name="Ivan", owner_email="ivan@test.com",
            )
