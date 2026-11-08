"""Tests for PublicService core marketplace methods with real logic coverage."""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def svc():
    from app.services.public_service import PublicService

    return PublicService()


@pytest.fixture
def db():
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.flush = MagicMock()
    session.add = MagicMock()
    return session


class TestCreateRequestFromListing:
    """Tests for create_request_from_listing (119 lines)."""

    def test_vehicle_not_found(self, svc, db):
        data = SimpleNamespace(
            planned_start="2026-11-10T08:00:00",
            planned_end="2026-11-10T18:00:00",
            contact_name="Test",
            contact_phone="+79990000000",
            contact_email=None,
            work_type="earthworks",
            comment="",
        )
        with patch("app.services.marketplace_service.marketplace_service") as mock_mp:
            mock_mp.get_vehicle_details.return_value = None
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc:
                svc.create_request_from_listing(db, 999, data)
            assert exc.value.status_code == 404

    def test_invalid_datetime_format(self, svc, db):
        data = SimpleNamespace(
            planned_start="not-a-date",
            planned_end="2026-11-10T18:00:00",
            contact_name="Test",
            contact_phone="+79990000000",
            contact_email=None,
            work_type="earthworks",
            comment="",
        )
        vehicle = SimpleNamespace(company_id=1, name="Excavator")
        with patch("app.services.marketplace_service.marketplace_service") as mock_mp:
            mock_mp.get_vehicle_details.return_value = vehicle
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc:
                svc.create_request_from_listing(db, 1, data)
            assert exc.value.status_code == 400

    def test_planned_end_before_start(self, svc, db):
        data = SimpleNamespace(
            planned_start="2026-11-10T18:00:00",
            planned_end="2026-11-10T08:00:00",
            contact_name="Test",
            contact_phone="+79990000000",
            contact_email=None,
            work_type="earthworks",
            comment="",
        )
        vehicle = SimpleNamespace(company_id=1, name="Excavator")
        with patch("app.services.marketplace_service.marketplace_service") as mock_mp:
            mock_mp.get_vehicle_details.return_value = vehicle
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc:
                svc.create_request_from_listing(db, 1, data)
            assert exc.value.status_code == 400
            assert "planned_end must be after planned_start" in str(exc.value.detail)

    def test_creates_new_client_contractor(self, svc, db):
        data = SimpleNamespace(
            planned_start="2026-11-10T08:00:00",
            planned_end="2026-11-10T18:00:00",
            contact_name="New Client",
            contact_phone="+79991111111",
            contact_email="new@test.com",
            work_type="crane",
            comment="Urgent",
        )
        vehicle = SimpleNamespace(company_id=1, name="Crane K-25")
        mock_request = SimpleNamespace(id=42, status="new")

        # No existing client found
        db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.services.marketplace_service.marketplace_service") as mock_mp:
            mock_mp.get_vehicle_details.return_value = vehicle
            mock_mp.create_request_from_listing.return_value = mock_request

            result = svc.create_request_from_listing(db, 1, data)

        assert result.request_id == 42
        assert result.vehicle_name == "Crane K-25"
        assert "Заявка #42 создана" in result.message
        # New contractor was added
        db.add.assert_called()
        db.flush.assert_called()

    def test_reuses_existing_client_by_email(self, svc, db):
        data = SimpleNamespace(
            planned_start="2026-11-10T08:00:00",
            planned_end="2026-11-10T18:00:00",
            contact_name="Existing",
            contact_phone=None,
            contact_email="exist@test.com",
            work_type="crane",
            comment="",
        )
        vehicle = SimpleNamespace(company_id=1, name="Crane")
        existing_client = SimpleNamespace(id=10)
        mock_request = SimpleNamespace(id=50, status="processing")

        db.query.return_value.filter.return_value.first.return_value = existing_client

        with patch("app.services.marketplace_service.marketplace_service") as mock_mp:
            mock_mp.get_vehicle_details.return_value = vehicle
            mock_mp.create_request_from_listing.return_value = mock_request

            result = svc.create_request_from_listing(db, 1, data)

        assert result.request_id == 50
        # Should NOT add new contractor
        db.add.assert_not_called()

    def test_internal_error_returns_500(self, svc, db):
        data = SimpleNamespace(
            planned_start="2026-11-10T08:00:00",
            planned_end="2026-11-10T18:00:00",
            contact_name="Test",
            contact_phone="+79990000000",
            contact_email=None,
            work_type="crane",
            comment="",
        )
        vehicle = SimpleNamespace(company_id=1, name="Crane")

        with patch("app.services.marketplace_service.marketplace_service") as mock_mp:
            mock_mp.get_vehicle_details.return_value = vehicle
            mock_mp.create_request_from_listing.side_effect = RuntimeError("boom")

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc:
                svc.create_request_from_listing(db, 1, data)
            assert exc.value.status_code == 500


