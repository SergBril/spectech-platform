"""Tests for MarketplaceRouteService."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service():
    from app.services.marketplace_route_service import MarketplaceRouteService

    return MarketplaceRouteService()


class TestCreateOfferOnRequest:
    """Cover create_offer_on_request (lines 21-134)."""

    def test_request_not_found(self, service, mock_db):
        from fastapi import HTTPException

        mock_db.get.return_value = None
        data = SimpleNamespace(vehicle_id=1)
        with pytest.raises(HTTPException) as exc:
            service.create_offer_on_request(mock_db, 1, 999, data, 1)
        assert exc.value.status_code == 404

    def test_request_status_not_allowed(self, service, mock_db):
        from fastapi import HTTPException

        request = SimpleNamespace(status="completed")
        mock_db.get.return_value = request
        data = SimpleNamespace(vehicle_id=1)
        with pytest.raises(HTTPException) as exc:
            service.create_offer_on_request(mock_db, 1, 1, data, 1)
        assert exc.value.status_code == 400

    def test_vehicle_not_found(self, service, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(status=RequestStatus.new)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request
            return None

        mock_db.get.side_effect = mock_get
        data = SimpleNamespace(vehicle_id=999)
        with pytest.raises(HTTPException) as exc:
            service.create_offer_on_request(mock_db, 1, 1, data, 1)
        assert exc.value.status_code == 404

    def test_commission_not_agreed(self, service, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(status=RequestStatus.new)
        vehicle = SimpleNamespace(company_id=1, marketplace_commission_agreed=False)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request
            return vehicle

        mock_db.get.side_effect = mock_get
        # No existing offer
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        data = SimpleNamespace(vehicle_id=1)
        with pytest.raises(HTTPException) as exc:
            service.create_offer_on_request(mock_db, 1, 1, data, 1)
        assert exc.value.status_code == 400
        assert "commission" in str(exc.value.detail).lower()

    def test_vehicle_not_owned(self, service, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(status=RequestStatus.new)
        vehicle = SimpleNamespace(company_id=2, marketplace_commission_agreed=True)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request
            return vehicle

        mock_db.get.side_effect = mock_get
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        data = SimpleNamespace(vehicle_id=1)
        with pytest.raises(HTTPException) as exc:
            service.create_offer_on_request(mock_db, 1, 1, data, 1)
        assert exc.value.status_code == 403

    def test_duplicate_offer(self, service, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(status=RequestStatus.new)
        vehicle = SimpleNamespace(company_id=1, marketplace_commission_agreed=True)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request
            return vehicle

        mock_db.get.side_effect = mock_get
        existing = SimpleNamespace(id=5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = existing
        mock_db.query.return_value = mock_query
        data = SimpleNamespace(vehicle_id=1)
        with pytest.raises(HTTPException) as exc:
            service.create_offer_on_request(mock_db, 1, 1, data, 1)
        assert exc.value.status_code == 400
        assert "already" in str(exc.value.detail).lower()


class TestAcceptOffer:
    """Cover accept_offer (lines 186-272)."""

    def test_offer_not_found(self, service, mock_db):
        from fastapi import HTTPException

        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        user = SimpleNamespace(id=5)
        with pytest.raises(HTTPException) as exc:
            service.accept_offer(mock_db, 1, 999, 1, user)
        assert exc.value.status_code == 404

    def test_offer_not_pending(self, service, mock_db):
        from fastapi import HTTPException

        offer = SimpleNamespace(status="accepted", request=None)
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = offer
        mock_db.query.return_value = mock_query
        user = SimpleNamespace(id=5)
        with pytest.raises(HTTPException) as exc:
            service.accept_offer(mock_db, 1, 1, 1, user)
        assert exc.value.status_code == 400

    def test_access_denied(self, service, mock_db):
        from fastapi import HTTPException

        request_obj = SimpleNamespace(created_by=99, company_id=2)
        offer = SimpleNamespace(status="pending", request=request_obj)
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = offer
        mock_db.query.return_value = mock_query
        user = SimpleNamespace(id=5)
        with pytest.raises(HTTPException) as exc:
            service.accept_offer(mock_db, 1, 1, 1, user)
        assert exc.value.status_code == 403


class TestRejectOffer:
    """Cover reject_offer (lines 273-330)."""

    def test_reject_success(self, service, mock_db):
        request_obj = SimpleNamespace(created_by=5, company_id=1)
        offer = SimpleNamespace(
            status="pending",
            request=request_obj,
            id=1,
            request_id=10,
            rejection_reason=None,
            reviewed_by_id=None,
            reviewed_at=None,
        )
        mock_query = MagicMock()
        mock_query.options.return_value.filter.return_value.first.return_value = offer
        mock_db.query.return_value = mock_query
        user = SimpleNamespace(id=5)
        data = SimpleNamespace(rejection_reason="Не подходит техника")

        with patch.object(service, "_build_offer_response", return_value={"id": 1}):
            service.reject_offer(mock_db, 1, 1, data, 1, user)

        assert offer.status == "rejected"
        assert offer.rejection_reason == "Не подходит техника"
        mock_db.commit.assert_called_once()


class TestPublishRequest:
    """Cover publish_request (lines 489-544)."""

    def test_request_not_found(self, service, mock_db):
        from fastapi import HTTPException

        mock_db.get.return_value = None
        user = SimpleNamespace(id=5)
        with pytest.raises(HTTPException) as exc:
            service.publish_request(mock_db, 1, 999, user)
        assert exc.value.status_code == 404

    def test_access_denied(self, service, mock_db):
        from fastapi import HTTPException

        request = SimpleNamespace(company_id=2)
        mock_db.get.return_value = request
        user = SimpleNamespace(id=5)
        with pytest.raises(HTTPException) as exc:
            service.publish_request(mock_db, 1, 1, user)
        assert exc.value.status_code == 403

    def test_already_published(self, service, mock_db):
        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(
            company_id=1,
            status=RequestStatus.new,
            is_published=True,
            published_at=datetime(2026, 11, 1, tzinfo=UTC),
            id=1,
        )
        mock_db.get.return_value = request
        user = SimpleNamespace(id=5)
        service.publish_request(mock_db, 1, 1, user)
        assert result.is_published is True
        mock_db.commit.assert_not_called()

    def test_publish_success(self, service, mock_db):
        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(
            company_id=1,
            status=RequestStatus.new,
            is_published=False,
            published_at=None,
            id=1,
        )
        mock_db.get.return_value = request
        user = SimpleNamespace(id=5)
        service.publish_request(mock_db, 1, 1, user)
        assert request.is_published is True
        assert request.published_at is not None
        mock_db.commit.assert_called_once()
        assert result.is_published is True

    def test_cannot_publish_completed(self, service, mock_db):
        from fastapi import HTTPException

        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(company_id=1, status=RequestStatus.completed)
        mock_db.get.return_value = request
        user = SimpleNamespace(id=5)
        with pytest.raises(HTTPException) as exc:
            service.publish_request(mock_db, 1, 1, user)
        assert exc.value.status_code == 400


class TestUnpublishRequest:
    """Cover unpublish_request (lines 545-580)."""

    def test_unpublish_success(self, service, mock_db):
        from app.models.dispatch import RequestStatus

        request = SimpleNamespace(
            company_id=1,
            status=RequestStatus.new,
            is_published=True,
            published_at=datetime.now(UTC),
            id=1,
        )
        mock_db.get.return_value = request
        user = SimpleNamespace(id=5)
        service.unpublish_request(mock_db, 1, 1, user)
        assert request.is_published is False
        mock_db.commit.assert_called_once()


class TestCreateOfferSuccess:
    """Cover create_offer_on_request success path (lines 85-136)."""

    def test_create_offer_success(self, service, mock_db):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        from app.models.dispatch import RequestStatus

        request_obj = SimpleNamespace(status=RequestStatus.new, company_id=2, id=10)
        vehicle = SimpleNamespace(
            company_id=1, marketplace_commission_agreed=True, name="KAMAZ"
        )
        SimpleNamespace(id=5, request_id=10)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request_obj
            return vehicle

        mock_db.get.side_effect = mock_get
        # No existing offer
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        data = SimpleNamespace(
            vehicle_id=1,
            offered_price=5000.0,
            price_type="per_hour",
            currency="RUB",
            estimated_arrival_minutes=30,
            distance_km=15.0,
            message="Готов выехать",
        )

        with patch.object(service, "_build_offer_response", return_value={"id": 5}):
            service.create_offer_on_request(mock_db, 1, 10, data, 1)

        assert result["id"] == 5
        mock_db.add.assert_called()
        mock_db.commit.assert_called()


class TestAcceptOfferSuccess:
    """Cover accept_offer success path (lines 240-274)."""

    def test_accept_offer_success(self, service, mock_db):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        request_obj = SimpleNamespace(
            created_by=5,
            company_id=1,
            status="new",
            assigned_vehicle_id=None,
            assigned_owner_id=None,
        )
        offer = SimpleNamespace(
            status="pending",
            request=request_obj,
            id=1,
            request_id=10,
            vehicle_id=3,
            owner_company_id=2,
            reviewed_by_id=None,
            reviewed_at=None,
        )

        # First query: find offer, second: find other offers to reject
        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                mq.options.return_value.filter.return_value.first.return_value = offer
            else:
                mq.filter.return_value.all.return_value = []
            return mq

        mock_db.query.side_effect = mock_query
        user = SimpleNamespace(id=5)

        with patch.object(
            service,
            "_build_offer_response",
            return_value={"id": 1, "status": "accepted"},
        ):
            service.accept_offer(mock_db, 1, 1, 1, user)

        assert offer.status == "accepted"
        assert (
            request_obj.status.value == "assigned" or request_obj.status == "assigned"
        )
        mock_db.commit.assert_called()


class TestCreateSurplusRequest:
    """Cover create_surplus_request (lines 366-439)."""

    def test_surplus_request_success(self, service, mock_db):
        from datetime import datetime
        from types import SimpleNamespace

        vehicle = SimpleNamespace(
            id=1, name="Экскаватор JCB", company_id=1, category_id=5
        )
        mock_db.get.return_value = vehicle

        SimpleNamespace(id=100, work_type="earthworks", vehicle_name="Экскаватор JCB")

        # Mock flush to set id
        def mock_flush():
            pass

        mock_db.flush.side_effect = mock_flush

        # After commit, refresh sets the object
        mock_db.refresh.side_effect = lambda obj: (
            setattr(obj, "id", 100) if not hasattr(obj, "work_type") else None
        )

        user = SimpleNamespace(id=5)
        data = SimpleNamespace(
            vehicle_id=1,
            work_type="earthworks",
            object_address="г. Москва, ул. Строителей, 1",
            region="Москва",
            planned_start=datetime(2026, 11, 10, 8, 0),
            planned_end=datetime(2026, 11, 10, 18, 0),
            shift_duration_hours=10,
            offered_price=5000.0,
            price_type="per_hour",
            dispatcher_commission_pct=10,
            comment="Свободная техника",
        )

        # Need to mock Request and RequestStatusLog constructors
        with (
            patch("app.services.marketplace_route_service.Request") as MockRequest,
            patch("app.models.dispatch.RequestStatusLog") as MockLog,
        ):
            mock_req_instance = SimpleNamespace(
                id=100, work_type="earthworks", vehicle_category_id=None
            )
            MockRequest.return_value = mock_req_instance
            MockLog.return_value = SimpleNamespace()

            service.create_surplus_request(mock_db, 1, data, user)

        assert result["id"] == 100
        assert result["vehicle_name"] == "Экскаватор JCB"
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_surplus_vehicle_not_found(self, service, mock_db):
        from types import SimpleNamespace

        from fastapi import HTTPException

        mock_db.get.return_value = None
        user = SimpleNamespace(id=5)
        data = SimpleNamespace(vehicle_id=999)

        with pytest.raises(HTTPException) as exc:
            service.create_surplus_request(mock_db, 1, data, user)
        assert exc.value.status_code == 404

    def test_surplus_vehicle_wrong_company(self, service, mock_db):
        from types import SimpleNamespace

        from fastapi import HTTPException

        vehicle = SimpleNamespace(id=1, company_id=2)
        mock_db.get.return_value = vehicle
        user = SimpleNamespace(id=5)
        data = SimpleNamespace(vehicle_id=1)

        with pytest.raises(HTTPException) as exc:
            service.create_surplus_request(mock_db, 1, data, user)
        assert exc.value.status_code == 403
