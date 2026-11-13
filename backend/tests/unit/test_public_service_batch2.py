"""Coverage tests for PublicService - batch 2."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture
def svc():
    from app.services.public_service import PublicService

    return PublicService()


@pytest.fixture
def mock_db():
    return MagicMock()


class TestCreateRequestFromListing:
    """Cover create_request_from_listing (lines 342-460)."""

    def test_vehicle_not_found(self, svc, mock_db):
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = None
            data = SimpleNamespace(
                planned_start="2026-11-01T08:00:00",
                planned_end="2026-11-01T16:00:00",
                contact_name="Test",
                contact_email="t@t.com",
                contact_phone=None,
                work_type="earthworks",
                comment="test",
            )
            with pytest.raises(HTTPException) as exc:
                svc.create_request_from_listing(mock_db, 999, data)
            assert exc.value.status_code == 404

    def test_invalid_dates(self, svc, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ", company_id=1)
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = vehicle
            data = SimpleNamespace(
                planned_start="bad-date",
                planned_end="2026-11-01T16:00:00",
                contact_name="Test",
                contact_email=None,
                contact_phone=None,
                work_type="earthworks",
                comment=None,
            )
            with pytest.raises(HTTPException) as exc:
                svc.create_request_from_listing(mock_db, 1, data)
            assert exc.value.status_code == 400

    def test_start_after_end(self, svc, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ", company_id=1)
        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = vehicle
            data = SimpleNamespace(
                planned_start="2026-11-02T08:00:00",
                planned_end="2026-11-01T16:00:00",
                contact_name="Test",
                contact_email=None,
                contact_phone=None,
                work_type="earthworks",
                comment=None,
            )
            with pytest.raises(HTTPException) as exc:
                svc.create_request_from_listing(mock_db, 1, data)
            assert exc.value.status_code == 400

    def test_success_new_client(self, svc, mock_db):
        vehicle = SimpleNamespace(id=1, name="KAMAZ", company_id=1)
        request_obj = SimpleNamespace(id=42, status=SimpleNamespace(value="new"))

        # No existing client found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.flush.side_effect = lambda: None

        with patch("app.services.marketplace_service.marketplace_service") as mock_ms:
            mock_ms.get_vehicle_details.return_value = vehicle
            mock_ms.create_request_from_listing.return_value = request_obj
            data = SimpleNamespace(
                planned_start="2026-11-01T08:00:00+00:00",
                planned_end="2026-11-01T16:00:00+00:00",
                contact_name="Client",
                contact_email="c@c.com",
                contact_phone="+7999",
                work_type="earthworks",
                comment="need excavator",
            )
            result = svc.create_request_from_listing(mock_db, 1, data)

        assert result.request_id == 42
        mock_db.add.assert_called()


class TestListMarketplaceRequests:
    """Cover list_marketplace_requests (lines 572-689)."""

    def test_empty(self, svc, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        mock_db.execute.return_value.scalar.return_value = 0
        result = svc.list_marketplace_requests(mock_db, 1, None, False, 10, 0)
        assert result["items"] == []
        assert result["total"] == 0

    def test_with_requests(self, svc, mock_db):
        req = SimpleNamespace(
            id=1,
            vehicle_category_id=2,
            work_type="earthworks",
            object_address="Moscow",
            planned_start=datetime(2026, 11, 5, tzinfo=UTC),
            planned_end=datetime(2026, 11, 6, tzinfo=UTC),
            shift_duration_hours=Decimal("8"),
            client_rate=Decimal("15000"),
            rate_type="shift",
            marketplace_mode="client",
            payment_terms_days=14,
            requirements={"min_tonnage": 10},
            priority=1,
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
        cat = SimpleNamespace(name="Excavators")

        # First execute call returns vehicle_regions, second returns total count
        exec_count = {"n": 0}

        def mock_execute(stmt):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] == 1:
                mr.scalars.return_value.all.return_value = ["Moscow"]
            elif exec_count["n"] == 2:
                mr.scalar.return_value = 1
            else:
                mr.scalars.return_value.all.return_value = [req]
            return mr

        mock_db.execute.side_effect = mock_execute
        mock_db.scalars.return_value.all.return_value = [req]
        mock_db.get.return_value = cat

        result = svc.list_marketplace_requests(mock_db, 1, 2, False, 10, 0)
        assert len(result["items"]) == 1
        assert result["items"][0]["is_extended_payment"] is True


class TestRespondToMarketplaceRequest:
    """Cover respond_to_marketplace_request (lines 690-833)."""

    @pytest.mark.asyncio
    async def test_request_not_found(self, svc, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(mock_db, 1, 999, 1)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_own_request_forbidden(self, svc, mock_db):
        req = SimpleNamespace(source_channel="marketplace", status="new", company_id=1)
        mock_db.get.return_value = req
        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(mock_db, 1, 1, 1)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_vehicle_not_available(self, svc, mock_db):
        req = SimpleNamespace(source_channel="marketplace", status="new", company_id=2)
        vehicle = SimpleNamespace(company_id=1, status="maintenance", name="KAMAZ")
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return req if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get

        with pytest.raises(HTTPException) as exc:
            await svc.respond_to_marketplace_request(mock_db, 1, 1, 1)
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_success(self, svc, mock_db):
        req = SimpleNamespace(
            source_channel="marketplace",
            status="new",
            company_id=2,
            planned_start=datetime(2026, 11, 5, tzinfo=UTC),
            planned_end=datetime(2026, 11, 6, tzinfo=UTC),
            object_address="Moscow",
            marketplace_mode="client",
            payment_terms_days=7,
            created_by=10,
        )
        vehicle = SimpleNamespace(
            company_id=1,
            status="available",
            name="KAMAZ",
            marketplace_commission_agreed=True,
        )
        user = SimpleNamespace(
            id=5,
            full_name="Ivan",
            email="i@t.com",
            company=SimpleNamespace(name="MyCo"),
        )

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return req if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1) or None

        with (
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ),
            patch("app.services.websocket_manager.manager") as mock_mgr,
        ):
            mock_mgr.send_to_user = AsyncMock()
            result = await svc.respond_to_marketplace_request(mock_db, 1, 1, 1, user)

        assert result["status"] == "pending_approval"
        mock_db.commit.assert_called()


class TestMarketplacePayoutsReport:
    """Cover marketplace_payouts_report (lines 834-960)."""

    def test_empty(self, svc, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        response = svc.marketplace_payouts_report(
            mock_db, "2026-11-01", "2026-11-30", company_id=1
        )
        assert (
            response.media_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_with_payouts(self, svc, mock_db):
        payout = SimpleNamespace(
            id=1,
            request_id=1,
            vehicle_id=1,
            gross_amount=Decimal("10000"),
            platform_commission=Decimal("1000"),
            net_amount=Decimal("9000"),
            payout_date=date(2026, 11, 5),
            status="paid",
            owner_name="TestCo",
            created_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        req = SimpleNamespace(id=1)
        vehicle = SimpleNamespace(name="KAMAZ")

        mock_db.scalars.return_value.all.return_value = [payout]
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return req if call_count["n"] % 2 == 1 else vehicle

        mock_db.get.side_effect = mock_get

        response = svc.marketplace_payouts_report(
            mock_db, "2026-11-01", "2026-11-30", company_id=1
        )
        assert (
            response.media_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


class TestMarketplaceStats:
    """Cover marketplace_stats (lines 961-1057)."""

    def test_success(self, svc, mock_db):
        mock_db.execute.return_value.scalar.side_effect = [10, 5, 3, 4, 1, 7.5, 20, 2]
        result = svc.marketplace_stats(mock_db, company_id=1)
        assert result["total_requests"] == 10
        assert result["active_requests"] == 5
        assert result["avg_payment_days"] == 7.5


class TestListMyResponses:
    """Cover list_my_responses (lines 1178-1218)."""

    def test_empty(self, svc, mock_db):
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = svc.list_my_responses(mock_db, 1)
        assert result == []

    def test_with_responses(self, svc, mock_db):
        assignment = SimpleNamespace(
            id=1,
            request_id=1,
            vehicle_id=1,
            status="pending_approval",
            created_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        req = SimpleNamespace(
            object_address="Moscow", work_type="earthworks", vehicle_category_id=2
        )
        vehicle = SimpleNamespace(name="KAMAZ")

        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            assignment
        ]
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return req if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get

        result = svc.list_my_responses(mock_db, 1)
        assert len(result) == 1
        assert result[0]["vehicle_name"] == "KAMAZ"


class TestGetCompanyReviewsPublic:
    """Cover get_company_reviews_public (lines 1282-end)."""

    def test_company_not_found(self, svc, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(HTTPException) as exc:
            svc.get_company_reviews_public(mock_db, 10, 0, 999)
        assert exc.value.status_code == 404

    def test_success(self, svc, mock_db):
        company = SimpleNamespace(id=1)
        mock_db.get.return_value = company

        avg_result = SimpleNamespace(avg_rating=4.5, total=10)
        dist_results = [
            SimpleNamespace(rating=5, cnt=6),
            SimpleNamespace(rating=4, cnt=4),
        ]
        review_row = SimpleNamespace(
            id=1,
            rating=5,
            comment="Great!",
            reviewer_name="Client",
            is_verified=True,
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )

        exec_count = {"n": 0}

        def mock_execute(stmt, params=None):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] == 1:
                mr.one.return_value = avg_result
            elif exec_count["n"] == 2:
                mr.all.return_value = dist_results
            else:
                mr.all.return_value = [review_row]
            return mr

        mock_db.execute.side_effect = mock_execute

        result = svc.get_company_reviews_public(mock_db, 10, 0, 1)
        assert result["average_rating"] == 4.5
        assert len(result["items"]) == 1
        assert result["rating_distribution"]["5"] == 6
