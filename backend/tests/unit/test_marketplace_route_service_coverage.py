"""Coverage tests for marketplace_route_service."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.refresh = MagicMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def svc():
    from app.services.marketplace_route_service import MarketplaceRouteService

    return MarketplaceRouteService()


class TestCreateOfferOnRequest:
    """Cover create_offer_on_request (lines 23-135)."""

    def test_request_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            svc.create_offer_on_request(
                mock_db, 1, 999, SimpleNamespace(vehicle_id=1), 1
            )
        assert exc.value.status_code == 404

    def test_vehicle_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(status=RequestStatus.new)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else None

        mock_db.get.side_effect = mock_get
        with pytest.raises(HTTPException) as exc:
            svc.create_offer_on_request(
                mock_db, 1, 1, SimpleNamespace(vehicle_id=999), 1
            )
        assert exc.value.status_code == 404

    def test_commission_not_agreed(self, svc, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(status=RequestStatus.new)
        vehicle = SimpleNamespace(company_id=1, marketplace_commission_agreed=False)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        with pytest.raises(HTTPException) as exc:
            svc.create_offer_on_request(mock_db, 1, 1, SimpleNamespace(vehicle_id=1), 1)
        assert exc.value.status_code == 400

    def test_wrong_company(self, svc, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(status=RequestStatus.new)
        vehicle = SimpleNamespace(company_id=2, marketplace_commission_agreed=True)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        with pytest.raises(HTTPException) as exc:
            svc.create_offer_on_request(mock_db, 1, 1, SimpleNamespace(vehicle_id=1), 1)
        assert exc.value.status_code == 403


class TestListOffersForRequest:
    """Cover list_offers_for_request (lines 137-166)."""

    def test_request_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            svc.list_offers_for_request(mock_db, 999, None, 1)
        assert exc.value.status_code == 404

    def test_success_empty(self, svc, mock_db):
        mock_db.get.return_value = SimpleNamespace(id=1)
        mock_db.scalars.return_value.unique.return_value.all.return_value = []
        result = svc.list_offers_for_request(mock_db, 1, None, 1)
        assert result == []


class TestGetOfferDetails:
    """Cover get_offer_details (lines 168-186)."""

    def test_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            None
        )
        with pytest.raises(HTTPException) as exc:
            svc.get_offer_details(mock_db, 999)
        assert exc.value.status_code == 404


class TestAcceptOffer:
    """Cover accept_offer (lines 188-273)."""

    def test_offer_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            None
        )
        user = SimpleNamespace(id=1)
        with pytest.raises(HTTPException) as exc:
            svc.accept_offer(mock_db, 1, 999, 1, user)
        assert exc.value.status_code == 404

    def test_wrong_status(self, svc, mock_db):
        from fastapi import HTTPException

        offer = SimpleNamespace(status="accepted", request=None)
        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            offer
        )
        user = SimpleNamespace(id=1)
        with pytest.raises(HTTPException) as exc:
            svc.accept_offer(mock_db, 1, 1, 1, user)
        assert exc.value.status_code == 400


class TestRejectOffer:
    """Cover reject_offer (lines 275-331)."""

    def test_offer_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
            None
        )
        user = SimpleNamespace(id=1)
        data = SimpleNamespace(rejection_reason="Too expensive")
        with pytest.raises(HTTPException) as exc:
            svc.reject_offer(mock_db, 1, 999, data, 1, user)
        assert exc.value.status_code == 404


class TestPublishRequest:
    """Cover publish_request (lines 491-545)."""

    def test_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.get.return_value = None
        user = SimpleNamespace(id=1)
        with pytest.raises(HTTPException) as exc:
            svc.publish_request(mock_db, 1, 999, user)
        assert exc.value.status_code == 404

    def test_wrong_company(self, svc, mock_db):
        from fastapi import HTTPException

        request = SimpleNamespace(company_id=2)
        mock_db.get.return_value = request
        user = SimpleNamespace(id=1)
        with pytest.raises(HTTPException) as exc:
            svc.publish_request(mock_db, 1, 1, user)
        assert exc.value.status_code == 403

    def test_already_published(self, svc, mock_db):
        request = SimpleNamespace(
            id=1,
            company_id=1,
            is_published=True,
            published_at=datetime.now(UTC),
            status=SimpleNamespace(value="new"),
        )
        mock_db.get.return_value = request
        user = SimpleNamespace(id=1)
        result = svc.publish_request(mock_db, 1, 1, user)
        assert result.is_published is True

    def test_success(self, svc, mock_db):
        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(
            id=1,
            company_id=1,
            is_published=False,
            published_at=None,
            status=RequestStatus.new,
        )
        mock_db.get.return_value = request
        user = SimpleNamespace(id=1)
        result = svc.publish_request(mock_db, 1, 1, user)
        assert result.is_published is True
        mock_db.commit.assert_called()


class TestUnpublishRequest:
    """Cover unpublish_request (lines 547-581)."""

    def test_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.get.return_value = None
        user = SimpleNamespace(id=1)
        with pytest.raises(HTTPException) as exc:
            svc.unpublish_request(mock_db, 1, 999, user)
        assert exc.value.status_code == 404

    def test_not_published(self, svc, mock_db):
        request = SimpleNamespace(
            id=1, company_id=1, is_published=False, published_at=None
        )
        mock_db.get.return_value = request
        user = SimpleNamespace(id=1)
        result = svc.unpublish_request(mock_db, 1, 1, user)
        assert result.is_published is False

    def test_success(self, svc, mock_db):
        request = SimpleNamespace(
            id=1, company_id=1, is_published=True, published_at=datetime.now(UTC)
        )
        mock_db.get.return_value = request
        user = SimpleNamespace(id=1)
        result = svc.unpublish_request(mock_db, 1, 1, user)
        assert result.is_published is False
        mock_db.commit.assert_called()


class TestCreateSurplusRequest:
    """Cover create_surplus_request (lines 356-448)."""

    def test_vehicle_not_found(self, svc, mock_db):
        from fastapi import HTTPException

        mock_db.get.return_value = None
        user = SimpleNamespace(id=1)
        data = SimpleNamespace(
            vehicle_id=999,
            dispatcher_commission_pct=10,
            offered_price=Decimal("5000"),
            price_type="per_hour",
            shift_duration_hours=None,
            work_type="earthworks",
            object_address="Moscow",
            region="moscow",
            planned_start=datetime.now(UTC),
            planned_end=datetime.now(UTC),
            comment="test",
        )
        with pytest.raises(HTTPException) as exc:
            svc.create_surplus_request(mock_db, 1, data, user)
        assert exc.value.status_code == 404

    def test_wrong_company(self, svc, mock_db):
        from fastapi import HTTPException

        vehicle = SimpleNamespace(company_id=2, name="KAMAZ", category_id=None)
        mock_db.get.return_value = vehicle
        user = SimpleNamespace(id=1)
        data = SimpleNamespace(
            vehicle_id=1,
            dispatcher_commission_pct=10,
            offered_price=Decimal("5000"),
            price_type="fixed",
            shift_duration_hours=None,
            work_type="earthworks",
            object_address="Moscow",
            region="moscow",
            planned_start=datetime.now(UTC),
            planned_end=datetime.now(UTC),
            comment="test",
        )
        with pytest.raises(HTTPException) as exc:
            svc.create_surplus_request(mock_db, 1, data, user)
        assert exc.value.status_code == 403

    def test_success(self, svc, mock_db):
        vehicle = SimpleNamespace(company_id=1, name="KAMAZ", category_id=1)
        mock_db.get.return_value = vehicle
        user = SimpleNamespace(id=1)
        data = SimpleNamespace(
            vehicle_id=1,
            dispatcher_commission_pct=10,
            offered_price=Decimal("5000"),
            price_type="per_hour",
            shift_duration_hours=8,
            work_type="earthworks",
            object_address="Moscow",
            region="moscow",
            planned_start=datetime.now(UTC),
            planned_end=datetime.now(UTC),
            comment="test",
        )
        result = svc.create_surplus_request(mock_db, 1, data, user)
        assert result["vehicle_name"] == "KAMAZ"
        assert result["dispatcher_commission_pct"] == 10
        assert result["is_published"] is True
        mock_db.commit.assert_called()


class TestListMarketplaceRequests:
    """Cover list_marketplace_requests (lines 583-end)."""

    def test_empty(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = (
            []
        )
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.list_marketplace_requests(mock_db, 1, 0, 20, None, None)
        assert result == []
