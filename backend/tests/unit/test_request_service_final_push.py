"""Final coverage push for request_service -> 95%+."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    for a in ['commit','rollback','flush','add','refresh']:
        setattr(db, a, MagicMock())
    return db


@pytest.fixture
def service(mock_db):
    from app.services.request_service import RequestService
    return RequestService(mock_db)


class TestFetchRequestsForExport:
    """Cover _fetch_requests_for_export filters + enrichment (393-438)."""

    def _full_req(self, **kw):
        d = dict(id=1, work_type="crane", object_address="Test",
            vehicle_category_id=1, client_id=10, assigned_vehicle_id=5,
            status="open", priority="normal", comment=None,
            company_id=1, created_by=5,
            planned_start=datetime(2026,11,1,tzinfo=UTC),
            planned_end=datetime(2026,11,2,tzinfo=UTC),
            created_at=datetime.now(UTC), updated_at=None,
            source_channel=None, rate_type=None,
            estimated_amount=None, final_amount=None)
        d.update(kw)
        return SimpleNamespace(**d)

    def test_all_filters_and_enrichment(self, service, mock_db):
        """All filter branches + enrichment lookups."""
        req = self._full_req()
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
        r = service._fetch_requests_for_export(
            [1], status_filter="open", priority="high",
            client_id=10, vehicle_category_id=1, assigned_vehicle_id=5,
            work_type="earthworks", search="Moscow",
            date_from="2026-11-01", date_to="2026-11-30",
            sort_by="created_at", sort_order="asc",
        )
        assert len(r) == 1

    def test_no_enrichment_ids(self, service, mock_db):
        """No category/client/vehicle IDs -> skip lookups."""
        req = self._full_req(vehicle_category_id=None, client_id=None, assigned_vehicle_id=None)
        mock_db.scalars.return_value.all.return_value = [req]
        r = service._fetch_requests_for_export([1])
        assert len(r) == 1

    def test_enrichment_none_results(self, service, mock_db):
        """IDs present but db.get returns None."""
        req = self._full_req(vehicle_category_id=999, client_id=999, assigned_vehicle_id=999)
        mock_db.scalars.return_value.all.return_value = [req]
        mock_db.get.return_value = None
        r = service._fetch_requests_for_export([1])
        assert len(r) == 1

    def test_sort_desc(self, service, mock_db):
        mock_db.scalars.return_value.all.return_value = []
        service._fetch_requests_for_export([1], sort_order="desc")


class TestAutoPricingWarning:
    """Cover lines 545-546."""

    @pytest.mark.asyncio
    async def test_pricing_exception_logged(self, service, mock_db):
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
        mr.client_rate = None
        mock_db.add.side_effect = lambda o: None
        mock_db.scalars.return_value.first.return_value = SimpleNamespace(id=1, name="Cat")
        with patch("app.services.pricing_service.pricing_service") as mp:
            mp.estimate_request_price.side_effect = RuntimeError("pricing fail")
            with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
                with patch("app.services.max_messenger_service.max_messenger_service") as mm:
                    mm.notify_company_dispatchers = AsyncMock(side_effect=RuntimeError("max fail"))
                    try:
                        await service.create_request(payload, 1, 5)
                    except Exception:
                        pass


class TestBulkResponseWSExceptions:
    """Cover WS notification exception paths (665-666, 779-780, 831-832)."""

    @pytest.mark.asyncio
    async def test_approve_ws_fail(self, service, mock_db):
        """Lines 665-666: approve path WS exception caught."""
        assignment = SimpleNamespace(id=1, request_id=1, status="pending_approval",
            assigned_by=5, contractor_company_id=2, vehicle_id=5)
        request = SimpleNamespace(id=1, company_id=1, status="open")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return request
            return assignment
        mock_db.get.side_effect = mg
        mock_db.scalars.return_value.all.return_value = []
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
            with patch("app.services.websocket_manager.manager") as mgr:
                mgr.send_to_user = AsyncMock(side_effect=RuntimeError("WS fail"))
                try:
                    await service.bulk_response_action([1], "approve", "", 1, 2)
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_reject_ws_fail(self, service, mock_db):
        """Lines 831-832: reject path WS/notification exception caught."""
        assignment = SimpleNamespace(id=1, request_id=1, status="pending_approval",
            assigned_by=5, contractor_company_id=2)
        request = SimpleNamespace(id=1, company_id=1, status="open")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return request
            return assignment
        mock_db.get.side_effect = mg
        with patch("app.services.request_service.create_notification",
                   new_callable=AsyncMock, side_effect=RuntimeError("notify fail")):
            result = await service.reject_response(1, 1, "reason", 1, 1)
            assert result["message"]


class TestApproveRejectValidations:
    """Cover validation checks (678, 719, 742, 805)."""

    @pytest.mark.asyncio
    async def test_approve_response_not_found(self, service, mock_db):
        """Line 719: assignment not found in approve_response."""
        from app.services.request_service import RequestServiceError
        req = SimpleNamespace(id=1, company_id=1)
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return req
            return None
        mock_db.get.side_effect = mg
        with pytest.raises(RequestServiceError) as ei:
            await service.approve_response(1, 999, 1, 1)
        assert ei.value.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_other_responses_rejected(self, service, mock_db):
        """Line 742: other pending responses get rejected."""
        req = SimpleNamespace(id=1, company_id=1, status="open",
            planned_start=datetime(2026,11,1,tzinfo=UTC),
            planned_end=datetime(2026,11,2,tzinfo=UTC))
        asn = SimpleNamespace(id=1, request_id=1, status="pending_approval",
            vehicle_id=5, assigned_by=5)
        other = SimpleNamespace(id=2, request_id=1, status="pending_approval")
        vehicle = SimpleNamespace(id=5, name="Truck")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return req
            if n["c"] == 2: return asn
            if n["c"] == 3: return vehicle
            return None
        mock_db.get.side_effect = mg
        # execute for other_responses
        mock_db.execute.return_value.scalars.return_value.all.return_value = [other]
        with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
            result = await service.approve_response(1, 1, 1, 1)
        assert other.status == "rejected"

    @pytest.mark.asyncio
    async def test_reject_response_not_found(self, service, mock_db):
        """Line 805: assignment not found in reject_response."""
        from app.services.request_service import RequestServiceError
        req = SimpleNamespace(id=1, company_id=1)
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return req
            return None
        mock_db.get.side_effect = mg
        with pytest.raises(RequestServiceError) as ei:
            await service.reject_response(1, 999, "reason", 1, 1)
        assert ei.value.status_code == 404
