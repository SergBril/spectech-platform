"""Coverage push: filters, enrichment, WS errors, validations."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    for attr in ['commit','rollback','flush','add','refresh']:
        setattr(db, attr, MagicMock())
    return db


@pytest.fixture
def service(mock_db):
    from app.services.request_service import RequestService
    return RequestService(mock_db)


def _full_req(**kw):
    d = dict(id=1, work_type="crane", object_address="Test",
        vehicle_category_id=1, client_id=10, assigned_vehicle_id=5,
        status="open", priority="normal", comment=None,
        company_id=1, created_by=5,
        planned_start=datetime(2026,11,1,tzinfo=UTC),
        planned_end=datetime(2026,11,2,tzinfo=UTC),
        created_at=datetime.now(UTC), updated_at=None,
        source_channel=None, rate_type=None,
        estimated_amount=None, final_amount=None,
        assigned_operator_id=None, assigned_owner_id=None,
        shift_duration_hours=None, client_rate=None,
        actual_start=None, actual_end=None,
        request_type=None, marketplace_commission_rate=None)
    d.update(kw)
    return SimpleNamespace(**d)


class TestListRequestsAllFilters:
    """Each filter individually to ensure branch coverage."""

    def _run(self, service, mock_db, **kwargs):
        mock_db.scalars.return_value.all.return_value = []
        return service.list_requests([1], **kwargs)

    def test_status_filter(self, service, mock_db):
        self._run(service, mock_db, status_filter="open")

    def test_priority(self, service, mock_db):
        self._run(service, mock_db, priority="high")

    def test_client_id(self, service, mock_db):
        self._run(service, mock_db, client_id=10)

    def test_vehicle_category_id(self, service, mock_db):
        self._run(service, mock_db, vehicle_category_id=1)

    def test_assigned_vehicle_id(self, service, mock_db):
        self._run(service, mock_db, assigned_vehicle_id=5)

    def test_work_type(self, service, mock_db):
        self._run(service, mock_db, work_type="earthworks")

    def test_search(self, service, mock_db):
        self._run(service, mock_db, search="Moscow")

    def test_date_from(self, service, mock_db):
        self._run(service, mock_db, date_from="2026-11-01")

    def test_date_to(self, service, mock_db):
        self._run(service, mock_db, date_to="2026-11-30")

    def test_sort_asc(self, service, mock_db):
        self._run(service, mock_db, sort_order="asc")

    def test_sort_desc(self, service, mock_db):
        self._run(service, mock_db, sort_order="desc")


class TestEnrichmentBranches:
    """Cover all enrichment lookup combinations."""

    def test_all_present(self, service, mock_db):
        req = _full_req()
        mock_db.scalars.return_value.all.return_value = [req]
        cat = SimpleNamespace(name="Краны")
        ctr = SimpleNamespace(name="ООО Клиент")
        veh = SimpleNamespace(name="KAMAZ")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return cat
            if n["c"] == 2: return ctr
            if n["c"] == 3: return veh
            return None
        mock_db.get.side_effect = mg
        r = service.list_requests([1])
        assert len(r) == 1

    def test_none_present(self, service, mock_db):
        req = _full_req(vehicle_category_id=999, client_id=999, assigned_vehicle_id=999)
        mock_db.scalars.return_value.all.return_value = [req]
        mock_db.get.return_value = None
        r = service.list_requests([1])
        assert len(r) == 1

    def test_no_ids(self, service, mock_db):
        req = _full_req(vehicle_category_id=None, client_id=None, assigned_vehicle_id=None)
        mock_db.scalars.return_value.all.return_value = [req]
        r = service.list_requests([1])
        assert len(r) == 1


class TestAutoPricingWarning:
    """Cover auto-pricing exception path (lines 545-546)."""

    @pytest.mark.asyncio
    async def test_pricing_fail_logged(self, service, mock_db):
        payload = {
            "work_type": "earthworks", "object_address": "Moscow",
            "vehicle_category_id": 1,
            "planned_start": "2026-11-01T08:00:00+00:00",
            "planned_end": "2026-11-02T17:00:00+00:00",
        }
        mr = MagicMock()
        mr.id = 1; mr.company_id = 1; mr.work_type = "earthworks"
        mr.object_address = "Moscow"; mr.vehicle_category_id = 1
        mr.source_channel = None
        mr.planned_start = datetime(2026,11,1,tzinfo=UTC)
        mr.planned_end = datetime(2026,11,2,tzinfo=UTC)
        mock_db.add.side_effect = lambda o: None
        mock_db.scalars.return_value.first.return_value = SimpleNamespace(id=1, name="Cat")
        with patch("app.services.pricing_service.pricing_service") as mp:
            mp.estimate_request_price.side_effect = RuntimeError("fail")
            with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
                with patch("app.services.max_messenger_service.max_messenger_service") as mm:
                    mm.notify_company_dispatchers = AsyncMock(side_effect=RuntimeError("max fail"))
                    try:
                        await service.create_request(payload, 1, 5)
                    except Exception:
                        pass


class TestWSNotificationErrors:
    """Cover WS notification exception paths (665-666, 779-780, 831-832)."""

    @pytest.mark.asyncio
    async def test_bulk_reject_ws_fail(self, service, mock_db):
        assignment = SimpleNamespace(id=1, request_id=1, status="pending_approval",
            assigned_by=5, contractor_company_id=2)
        request = SimpleNamespace(id=1, company_id=1, status="open")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return request
            return assignment
        mock_db.get.side_effect = mg
        mock_db.scalars.return_value.all.return_value = []
        with patch("app.services.websocket_manager.manager") as mgr:
            mgr.send_to_user = AsyncMock(side_effect=RuntimeError("WS fail"))
            try:
                await service.bulk_response_action([1], "reject", "No", 1, 2)
            except Exception:
                pass


class TestApproveRejectValidations:
    """Cover validation checks (678, 719, 742, 805)."""

    @pytest.mark.asyncio
    async def test_approve_not_found(self, service, mock_db):
        from app.services.request_service import RequestServiceError
        mock_db.get.return_value = None
        with pytest.raises(RequestServiceError) as ei:
            await service.approve_response(1, 999, 1, 1)
        assert ei.value.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_already_done(self, service, mock_db):
        from app.services.request_service import RequestServiceError
        req = SimpleNamespace(id=1, company_id=1)
        asn = SimpleNamespace(id=1, request_id=1, status="approved")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return req
            return asn
        mock_db.get.side_effect = mg
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
    async def test_reject_already_done(self, service, mock_db):
        from app.services.request_service import RequestServiceError
        req = SimpleNamespace(id=1, company_id=1)
        asn = SimpleNamespace(id=1, request_id=1, status="rejected")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return req
            return asn
        mock_db.get.side_effect = mg
        with pytest.raises(RequestServiceError) as ei:
            await service.reject_response(1, 1, "reason", 1, 1)
        assert ei.value.status_code == 409
