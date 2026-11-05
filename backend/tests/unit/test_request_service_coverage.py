"""Coverage tests for RequestService - additional methods."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    from app.services.request_service import RequestService

    return RequestService(mock_db)


class TestCreateRequest:
    """Cover create_request (lines 471-581)."""

    @pytest.mark.asyncio
    async def test_invalid_dates(self, service):
        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc:
            await service.create_request(
                {
                    "planned_start": "2026-11-02T08:00:00",
                    "planned_end": "2026-11-01T16:00:00",
                },
                company_id=1,
                user_id=1,
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_category_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc:
            await service.create_request(
                {
                    "vehicle_category_id": 999,
                    "planned_start": "2026-11-01T08:00:00+00:00",
                    "planned_end": "2026-11-02T16:00:00+00:00",
                },
                company_id=1,
                user_id=1,
            )
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_self_transaction_prevention(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        cat = SimpleNamespace(id=2)
        vehicle = SimpleNamespace(company_id=1)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return cat
            return vehicle

        mock_db.get.side_effect = mock_get

        with pytest.raises(RequestServiceError) as exc:
            await service.create_request(
                {
                    "vehicle_category_id": 2,
                    "vehicle_id": 1,
                    "planned_start": "2026-11-01T08:00:00+00:00",
                    "planned_end": "2026-11-02T16:00:00+00:00",
                },
                company_id=1,
                user_id=1,
            )
        assert exc.value.status_code == 422
        assert "own vehicle" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_success(self, service, mock_db):
        SimpleNamespace(
            id=1,
            work_type="earthworks",
            planned_start=datetime(2026, 11, 1, tzinfo=UTC),
            planned_end=datetime(2026, 11, 2, tzinfo=UTC),
            region="Moscow",
            rate_type="per_shift",
            shift_duration_hours=Decimal("8"),
            client_rate=None,
            estimated_amount=None,
            status="new",
        )
        mock_db.get.return_value = SimpleNamespace(id=2)  # category
        mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1) or None

        with (
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ),
            patch("app.services.pricing_service.pricing_service") as mock_pricing,
        ):
            mock_pricing.calculate_estimate.return_value = {
                "estimated_amount": 15000,
                "rate_used": 15000,
                "rate_type": "per_shift",
            }
            await service.create_request(
                {
                    "vehicle_category_id": 2,
                    "work_type": "earthworks",
                    "planned_start": "2026-11-01T08:00:00+00:00",
                    "planned_end": "2026-11-02T16:00:00+00:00",
                },
                company_id=1,
                user_id=1,
            )
        mock_db.add.assert_called()
        mock_db.commit.assert_called()


class TestBulkResponseAction:
    """Cover bulk_response_action (lines 582-700)."""

    @pytest.mark.asyncio
    async def test_invalid_action(self, service):
        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc:
            await service.bulk_response_action([1], "invalid", "", 1, 1)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_assignment_not_found(self, service, mock_db):
        mock_db.get.return_value = None
        result = await service.bulk_response_action([999], "approve", "", 1, 1)
        assert result["processed"] == 0
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_approve_success(self, service, mock_db):
        assignment = SimpleNamespace(
            id=1,
            request_id=1,
            vehicle_id=1,
            status="pending_approval",
            assigned_by=5,
        )
        request = SimpleNamespace(
            id=1,
            company_id=1,
            status="has_responses",
            planned_start=datetime(2026, 11, 5, tzinfo=UTC),
        )
        vehicle = SimpleNamespace(current_driver_id=10)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return assignment
            if call_count["n"] == 2:
                return request
            return vehicle

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        with (
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ),
            patch("app.services.websocket_manager.manager") as mock_mgr,
        ):
            mock_mgr.send_to_user = AsyncMock()
            result = await service.bulk_response_action([1], "approve", "", 1, 1)

        assert result["processed"] == 1
        assert assignment.status == "approved"
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_reject_success(self, service, mock_db):
        assignment = SimpleNamespace(
            id=1, request_id=1, status="pending_approval", assigned_by=5
        )
        request = SimpleNamespace(id=1, company_id=1, status="has_responses")

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return assignment if call_count["n"] == 1 else request

        mock_db.get.side_effect = mock_get

        with (
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ),
            patch("app.services.websocket_manager.manager") as mock_mgr,
        ):
            mock_mgr.send_to_user = AsyncMock()
            result = await service.bulk_response_action([1], "reject", "busy", 1, 1)

        assert result["processed"] == 1
        assert assignment.status == "rejected"


class TestApproveResponse:
    """Cover approve_response (lines 701-786)."""

    @pytest.mark.asyncio
    async def test_request_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc:
            await service.approve_response(999, 1, 1, 1)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_already_processed(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(company_id=1)
        assignment = SimpleNamespace(status="approved", request_id=1)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else assignment

        mock_db.get.side_effect = mock_get

        with pytest.raises(RequestServiceError) as exc:
            await service.approve_response(1, 1, 1, 1)
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_success(self, service, mock_db):
        request = SimpleNamespace(
            company_id=1,
            status="has_responses",
            planned_start=datetime(2026, 11, 5, tzinfo=UTC),
        )
        assignment = SimpleNamespace(
            status="pending_approval", request_id=1, vehicle_id=1, assigned_by=5
        )
        vehicle = SimpleNamespace(name="KAMAZ")

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request
            if call_count["n"] == 2:
                return assignment
            return vehicle

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        with patch(
            "app.services.notification_service.create_notification",
            new_callable=AsyncMock,
        ):
            result = await service.approve_response(1, 1, 1, 1)

        assert "shift_task_id" in result
        assert assignment.status == "approved"
        mock_db.commit.assert_called()


class TestRejectResponse:
    """Cover reject_response (lines 787-835)."""

    @pytest.mark.asyncio
    async def test_success(self, service, mock_db):
        request = SimpleNamespace(company_id=1, status="has_responses")
        assignment = SimpleNamespace(
            status="pending_approval", request_id=1, assigned_by=5
        )

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else assignment

        mock_db.get.side_effect = mock_get

        with patch(
            "app.services.notification_service.create_notification",
            new_callable=AsyncMock,
        ):
            result = await service.reject_response(1, 1, "busy", 1, 1)

        assert "message" in result
        assert assignment.status == "rejected"


class TestGetRequestTimeline:
    """Cover get_request_timeline (lines 836-899)."""

    def test_request_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc:
            service.get_request_timeline(999, 1)
        assert exc.value.status_code == 404

    def test_access_denied(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(company_id=2)
        mock_db.get.return_value = request
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with pytest.raises(RequestServiceError) as exc:
            service.get_request_timeline(1, 1)
        assert exc.value.status_code == 403

    def test_success(self, service, mock_db):
        from app.models.dispatch import Request as RequestModel

        request = SimpleNamespace(company_id=1)
        log = SimpleNamespace(
            id=1,
            from_status="new",
            to_status="assigned",
            comment="Assigned",
            changed_by_user_id=1,
            created_at=datetime(2026, 11, 5, tzinfo=UTC),
        )
        user = SimpleNamespace(full_name="Ivan", email="i@t.com")

        def mock_get(model, pk):
            if model == RequestModel or (
                hasattr(model, "__name__") and "Request" in str(model)
            ):
                return request
            return user

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalars.return_value.all.return_value = [log]

        result = service.get_request_timeline(1, 1)
        assert len(result) == 1
        assert result[0]["changed_by"] == "Ivan"


class TestUpdateRequestPut:
    """Cover update_request_put (lines 900-966)."""

    def test_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc:
            service.update_request_put(999, 1, 1)
        assert exc.value.status_code == 404

    def test_cannot_edit_assigned(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(company_id=1, status="assigned")
        mock_db.get.return_value = request
        with pytest.raises(RequestServiceError) as exc:
            service.update_request_put(1, 1, 1)
        assert exc.value.status_code == 409

    def test_success_with_changes(self, service, mock_db):
        request = SimpleNamespace(
            company_id=1,
            status="new",
            work_type="old",
            object_address="old addr",
            planned_start=None,
            planned_end=None,
            client_rate=None,
            rate_type=None,
            payment_terms_days=None,
            marketplace_mode=None,
            priority=None,
            requirements=None,
        )
        mock_db.get.return_value = request

        result = service.update_request_put(
            1,
            1,
            1,
            work_type="earthworks",
            object_address="Moscow",
            priority="high",
        )
        assert result["message"] == "Заявка обновлена"
        assert request.work_type == "earthworks"
        mock_db.commit.assert_called()


class TestUpdateRequestPatch:
    """Cover update_request_patch (lines 967-end)."""

    @pytest.mark.asyncio
    async def test_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc:
            await service.update_request_patch(999, {}, 1, 1)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_status_change_with_notification(self, service, mock_db):
        request = SimpleNamespace(
            id=1,
            company_id=1,
            status="new",
            work_type="earthworks",
            created_by=10,
        )
        mock_db.get.return_value = request

        with patch(
            "app.services.notification_service.create_notification",
            new_callable=AsyncMock,
        ):
            await service.update_request_patch(
                1,
                {"status": "processing"},
                1,
                1,
            )
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_field_update(self, service, mock_db):
        request = SimpleNamespace(
            id=1, company_id=1, status="new", work_type="old", created_by=1
        )
        mock_db.get.return_value = request

        await service.update_request_patch(
            1,
            {"work_type": "crane_work"},
            1,
            1,
        )
        assert request.work_type == "crane_work"


class TestListRequests:
    """Cover list_requests (lines 241-362)."""

    def test_empty(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_requests([1])
        assert result == []

    def test_with_filters_and_enrichment(self, service, mock_db):
        req = SimpleNamespace(
            id=1,
            client_id=1,
            status=SimpleNamespace(value="new"),
            request_type="standard",
            vehicle_category_id=2,
            work_type="earthworks",
            object_address="Moscow",
            planned_start=datetime(2026, 11, 5, tzinfo=UTC),
            planned_end=datetime(2026, 11, 6, tzinfo=UTC),
            actual_start=None,
            actual_end=None,
            shift_duration_hours=Decimal("8"),
            client_rate=Decimal("15000"),
            rate_type="per_shift",
            estimated_amount=Decimal("15000"),
            final_amount=None,
            assigned_vehicle_id=1,
            assigned_operator_id=None,
            assigned_owner_id=None,
            source_channel="marketplace",
            priority="normal",
            comment="test",
            company_id=1,
            created_by=1,
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
            updated_at=None,
        )
        contractor = SimpleNamespace(name="ClientCo")
        category = SimpleNamespace(name="Excavators")
        vehicle = SimpleNamespace(name="KAMAZ")

        mock_db.scalars.return_value.all.return_value = [req]
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return contractor
            if call_count["n"] == 2:
                return category
            return vehicle

        mock_db.get.side_effect = mock_get

        result = service.list_requests(
            [1],
            status_filter="new",
            search="earth",
            sort_by="created_at",
            sort_order="desc",
        )
        assert len(result) == 1
        assert result[0]["client_name"] == "ClientCo"
        assert result[0]["vehicle_category_name"] == "Excavators"
        assert result[0]["assigned_vehicle_name"] == "KAMAZ"
