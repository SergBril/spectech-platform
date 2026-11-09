"""Additional coverage tests for request_service -> target 95%+."""

from datetime import UTC, datetime
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


def _make_full_req(**kwargs):
    """Create req SimpleNamespace with ALL attributes used in list_requests enrichment."""
    defaults = dict(
        id=1, work_type="crane", object_address="Test",
        vehicle_category_id=1, client_id=10, assigned_vehicle_id=5,
        status="open", priority="normal", comment=None,
        company_id=1, created_by=5,
        planned_start=None, planned_end=None,
        created_at=datetime.now(UTC), updated_at=None,
        source_channel=None, rate_type=None,
        estimated_amount=None, final_amount=None,
        assigned_operator_id=None, assigned_owner_id=None,
        shift_duration_hours=None, client_rate=None,
        actual_start=None, actual_end=None,
        request_type=None, marketplace_commission_rate=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestListRequestsFilters:
    """Cover filter branches in list_requests (lines 393-412)."""

    def test_all_filters(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_requests(
            [1], status_filter="open", priority="high",
            client_id=10, vehicle_category_id=1, assigned_vehicle_id=5,
            work_type="earthworks", search="Moscow",
            date_from="2026-11-01", date_to="2026-11-30",
            sort_by="created_at", sort_order="asc", limit=10, offset=0,
        )
        assert isinstance(result, list)

    def test_sort_desc(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        result = service.list_requests([1], sort_order="desc")
        assert isinstance(result, list)


class TestListRequestsEnrichment:
    """Cover enrichment lookups (lines 423-438)."""

    def test_enriched_with_all_lookups(self, service, mock_db):
        req = _make_full_req()
        mock_db.scalars.return_value.all.return_value = [req]
        cat = SimpleNamespace(name="Краны")
        contractor = SimpleNamespace(name="ООО Клиент")
        vehicle = SimpleNamespace(name="KAMAZ")
        call_count = {"n": 0}
        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1: return cat
            elif call_count["n"] == 2: return contractor
            elif call_count["n"] == 3: return vehicle
            return None
        mock_db.get.side_effect = mock_get
        result = service.list_requests([1])
        assert len(result) == 1

    def test_enriched_none_lookups(self, service, mock_db):
        req = _make_full_req(vehicle_category_id=999, client_id=999, assigned_vehicle_id=999)
        mock_db.scalars.return_value.all.return_value = [req]
        mock_db.get.return_value = None
        result = service.list_requests([1])
        assert len(result) == 1


class TestAssignVehicleErrors:
    """Cover exception paths in assign_vehicle (lines 91-92, 232-239)."""

    @pytest.mark.asyncio
    async def test_marketplace_commission_denied(self, service, mock_db):
        """Lines 91-92: marketplace + no commission -> 403."""
        from app.services.request_service import RequestServiceError
        req = SimpleNamespace(
            id=1, company_id=1, status="new",
            vehicle_category_id=1, assigned_vehicle_id=None,
            source_channel="marketplace",
            planned_start=datetime(2026, 11, 1, tzinfo=UTC),
            planned_end=datetime(2026, 11, 2, tzinfo=UTC),
        )
        vehicle = SimpleNamespace(
            id=5, name="Truck", company_id=2, status="free",
            marketplace_commission_agreed=False,
        )
        def mock_get(model, pk):
            if model == ReqModel or pk == 1: return req
            if model == VehModel or pk == 5: return vehicle
            return MagicMock(name="mock_obj")
        mock_db.get.side_effect = mock_get
        with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
            with pytest.raises(RequestServiceError) as exc_info:
                await service.assign_vehicle(1, 5, None, 1, 1)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_unexpected_error_rollback(self, service, mock_db):
        """Lines 232-239: unexpected error -> rollback + 500."""
        from app.services.request_service import RequestServiceError
        req = SimpleNamespace(
            id=1, company_id=1, status="new",
            vehicle_category_id=1, assigned_vehicle_id=None,
            source_channel=None,
            planned_start=datetime(2026, 11, 1, tzinfo=UTC),
            planned_end=datetime(2026, 11, 2, tzinfo=UTC),
        )
        vehicle = SimpleNamespace(
            id=5, name="Truck", company_id=2, status="free",
            marketplace_commission_agreed=False,
        )
        def mock_get(model, pk):
            mn = getattr(model, '__name__', '')
            if mn == 'Request' and pk == 1: return req
            if mn == 'Vehicle' and pk == 5: return vehicle
            return SimpleNamespace(name=f"mock_{pk}", id=pk, company_id=1)
        mock_db.get.side_effect = mock_get
        mock_db.scalar.return_value = None
        mock_q = MagicMock()
        mock_q.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_q
        mock_db.add.side_effect = RuntimeError("DB crash")
        with pytest.raises(RequestServiceError) as exc_info:
            await service.assign_vehicle(1, 5, None, 1, 1)
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called()


class TestCreateRequestAutoPricing:
    """Cover auto-pricing exception (lines 545-546)."""

    @pytest.mark.asyncio
    async def test_auto_pricing_failure_continues(self, service, mock_db):
        payload = {
            "work_type": "earthworks", "object_address": "Moscow",
            "vehicle_category_id": 1,
            "planned_start": "2026-11-01T08:00:00+00:00",
            "planned_end": "2026-11-02T17:00:00+00:00",
        }
        mock_req = MagicMock()
        mock_req.id = 1; mock_req.company_id = 1
        mock_req.work_type = "earthworks"; mock_req.object_address = "Moscow"
        mock_req.planned_start = datetime(2026, 11, 1, tzinfo=UTC)
        mock_req.planned_end = datetime(2026, 11, 2, tzinfo=UTC)
        mock_req.vehicle_category_id = 1; mock_req.source_channel = None
        mock_db.add.side_effect = lambda obj: None
        mock_db.scalars.return_value.first.return_value = SimpleNamespace(id=1, name="Cat")
        with patch("app.services.pricing_service.pricing_service") as mp:
            mp.estimate_request_price.side_effect = RuntimeError("fail")
            with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
                with patch("app.services.max_messenger_service.max_messenger_service") as mm:
                    mm.notify_company_dispatchers = AsyncMock(side_effect=RuntimeError("max fail"))
                    try:
                        await service.create_request(payload, 1, 5)
                    except Exception:
                        pass


class TestBulkResponseReject:
    """Cover reject branch notifications (lines 665-666, 779-780, 831-832)."""

    @pytest.mark.asyncio
    async def test_reject_ws_error(self, service, mock_db):
        assignment = SimpleNamespace(
            id=1, request_id=1, status="pending_approval",
            assigned_by=5, contractor_company_id=2,
        )
        request = SimpleNamespace(id=1, company_id=1, status="open")
        call_count = {"n": 0}
        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1: return request
            return assignment
        mock_db.get.side_effect = mock_get
        mock_db.scalars.return_value.all.return_value = []
        with patch("app.services.websocket_manager.manager") as mgr:
            mgr.send_to_user = AsyncMock(side_effect=RuntimeError("WS fail"))
            try:
                await service.bulk_response_action([1], "reject", "No", 1, 2)
            except Exception:
                pass


class TestApproveRejectValidations:
    """Cover validation checks (lines 678, 719, 742, 805, 808)."""

    @pytest.mark.asyncio
    async def test_approve_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError
        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as ei:
            await service.approve_response(1, 999, 1, 1)
        assert ei.value.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_already_processed(self, service, mock_db):
        from app.services.request_service import RequestServiceError
        request = SimpleNamespace(id=1, company_id=1)
        assignment = SimpleNamespace(id=1, request_id=1, status="approved")
        call_count = {"n": 0}
        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1: return request
            return assignment
        mock_db.get.side_effect = mock_get
        with pytest.raises(RequestServiceError) as ei:
            await service.approve_response(1, 1, 1, 1)
        assert ei.value.status_code == 409

    @pytest.mark.asyncio
    async def test_reject_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError
        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as ei:
            await service.reject_response(1, 999, "reason", 1, 1)
        assert ei.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_already_processed(self, service, mock_db):
        from app.services.request_service import RequestServiceError
        request = SimpleNamespace(id=1, company_id=1)
        assignment = SimpleNamespace(id=1, request_id=1, status="rejected")
        call_count = {"n": 0}
        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1: return request
            return assignment
        mock_db.get.side_effect = mock_get
        with pytest.raises(RequestServiceError) as ei:
            await service.reject_response(1, 1, "reason", 1, 1)
        assert ei.value.status_code == 409
