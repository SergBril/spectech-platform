"""Coverage tests for marketplace_service."""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestPublishVehicle:
    """Cover publish_vehicle (lines 24-95)."""

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            MarketplaceService.publish_vehicle(mock_db, 1, 7)

    def test_wrong_company(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(company_id=99, is_deleted=False)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="another company"):
            MarketplaceService.publish_vehicle(mock_db, 1, 7)

    def test_deleted(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(company_id=7, is_deleted=True)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="deleted"):
            MarketplaceService.publish_vehicle(mock_db, 1, 7)

    def test_no_rate(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(company_id=7, is_deleted=False, hourly_rate=None, shift_rate=None)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="rate must be specified"):
            MarketplaceService.publish_vehicle(mock_db, 1, 7)

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", company_id=7, is_deleted=False,
            hourly_rate=None, shift_rate=None, downtime_hourly_rate=None,
            marketplace_description=None, photos=None,
            base_location_lat=None, base_location_lon=None,
            is_available_for_rent=False, marketplace_commission_agreed=False,
        )
        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda r: None
        result = MarketplaceService.publish_vehicle(
            mock_db, 1, 7, hourly_rate=Decimal("1500"), description="Test",
        )
        assert vehicle.is_available_for_rent is True
        assert vehicle.marketplace_commission_agreed is True
        mock_db.commit.assert_called()


class TestUnpublishVehicle:
    """Cover unpublish_vehicle (lines 97-113)."""

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            MarketplaceService.unpublish_vehicle(mock_db, 1, 7)

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, company_id=7, is_available_for_rent=True, marketplace_commission_agreed=True)
        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda r: None
        MarketplaceService.unpublish_vehicle(mock_db, 1, 7)
        assert vehicle.is_available_for_rent is False
        mock_db.commit.assert_called()


class TestUpdateListing:
    """Cover update_listing (lines 115-147)."""

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            MarketplaceService.update_listing(mock_db, 1, 7, hourly_rate=100)

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, company_id=7, hourly_rate=None)
        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda r: None
        MarketplaceService.update_listing(mock_db, 1, 7, hourly_rate=Decimal("2000"))
        assert vehicle.hourly_rate == Decimal("2000")
        mock_db.commit.assert_called()