class TestRespondToMarketplaceRequest:
    """Tests for respond_to_marketplace_request (132 lines)."""

    @pytest.mark.asyncio
    async def test_request_not_found(self, svc, db):
        db.get.return_value = None
        user = SimpleNamespace(id=1, full_name="Admin", email="a@b.com", company=None)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(db, 1, 999, 1, user)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_request_not_marketplace(self, svc, db):
        req = SimpleNamespace(source_channel="manual", status="new", company_id=2)
        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else None
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(db, 1, 1, 1, SimpleNamespace(id=1))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_request_closed_cannot_respond(self, svc, db):
        req = SimpleNamespace(
            source_channel="marketplace", status="completed", company_id=2
        )
        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else None
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(db, 1, 1, 1, SimpleNamespace(id=1))
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_cannot_respond_own_request(self, svc, db):
        req = SimpleNamespace(source_channel="marketplace", status="new", company_id=1)
        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else None
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(db, 1, 1, 1, SimpleNamespace(id=1))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_vehicle_not_available(self, svc, db):
        req = SimpleNamespace(source_channel="marketplace", status="new", company_id=2)
        vehicle = SimpleNamespace(company_id=1, status="maintenance", name="Broken")
        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else vehicle
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(db, 1, 1, 1, SimpleNamespace(id=1))
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_no_commission_agreement(self, svc, db):
        req = SimpleNamespace(source_channel="marketplace", status="new", company_id=2)
        vehicle = SimpleNamespace(
            company_id=1,
            status="active",
            name="Truck",
            marketplace_commission_agreed=False,
        )
        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else vehicle
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(db, 1, 1, 1, SimpleNamespace(id=1))
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_already_responded(self, svc, db):
        req = SimpleNamespace(source_channel="marketplace", status="new", company_id=2)
        vehicle = SimpleNamespace(
            company_id=1,
            status="active",
            name="Truck",
            marketplace_commission_agreed=True,
        )
        existing_assignment = SimpleNamespace(id=5)

        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else vehicle
        )
        db.execute.return_value.scalar_one_or_none.return_value = existing_assignment

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(db, 1, 1, 1, SimpleNamespace(id=1))
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_successful_response(self, svc, db):
        req = SimpleNamespace(
            source_channel="marketplace",
            status="new",
            company_id=2,
            created_by=10,
            object_address="Москва, ул. Тестовая",
            marketplace_mode="client",
            payment_terms_days=7,
        )
        vehicle = SimpleNamespace(
            company_id=1,
            status="active",
            name="KAMAZ",
            marketplace_commission_agreed=True,
        )
        user = SimpleNamespace(
            id=1,
            full_name="Driver",
            email="d@b.com",
            company=SimpleNamespace(name="MyCompany"),
        )

        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else vehicle
        )
        db.execute.return_value.scalar_one_or_none.return_value = None  # no existing

        mock_notify = AsyncMock()
        mock_ws = AsyncMock()

        with (
            patch("app.services.notification_service.create_notification", mock_notify),
            patch("app.services.websocket_manager.manager") as mock_manager,
        ):
            mock_manager.send_to_user = mock_ws
            result = await svc.respond_to_marketplace_request(db, 1, 1, 1, user)

        assert result["status"] == "pending_approval"
        assert result["vehicle_name"] == "KAMAZ"
        assert "Отклик успешно отправлен" in result["message"]
        db.commit.assert_called_once()
        mock_notify.assert_called_once()
        mock_ws.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_failure_doesnt_block(self, svc, db):
        req = SimpleNamespace(
            source_channel="marketplace",
            status="new",
            company_id=2,
            created_by=10,
            object_address="Addr",
            marketplace_mode="owner_dispatcher",
            payment_terms_days=14,
        )
        vehicle = SimpleNamespace(
            company_id=1,
            status="active",
            name="Bulldozer",
            marketplace_commission_agreed=True,
        )
        user = SimpleNamespace(id=1, full_name="Op", email="o@b.com", company=None)

        db.get.side_effect = lambda model, id: (
            req if model.__name__ == "Request" else vehicle
        )
        db.execute.return_value.scalar_one_or_none.return_value = None

        with (
            patch(
                "app.services.notification_service.create_notification",
                side_effect=Exception("notify fail"),
            ),
            patch("app.services.websocket_manager.manager") as mock_manager,
        ):
            mock_manager.send_to_user = AsyncMock(side_effect=Exception("ws fail"))
            result = await svc.respond_to_marketplace_request(db, 1, 1, 1, user)

        # Still succeeds despite notification failures
        assert result["status"] == "pending_approval"
        db.commit.assert_called_once()


