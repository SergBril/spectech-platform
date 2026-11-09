"""Extra tests for marketplace_route_service missing lines -> 100%."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.marketplace_route_service import MarketplaceRouteService


@pytest.fixture
def svc():
    return MarketplaceRouteService()


class TestCreateOfferMaxNotification:
    """Cover lines 112-122: MAX messenger notification on offer creation."""

    def test_max_notification_success(self, svc):
        mock_db = MagicMock()
        request_obj = MagicMock()
        request_obj.id = 1
        request_obj.status = "new"
        request_obj.company_id = 7
        request_obj.work_type = "earthworks"
        vehicle = MagicMock()
        vehicle.company_id = 5
        vehicle.id = 10
        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if "Request" in name: return request_obj
            if "Vehicle" in name or "vehicle" in str(model).lower(): return vehicle
            if "Company" in name: return company
            if "Category" in name: return category
            if id == 10: return vehicle
            return None
        company = MagicMock()
        company.name = "OOO Test"
        category = MagicMock()
        category.name = "Test Category"
        mock_db.get = MagicMock(side_effect=get_se)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        def refresh_side_effect(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 100
        mock_db.refresh = MagicMock(side_effect=refresh_side_effect)
        data = SimpleNamespace(
            vehicle_id=10, offered_price=5000, price_type="hourly", commission_agreed=True,
            currency="RUB", estimated_arrival_minutes=None, distance_km=None, message=None,
        )
        with patch("app.services.max_messenger_service.max_messenger_service") as mock_max:
            mock_max.notify_company_dispatchers = AsyncMock()
            result = svc.create_offer_on_request(mock_db, company_id=5, request_id=1, data=data, current_company_id=5)
        assert result is not None

    def test_max_notification_no_loop(self, svc):
        """Line 121-122: RuntimeError when no event loop."""
        mock_db = MagicMock()
        request_obj = MagicMock()
        request_obj.id = 1
        request_obj.status = "new"
        request_obj.company_id = 7
        request_obj.work_type = "earthworks"
        vehicle = MagicMock()
        vehicle.company_id = 5
        vehicle.id = 10
        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if "Request" in name: return request_obj
            if "Vehicle" in name or "vehicle" in str(model).lower(): return vehicle
            if "Company" in name: return company
            if "Category" in name: return category
            # Fallback: if id matches vehicle id, return vehicle
            if id == 10: return vehicle
            return None
        company = MagicMock()
        company.name = "OOO Test"
        category = MagicMock()
        category.name = "Test Category"
        mock_db.get = MagicMock(side_effect=get_se)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        def refresh_side_effect(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 100
        mock_db.refresh = MagicMock(side_effect=refresh_side_effect)
        data = SimpleNamespace(
            vehicle_id=10, offered_price=5000, price_type="hourly", commission_agreed=True,
            currency="RUB", estimated_arrival_minutes=None, distance_km=None, message=None,
        )
        with (
            patch("app.services.max_messenger_service.max_messenger_service"),
            patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")),
        ):
            result = svc.create_offer_on_request(mock_db, company_id=5, request_id=1, data=data, current_company_id=5)
        assert result is not None


class TestListOffersWithStatus:
    """Cover line 162: status filter."""

    def test_list_with_status_filter(self, svc):
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.unique.return_value.all.return_value = []
        mock_db.scalars.return_value = mock_result
        result = svc.list_offers_for_request(mock_db, request_id=1, status="pending", current_company_id=7)
        assert isinstance(result, list)


class TestAcceptOfferRejectOthers:
    """Cover lines 259-261: reject other offers on accept."""

    def test_other_offers_rejected(self, svc):
        mock_db = MagicMock()
        offer = MagicMock()
        offer.id = 1
        offer.status = "pending"
        offer.request_id = 1
        offer.owner_company_id = 5
        offer.vehicle_id = 10
        offer.offered_price = 5000
        offer.price_type = "hourly"
        offer.created_at = datetime(2026, 11, 9)
        offer.updated_at = datetime(2026, 11, 9)
        offer.reviewed_at = None
        offer.rejection_reason = None
        offer.currency = "RUB"
        offer.estimated_arrival_minutes = None
        offer.distance_km = None
        offer.message = None
        offer.operator_id = None
        offer.reviewed_by_id = None
        request_obj = MagicMock()
        request_obj.created_by = 1
        request_obj.company_id = 7
        request_obj.status = "new"
        offer.request = request_obj
        other_offer = MagicMock()
        other_offer.status = "pending"
        current_user = SimpleNamespace(id=1)
        company = MagicMock()
        company.name = "OOO Test"
        vehicle = MagicMock()
        vehicle.category_id = None
        vehicle.name = "Test Vehicle"
        vehicle.id = 10
        # db.query().options().filter().first() -> offer (for initial lookup)
        # db.query().filter().all() -> [other_offer] (for rejecting others)
        filter_mock = MagicMock()
        filter_mock.first.return_value = offer
        filter_mock.all.return_value = [other_offer]
        options_mock = MagicMock()
        options_mock.filter.return_value = filter_mock
        mock_db.query.return_value.options.return_value = options_mock
        mock_db.query.return_value.filter.return_value = filter_mock
        # db.get for company/vehicle in _build_offer_response
        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if "Company" in name: return company
            if "Vehicle" in name: return vehicle
            return None
        mock_db.get = MagicMock(side_effect=get_se)
        mock_db.commit = MagicMock()
        def refresh_side_effect(obj):
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 100
        mock_db.refresh = MagicMock(side_effect=refresh_side_effect)
        result = svc.accept_offer(mock_db, company_id=7, offer_id=1, current_company_id=7, current_user=current_user)
        assert other_offer.status == "rejected"
        assert other_offer.rejection_reason == "Another offer was accepted"


class TestRejectOfferValidation:
    """Cover lines 301, 309-310: reject validation."""

    def test_wrong_status(self, svc):
        mock_db = MagicMock()
        offer = MagicMock()
        offer.status = "accepted"
        mock_db.get.return_value = offer
        current_user = SimpleNamespace(id=1)
        data = SimpleNamespace(rejection_reason="test")
        with pytest.raises(HTTPException, match="Cannot reject"):
            svc.reject_offer(mock_db, company_id=7, offer_id=1, data=data, current_company_id=7, current_user=current_user)

    def test_access_denied(self, svc):
        mock_db = MagicMock()
        offer = MagicMock()
        offer.status = "pending"
        request_obj = MagicMock()
        request_obj.created_by = 99
        request_obj.company_id = 99
        offer.request = request_obj
        mock_db.get.return_value = offer
        current_user = SimpleNamespace(id=1)
        data = SimpleNamespace(rejection_reason="test")
        with pytest.raises(HTTPException, match="reject"):
            svc.reject_offer(mock_db, company_id=7, offer_id=1, data=data, current_company_id=7, current_user=current_user)


class TestGetMatchingVehicles:
    """Cover lines 340-350: matching vehicles."""

    def test_request_not_found(self, svc):
        mock_db = MagicMock()
        mock_db.get.return_value = None
        with pytest.raises(HTTPException, match="Request not found"):
            svc.get_matching_vehicles_for_request(mock_db, company_id=7, request_id=999)

    def test_success(self, svc):
        mock_db = MagicMock()
        request_obj = MagicMock()
        request_obj.id = 1
        mock_db.get.return_value = request_obj
        with patch("app.services.marketplace.vehicle_matcher.vehicle_matcher") as mock_matcher:
            mock_matcher.find_matching_vehicles.return_value = [{"vehicle_id": 10, "score": 85}]
            result = svc.get_matching_vehicles_for_request(mock_db, company_id=7, request_id=1)
        assert result["total_matches"] == 1


class TestPublishRequestAccessDenied:
    """Cover line 556: access denied on publish."""

    def test_wrong_company(self, svc):
        mock_db = MagicMock()
        request_obj = MagicMock()
        request_obj.company_id = 99
        mock_db.get.return_value = request_obj
        with pytest.raises(HTTPException, match="Нет доступа"):
            svc.publish_request(mock_db, company_id=7, request_id=1)


class TestListMarketplaceRequestsFilters:
    """Cover lines 622, 625, 629, 639-658: filters and response building."""

    def test_with_all_filters(self, svc):
        mock_db = MagicMock()
        req = MagicMock()
        req.id = 1
        req.work_type = "earthworks"
        req.object_address = "Moscow"
        req.region = "Москва"
        req.vehicle_category_id = 3
        req.status = "published"
        req.created_at = datetime(2026, 11, 9)
        req.is_published = True
        req.description = "Test"
        req.price_budget = 10000
        req.price_type = "fixed"
        req.start_date = datetime(2026, 11, 10)
        req.end_date = datetime(2026, 11, 20)
        req.planned_start = datetime(2026, 11, 10)
        req.planned_end = datetime(2026, 11, 20)
        req.shift_duration_hours = 8
        req.client_rate = 5000
        req.rate_type = "hourly"
        req.estimated_amount = 40000
        req.priority = "normal"
        req.published_at = datetime(2026, 11, 9)
        category = MagicMock()
        category.name = "Экскаватор"
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = [req]
        count_result = MagicMock()
        count_result.count.return_value = 2
        call_count = [0]
        def execute_se(stmt):
            call_count[0] += 1
            if call_count[0] == 1:
                return exec_result
            return count_result
        mock_db.execute = MagicMock(side_effect=execute_se)
        mock_db.query.return_value.filter.return_value = count_result
        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if "Category" in name: return category
            return None
        mock_db.get = MagicMock(side_effect=get_se)
        result = svc.list_marketplace_requests(
            mock_db, company_id=7, skip=0, limit=50,
            category_id=3, region="Москва",
        )
        assert isinstance(result, list)
