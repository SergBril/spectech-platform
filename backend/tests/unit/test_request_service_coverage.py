"""Coverage tests for request_service."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    from app.services.request_service import RequestService

    return RequestService(mock_db)


class TestRequestServiceError:
    """Cover RequestServiceError (lines 29-35)."""

    def test_init(self):
        from app.services.request_service import RequestServiceError

        err = RequestServiceError(404, "Not found")
        assert err.status_code == 404
        assert err.detail == "Not found"
        assert str(err) == "Not found"


class TestAssignVehicle:
    """Cover assign_vehicle (lines 41-240)."""

    @pytest.mark.asyncio
    async def test_request_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_request_wrong_company(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(company_id=99, status="open")
        mock_db.get.return_value = request
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_request_closed(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(company_id=7, status="closed")
        mock_db.get.return_value = request
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_vehicle_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(company_id=7, status="open")
        vehicle = None
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request
            return vehicle

        mock_db.get.side_effect = mock_get
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_vehicle_unavailable_status(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(company_id=7, status="open")
        vehicle = SimpleNamespace(company_id=7, status="repair", name="KAMAZ")
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_marketplace_commission_not_agreed(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = SimpleNamespace(
            company_id=7, status="open", source_channel="marketplace"
        )
        vehicle = SimpleNamespace(
            company_id=7,
            status="active",
            name="KAMAZ",
            marketplace_commission_agreed=False,
        )
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        with patch(
            "app.services.request_service.create_notification", new_callable=AsyncMock
        ):
            with pytest.raises(RequestServiceError) as exc_info:
                await service.assign_vehicle(1, 1, None, 7, 1)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_dates(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        now = datetime.now(UTC)
        request = SimpleNamespace(
            company_id=7,
            status="open",
            source_channel=None,
            planned_start=now + timedelta(days=2),
            planned_end=now + timedelta(days=1),
        )
        vehicle = SimpleNamespace(
            company_id=7,
            status="active",
            name="KAMAZ",
            marketplace_commission_agreed=True,
        )
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_overlapping_assignment(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        now = datetime.now(UTC)
        request = SimpleNamespace(
            company_id=7,
            status="open",
            source_channel=None,
            planned_start=now,
            planned_end=now + timedelta(days=1),
        )
        vehicle = SimpleNamespace(
            company_id=7,
            status="active",
            name="KAMAZ",
            marketplace_commission_agreed=True,
        )
        overlap = SimpleNamespace(
            request_id=99, planned_start=now, planned_end=now + timedelta(days=1)
        )
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        mock_db.scalar.return_value = overlap
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_idempotent_existing_assignment(self, service, mock_db):
        now = datetime.now(UTC)
        request = SimpleNamespace(
            id=1,
            company_id=7,
            status="open",
            source_channel=None,
            planned_start=now,
            planned_end=now + timedelta(days=1),
        )
        vehicle = SimpleNamespace(
            company_id=7,
            status="active",
            name="KAMAZ",
            marketplace_commission_agreed=True,
        )
        existing = SimpleNamespace(id=5)
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        mock_db.scalar.return_value = None
        q = MagicMock()
        q.filter.return_value.first.return_value = existing
        mock_db.query.return_value = q
        result = await service.assign_vehicle(1, 1, None, 7, 1)
        assert result is not None

    @pytest.mark.asyncio
    async def test_success_with_operator(self, service, mock_db):
        now = datetime.now(UTC)
        request = SimpleNamespace(
            id=1,
            company_id=7,
            status="open",
            source_channel=None,
            planned_start=now,
            planned_end=now + timedelta(days=1),
            work_type="earthworks",
            assigned_vehicle_id=None,
            assigned_operator_id=None,
        )
        vehicle = SimpleNamespace(
            id=1,
            company_id=7,
            status="active",
            name="KAMAZ",
            marketplace_commission_agreed=True,
        )
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        mock_db.scalar.return_value = None
        q_assign = MagicMock()
        q_assign.filter.return_value.first.return_value = None
        q_shift = MagicMock()
        q_shift.filter.return_value.first.return_value = None
        call_q = {"n": 0}

        def mock_query(model):
            call_q["n"] += 1
            return q_assign if call_q["n"] == 1 else q_shift

        mock_db.query.side_effect = mock_query
        mock_db.flush.side_effect = lambda: None
        mock_db.refresh.side_effect = lambda r: None
        with patch(
            "app.services.request_service.create_notification", new_callable=AsyncMock
        ):
            result = await service.assign_vehicle(
                1, 1, operator_id=5, company_id=7, user_id=1
            )
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_integrity_error(self, service, mock_db):
        from sqlalchemy.exc import IntegrityError

        from app.services.request_service import RequestServiceError

        now = datetime.now(UTC)
        request = SimpleNamespace(
            id=1,
            company_id=7,
            status="open",
            source_channel=None,
            planned_start=now,
            planned_end=now + timedelta(days=1),
        )
        vehicle = SimpleNamespace(
            id=1,
            company_id=7,
            status="active",
            name="KAMAZ",
            marketplace_commission_agreed=True,
        )
        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            return request if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        mock_db.scalar.return_value = None
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        mock_db.query.return_value = q
        mock_db.flush.side_effect = IntegrityError("dup", None, None)
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 1, None, 7, 1)
        assert exc_info.value.status_code == 409
        mock_db.rollback.assert_called()


def _make_full_request(**kwargs):
    defaults = {
        "id": 1,
        "company_id": 7,
        "client_id": 10,
        "status": "open",
        "priority": "normal",
        "work_type": "earthworks",
        "object_address": "Moscow",
        "vehicle_category_id": 1,
        "assigned_vehicle_id": None,
        "assigned_operator_id": None,
        "assigned_owner_id": None,
        "planned_start": datetime(2026, 11, 1, tzinfo=UTC),
        "planned_end": datetime(2026, 11, 2, tzinfo=UTC),
        "actual_start": None,
        "actual_end": None,
        "shift_duration_hours": None,
        "client_rate": None,
        "rate_type": None,
        "estimated_amount": None,
        "final_amount": None,
        "created_at": datetime(2026, 10, 1, tzinfo=UTC),
        "updated_at": None,
        "source_channel": None,
        "comment": None,
        "created_by": 1,
        "request_type": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestListRequests:
    """Cover list_requests (lines 241-362)."""

    def test_basic(self, service, mock_db):
        req = _make_full_request()
        mock_db.scalars.return_value.all.return_value = [req]
        # Mock enrichment lookups (Contractor, Category, Vehicle)
        mock_db.get.return_value = None
        result = service.list_requests([7])
        assert len(result) == 1

    def test_empty(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_requests([7])
        assert result == []

    def test_with_all_filters(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_requests(
            [7],
            status_filter="open",
            priority="high",
            client_id=10,
            vehicle_category_id=1,
            assigned_vehicle_id=5,
            work_type="crane",
            search="test",
            date_from="2026-01-01",
            date_to="2026-12-31",
            sort_by="created_at",
            sort_order="asc",
            limit=10,
            offset=0,
        )
        assert isinstance(result, list)


class TestGetRequestTimeline:
    """Cover get_request_timeline (lines 836-898)."""

    def test_success(self, service, mock_db):
        request = _make_full_request()  # company_id=7 matches call arg
        log = SimpleNamespace(
            id=1,
            from_status="open",
            to_status="assigned",
            changed_by_user_id=1,
            comment="test",
            created_at=datetime.now(UTC),
            changed_at=datetime.now(UTC),
        )
        user = SimpleNamespace(full_name="Admin", email="a@test.com")

        call_count = {"n": 0}

        def mock_get(model, obj_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return request
            return user

        mock_db.get.side_effect = mock_get

        # company_id matches -> no access check execute, only logs query
        logs_scalars = MagicMock()
        logs_scalars.all.return_value = [log]
        logs_result = MagicMock()
        logs_result.scalars.return_value = logs_scalars

        mock_db.execute.return_value = logs_result

        result = service.get_request_timeline(1, 7)
        assert len(result) == 1
        assert result[0]["from_status"] == "open"

    def test_not_found_raises(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc_info:
            service.get_request_timeline(999, 7)
        assert exc_info.value.status_code == 404

    def test_access_denied_raises(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        request = _make_full_request(company_id=99)
        mock_db.get.return_value = request
        access_result = MagicMock()
        access_result.scalar_one_or_none.return_value = None  # no access
        mock_db.execute.return_value = access_result
        with pytest.raises(RequestServiceError) as exc_info:
            service.get_request_timeline(1, 7)
        assert exc_info.value.status_code == 403


class TestUpdateRequestPut:
    """Cover update_request_put (lines 900-965)."""

    def test_not_found_raises(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as exc_info:
            service.update_request_put(1, 7, 1, work_type="crane")
        assert exc_info.value.status_code == 404

    def test_assigned_raises(self, service, mock_db):
        from app.services.request_service import RequestServiceError

        req = _make_full_request(status="assigned")
        mock_db.get.return_value = req
        with pytest.raises(RequestServiceError) as exc_info:
            service.update_request_put(1, 7, 1, work_type="crane")
        assert exc_info.value.status_code == 409

    def test_success(self, service, mock_db):
        req = _make_full_request()
        mock_db.get.return_value = req
        result = service.update_request_put(1, 7, 1, work_type="crane", priority="high")
        assert result["message"] is not None
        assert req.work_type == "crane"
        mock_db.commit.assert_called()


class TestExportMethods:
    """Cover export methods (lines 457-469)."""

    def test_export_pdf(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        with patch("app.utils.export_utils.export_requests_pdf", return_value=b"pdf"):
            result = service.export_requests_pdf(company_ids=[7])
        assert result == b"pdf"

    def test_export_excel(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        with patch(
            "app.utils.export_utils.export_requests_excel", return_value=b"xlsx"
        ):
            result = service.export_requests_excel(company_ids=[7])
        assert result == b"xlsx"