class TestMarketplacePayoutsReport:
    """Tests for marketplace_payouts_report (139 lines)."""

    def test_empty_payouts_returns_excel(self, svc, db):
        db.scalars.return_value.all.return_value = []

        result = svc.marketplace_payouts_report(db, None, None)

        assert result is not None
        assert result is not None
        assert (
            result.media_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_with_date_filters(self, svc, db):
        db.scalars.return_value.all.return_value = []

        result = svc.marketplace_payouts_report(db, "2026-01-01", "2026-12-31")

        assert result is not None

    def test_with_payout_data(self, svc, db):
        from types import SimpleNamespace

        payout = SimpleNamespace(
            id=1,
            payout_date=date(2026, 10, 15),
            gross_amount=Decimal("50000"),
            platform_commission=Decimal("5000"),
            net_amount=Decimal("45000"),
            status="approved",
            created_at=datetime(2026, 10, 15),
            request_id=10,
            vehicle_id=5,
            owner_id=1,
            owner_name="Иванов И.И.",
        )
        db.scalars.return_value.all.return_value = [payout]

        # db.get should return request/vehicle by model type and id
        mock_request = SimpleNamespace(id=10)
        mock_vehicle = SimpleNamespace(name="KAMAZ")

        def mock_get(model, pk):
            if hasattr(model, "__name__"):
                if model.__name__ == "Request":
                    return mock_request
                elif model.__name__ == "Vehicle":
                    return mock_vehicle
            return None

        db.get.side_effect = mock_get

        result = svc.marketplace_payouts_report(db, None, None)

        assert result is not None


class TestExportMarketplaceRequests:
    """Tests for export_marketplace_requests (120 lines)."""

    def test_empty_requests_returns_excel(self, svc, db):
        db.scalars.return_value.all.return_value = []

        result = svc.export_marketplace_requests(db, None)

        assert result is not None

    def test_with_category_filter(self, svc, db):
        db.scalars.return_value.all.return_value = []

        result = svc.export_marketplace_requests(db, category_id=5)

        assert result is not None

    def test_with_request_data(self, svc, db):
        from types import SimpleNamespace

        req = SimpleNamespace(
            id=1,
            vehicle_category_id=3,
            work_type="earthworks",
            object_address="Москва, ул. Ленина",
            planned_start=datetime(2026, 11, 10),
            planned_end=datetime(2026, 11, 15),
            client_rate=Decimal("2500"),
            rate_type="hourly",
            marketplace_mode="client",
            payment_terms_days=7,
            priority="high",
            status="new",
            created_at=datetime(2026, 11, 1),
        )
        mock_cat = SimpleNamespace(name="Экскаваторы")

        def mock_get(model, pk):
            if hasattr(model, "__name__") and model.__name__ == "Category":
                return mock_cat
            return None

        db.get.side_effect = mock_get
        db.scalars.return_value.all.return_value = [req]

        result = svc.export_marketplace_requests(db, None)

        assert result is not None