class TestSearchVehicles:
    """Cover search_vehicles (lines 149-240)."""

    def test_basic_search(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        v = SimpleNamespace(id=1, base_location_lat=55.75, base_location_lon=37.62)
        mock_db.scalars.return_value.all.return_value = [v]
        result = MarketplaceService.search_vehicles(mock_db)
        assert len(result) == 1

    def test_with_all_filters(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        v = SimpleNamespace(id=1, base_location_lat=55.75, base_location_lon=37.62)
        mock_db.scalars.return_value.all.return_value = [v]
        # Mock _filter_available
        with patch.object(MarketplaceService, "_filter_available", return_value={1}):
            result = MarketplaceService.search_vehicles(
                mock_db, category_id=1, search="KAMAZ",
                min_hourly_rate=100, max_hourly_rate=5000,
                lat=55.75, lon=37.62, radius_km=50,
                available_from=date(2026, 11, 1), available_to=date(2026, 11, 30),
            )
        assert isinstance(result, list)


class TestGetVehicleDetails:
    """Cover get_vehicle_details (lines 242-250)."""

    def test_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        assert MarketplaceService.get_vehicle_details(mock_db, 1) is None

    def test_not_available(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(is_available_for_rent=False, is_deleted=False)
        mock_db.get.return_value = vehicle
        assert MarketplaceService.get_vehicle_details(mock_db, 1) is None

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, is_available_for_rent=True, is_deleted=False)
        mock_db.get.return_value = vehicle
        result = MarketplaceService.get_vehicle_details(mock_db, 1)
        assert result.id == 1


class TestGetAvailabilityCalendar:
    """Cover get_availability_calendar (lines 252-320)."""

    def test_empty_rentals(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.scalars.return_value.all.return_value = []
        result = MarketplaceService.get_availability_calendar(mock_db, 1)
        assert len(result) >= 30  # default ~30 days inclusive
        assert all(d["available"] for d in result)

    def test_with_dates(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.scalars.return_value.all.return_value = []
        result = MarketplaceService.get_availability_calendar(
            mock_db, 1, from_date=date(2026, 11, 1), to_date=date(2026, 11, 7),
        )
        assert len(result) == 7


class TestCreateRequestFromListing:
    """Cover create_request_from_listing (lines 322-409)."""

    def test_vehicle_not_found(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            MarketplaceService.create_request_from_listing(
                mock_db, 1, 10, 7, "earthworks",
                datetime.now(UTC), datetime.now(UTC) + timedelta(days=1),
            )

    def test_not_available(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, is_available_for_rent=False, name="KAMAZ")
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="not available"):
            MarketplaceService.create_request_from_listing(
                mock_db, 1, 10, 7, "earthworks",
                datetime.now(UTC), datetime.now(UTC) + timedelta(days=1),
            )

    def test_success(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, name="KAMAZ", is_available_for_rent=True, owner_id=None)
        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda r: setattr(r, "id", 1) if not getattr(r, "id", None) else None
        with patch.object(MarketplaceService, "_filter_available", return_value={1}):
            result = MarketplaceService.create_request_from_listing(
                mock_db, 1, 10, 7, "earthworks",
                datetime(2026, 11, 10, tzinfo=UTC), datetime(2026, 11, 11, tzinfo=UTC),
            )
        mock_db.add.assert_called()
        mock_db.commit.assert_called()


class TestFilterAvailable:
    """Cover _filter_available (lines 441-481)."""

    def test_empty_ids(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        result = MarketplaceService._filter_available(mock_db, [], date.today(), date.today())
        assert result == set()

    def test_all_available(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        mock_db.scalars.return_value.all.return_value = []
        result = MarketplaceService._filter_available(mock_db, [1, 2], date.today(), date.today() + timedelta(days=7))
        assert result == {1, 2}


class TestHaversine:
    """Cover _haversine (lines 483-end)."""

    def test_same_point(self):
        from app.services.marketplace_service import MarketplaceService
        assert MarketplaceService._haversine(55.75, 37.62, 55.75, 37.62) == 0.0

    def test_known_distance(self):
        from app.services.marketplace_service import MarketplaceService
        dist = MarketplaceService._haversine(55.7558, 37.6173, 59.9343, 30.3351)
        assert 630 < dist < 640  # km



class TestPublishVehicleBranches:
    """Cover remaining publish_vehicle branches (lines 69-79)."""

    def test_with_all_params(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", company_id=7, is_deleted=False,
            hourly_rate=Decimal("1000"), shift_rate=Decimal("8000"),
            downtime_hourly_rate=None, marketplace_description=None,
            photos=None, base_location_lat=None, base_location_lon=None,
            is_available_for_rent=False, marketplace_commission_agreed=False,
        )
        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda r: None
        MarketplaceService.publish_vehicle(
            mock_db, 1, 7,
            hourly_rate=Decimal("2000"), shift_rate=Decimal("15000"),
            downtime_hourly_rate=Decimal("500"), description="Updated",
            photos=["img1.jpg"], base_location_lat=55.75, base_location_lon=37.62,
        )
        assert vehicle.hourly_rate == Decimal("2000")
        assert vehicle.shift_rate == Decimal("15000")
        assert vehicle.downtime_hourly_rate == Decimal("500")
        assert vehicle.photos == ["img1.jpg"]
        assert vehicle.base_location_lat == 55.75

    def test_existing_rates_used(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", company_id=7, is_deleted=False,
            hourly_rate=Decimal("1000"), shift_rate=None,
            downtime_hourly_rate=None, marketplace_description=None,
            photos=None, base_location_lat=None, base_location_lon=None,
            is_available_for_rent=False, marketplace_commission_agreed=False,
        )
        mock_db.get.return_value = vehicle
        mock_db.refresh.side_effect = lambda r: None
        # No new rates passed, existing hourly_rate should be enough
        MarketplaceService.publish_vehicle(mock_db, 1, 7)
        assert vehicle.is_available_for_rent is True


class TestUnpublishWrongCompany:
    """Cover unpublish wrong company (line 104)."""

    def test_wrong_company(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(company_id=99)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="another company"):
            MarketplaceService.unpublish_vehicle(mock_db, 1, 7)


class TestUpdateListingWrongCompany:
    """Cover update_listing wrong company (line 124)."""

    def test_wrong_company(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(company_id=99)
        mock_db.get.return_value = vehicle
        with pytest.raises(ValueError, match="another company"):
            MarketplaceService.update_listing(mock_db, 1, 7, hourly_rate=100)


class TestAvailabilityCalendarWithRentals:
    """Cover get_availability_calendar with busy dates (lines 290-301)."""

    def test_with_busy_dates(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        today = date.today()
        rental = SimpleNamespace(
            id=1, status="active",
            items=[SimpleNamespace(vehicle_id=1)],
            start_date=datetime.combine(today, datetime.min.time()),
            end_date=datetime.combine(today + timedelta(days=2), datetime.max.time()),
        )
        mock_db.scalars.return_value.all.return_value = [rental]
        result = MarketplaceService.get_availability_calendar(
            mock_db, 1, from_date=today, to_date=today + timedelta(days=5),
        )
        # First 3 days should be busy
        busy_days = [d for d in result if not d["available"]]
        assert len(busy_days) == 3


class TestCreateRequestNotAvailablePeriod:
    """Cover create_request period not available (line 353)."""

    def test_period_not_available(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, name="KAMAZ", is_available_for_rent=True)
        mock_db.get.return_value = vehicle
        with patch.object(MarketplaceService, "_filter_available", return_value=set()):
            with pytest.raises(ValueError, match="not available for the selected period"):
                MarketplaceService.create_request_from_listing(
                    mock_db, 1, 10, 7, "earthworks",
                    datetime(2026, 11, 10, tzinfo=UTC), datetime(2026, 11, 11, tzinfo=UTC),
                )


class TestNotifyOwnerNewRequest:
    """Cover _notify_owner_new_request (lines 415-438)."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(name="KAMAZ")
        request = SimpleNamespace(
            id=1, work_type="earthworks",
            planned_start=datetime(2026, 11, 10, tzinfo=UTC),
            planned_end=datetime(2026, 11, 11, tzinfo=UTC),
        )
        mock_email = MagicMock()
        with patch("app.services.email_service.email_service", mock_email):
            await MarketplaceService._notify_owner_new_request(
                "owner@test.com", "Owner", vehicle, request,
            )
        mock_email.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_error_logged(self):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(name="KAMAZ")
        request = SimpleNamespace(
            id=1, work_type="earthworks",
            planned_start=datetime(2026, 11, 10, tzinfo=UTC),
            planned_end=datetime(2026, 11, 11, tzinfo=UTC),
        )
        mock_email = MagicMock()
        mock_email.send_email.side_effect = Exception("SMTP fail")
        with patch("app.services.email_service.email_service", mock_email):
            # Should not raise
            await MarketplaceService._notify_owner_new_request(
                "owner@test.com", "Owner", vehicle, request,
            )


class TestFilterAvailableWithBusy:
    """Cover _filter_available with busy vehicles (lines 475-478)."""

    def test_some_busy(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        rental = SimpleNamespace(
            items=[SimpleNamespace(vehicle_id=1)],
        )
        mock_db.scalars.return_value.all.return_value = [rental]
        result = MarketplaceService._filter_available(
            mock_db, [1, 2], date.today(), date.today() + timedelta(days=7),
        )
        assert 1 not in result
        assert 2 in result



class TestAvailabilityCalendarMixedVehicles:
    """Cover line 293: skip items with different vehicle_id."""

    def test_skip_other_vehicle_items(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        today = date.today()
        # Rental has item for vehicle_id=2, but we query vehicle_id=1
        rental = SimpleNamespace(
            id=1, status="active",
            items=[SimpleNamespace(vehicle_id=2)],  # different vehicle
            start_date=datetime.combine(today, datetime.min.time()),
            end_date=datetime.combine(today + timedelta(days=2), datetime.max.time()),
        )
        mock_db.scalars.return_value.all.return_value = [rental]
        result = MarketplaceService.get_availability_calendar(
            mock_db, 1, from_date=today, to_date=today + timedelta(days=5),
        )
        # All days should be available since item is for vehicle 2
        assert all(d["available"] for d in result)


class TestCreateRequestWithOwnerNotification:
    """Cover lines 390-404: owner notification with event loop."""

    @pytest.mark.asyncio
    async def test_with_owner_and_loop(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, name="KAMAZ", is_available_for_rent=True, owner_id=5)
        owner = SimpleNamespace(id=5, email="owner@test.com", name="Owner Name")
        mock_db.get.side_effect = lambda model, obj_id: vehicle if obj_id == 1 else owner
        mock_db.refresh.side_effect = lambda r: setattr(r, "id", 1) if not getattr(r, "id", None) else None

        with patch.object(MarketplaceService, "_filter_available", return_value={1}), \
             patch.object(MarketplaceService, "_notify_owner_new_request", new_callable=AsyncMock) as mock_notify:
            result = MarketplaceService.create_request_from_listing(
                mock_db, 1, 10, 7, "earthworks",
                datetime(2026, 11, 10, tzinfo=UTC), datetime(2026, 11, 11, tzinfo=UTC),
            )
        # Notification task was created (may or may not have been awaited)
        assert result is not None

    def test_no_event_loop(self, mock_db):
        from app.services.marketplace_service import MarketplaceService
        vehicle = SimpleNamespace(id=1, name="KAMAZ", is_available_for_rent=True, owner_id=5)
        owner = SimpleNamespace(id=5, email=None, name="Owner")
        call_count = {"n": 0}
        def mock_get(model, obj_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return vehicle
            return owner
        mock_db.get.side_effect = mock_get
        mock_db.refresh.side_effect = lambda r: setattr(r, "id", 1) if not getattr(r, "id", None) else None

        with patch.object(MarketplaceService, "_filter_available", return_value={1}):
            result = MarketplaceService.create_request_from_listing(
                mock_db, 1, 10, 7, "earthworks",
                datetime(2026, 11, 10, tzinfo=UTC), datetime(2026, 11, 11, tzinfo=UTC),
            )
        assert result is not None
