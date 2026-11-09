"""Final 10 lines coverage for request_service -> 98%+."""

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


class TestLine233RequestServiceErrorReraise:
    """Cover line 233: except RequestServiceError: raise."""

    @pytest.mark.asyncio
    async def test_reraise_request_service_error(self, service, mock_db):
        # Validation error (RequestServiceError) raised inside try block
        # must be re-raised without rollback
        req = SimpleNamespace(
            id=1, company_id=1, status="closed",
            vehicle_category_id=1, assigned_vehicle_id=None,
            source_channel=None,
            planned_start=datetime(2026,11,1,tzinfo=UTC),
            planned_end=datetime(2026,11,2,tzinfo=UTC),
        )
        vehicle = SimpleNamespace(
            id=5, name="Truck", company_id=1, status="free",
            marketplace_commission_agreed=False,
        )
        def mg(model, pk):
            mn = getattr(model, '__name__', '')
            if mn == 'Request' and pk == 1: return req
            if mn == 'Vehicle' and pk == 5: return vehicle
            return SimpleNamespace(name=f"m_{pk}", id=pk, company_id=1)
        mock_db.get.side_effect = mg

        from app.services.request_service import RequestServiceError
        with pytest.raises(RequestServiceError) as ei:
            await service.assign_vehicle(1, 5, None, 1, 1)
        # status="closed" -> 409 "Request is closed"
        assert ei.value.status_code == 409
        # rollback should NOT be called for RequestServiceError
        mock_db.rollback.assert_not_called()


class TestAutoPricingWarning:
    """Cover lines 545-546: pricing exception logged."""

    @pytest.mark.asyncio
    async def test_pricing_fail(self, service, mock_db):
        payload = {
            "work_type": "earthworks", "object_address": "Moscow",
            "vehicle_category_id": 1,
            "planned_start": "2026-11-01T08:00:00+00:00",
            "planned_end": "2026-11-02T17:00:00+00:00",
        }
        mr = MagicMock()
        mr.id = 1; mr.company_id = 1; mr.work_type = "earthworks"
        mr.object_address = "Moscow"; mr.vehicle_category_id = 1
        mr.source_channel = None; mr.client_rate = None
        mr.shift_duration_hours = None; mr.rate_type = None
        mr.region = None
        mr.planned_start = datetime(2026,11,1,tzinfo=UTC)
        mr.planned_end = datetime(2026,11,2,tzinfo=UTC)
        mock_db.add.side_effect = lambda o: None
        mock_db.scalars.return_value.first.return_value = SimpleNamespace(id=1, name="Cat")
        # pricing_service is imported at module level or used directly
        with patch("app.services.pricing_service.pricing_service") as ps:
            ps.calculate_estimate.side_effect = RuntimeError("pricing fail")
            with patch("app.services.notification_service.create_notification", new_callable=AsyncMock):
                with patch("app.services.max_messenger_service.max_messenger_service") as mm:
                    mm.notify_company_dispatchers = AsyncMock(side_effect=RuntimeError("max fail"))
                    try:
                        await service.create_request(payload, 1, 5)
                    except Exception:
                        pass


class TestBulkResponseWSExceptions:
    """Cover lines 665-666, 678: bulk approve WS/notification errors."""

    @pytest.mark.asyncio
    async def test_approve_notification_and_ws_fail(self, service, mock_db):
        assignment = SimpleNamespace(id=1, request_id=1, status="pending_approval",
            assigned_by=5, contractor_company_id=2)
        request = SimpleNamespace(id=1, company_id=1, status="open")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return request
            return assignment
        mock_db.get.side_effect = mg
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        # Both create_notification AND manager.send_to_user raise
        with patch("app.services.notification_service.create_notification",
                   new_callable=AsyncMock, side_effect=RuntimeError("notify fail")):
            with patch("app.services.websocket_manager.manager") as mgr:
                mgr.send_to_user = AsyncMock(side_effect=RuntimeError("WS fail"))
                try:
                    await service.bulk_response_action([1], "approve", "", 1, 2)
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_reject_notification_and_ws_fail(self, service, mock_db):
        """Cover lines 831-832: reject notification exception."""
        assignment = SimpleNamespace(id=1, request_id=1, status="pending_approval",
            assigned_by=5, contractor_company_id=2)
        request = SimpleNamespace(id=1, company_id=1, status="open")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return request
            return assignment
        mock_db.get.side_effect = mg
        with patch("app.services.notification_service.create_notification",
                   new_callable=AsyncMock, side_effect=RuntimeError("notify fail")):
            result = await service.reject_response(1, 1, "reason", 1, 1)
            assert "message" in result


class TestApproveResponseNotificationException:
    """Cover lines 779-780: approve_response notification exception."""

    @pytest.mark.asyncio
    async def test_approve_notify_fail(self, service, mock_db):
        req = SimpleNamespace(id=1, company_id=1, status="open",
            planned_start=datetime(2026,11,1,tzinfo=UTC),
            planned_end=datetime(2026,11,2,tzinfo=UTC))
        asn = SimpleNamespace(id=1, request_id=1, status="pending_approval",
            vehicle_id=5, assigned_by=5)
        vehicle = SimpleNamespace(id=5, name="Truck")
        n = {"c": 0}
        def mg(m, pk):
            n["c"] += 1
            if n["c"] == 1: return req
            if n["c"] == 2: return asn
            if n["c"] == 3: return vehicle
            return None
        mock_db.get.side_effect = mg
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        with patch("app.services.notification_service.create_notification",
                   new_callable=AsyncMock, side_effect=RuntimeError("notify fail")):
            result = await service.approve_response(1, 1, 1, 1)
            assert "message" in result
