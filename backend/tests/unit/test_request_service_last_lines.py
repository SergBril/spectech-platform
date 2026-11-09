"""Точечные тесты для request_service.py: 233, 665-666, 678."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace
from datetime import datetime, UTC


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


# === Line 233: re-raise RequestServiceError on IntegrityError ===
class TestAssignVehicleReraise:
    @pytest.mark.asyncio
    async def test_reraise_on_integrity_error(self, service, mock_db):
        from sqlalchemy.exc import IntegrityError
        from app.services.request_service import RequestServiceError

        req = SimpleNamespace(
            id=1, company_id=1, status="new",
            planned_start=datetime(2026, 11, 10, tzinfo=UTC),
            planned_end=datetime(2026, 11, 15, tzinfo=UTC),
            source_channel="direct",
        )
        vehicle = SimpleNamespace(
            id=2, company_id=1, status="active", name="Truck",
            marketplace_commission_agreed=True,
        )
        mock_db.get.side_effect = lambda m, i: req if i == 1 else vehicle

        # Make commit raise IntegrityError -> caught -> RequestServiceError(409) -> line 233 re-raise
        mock_db.commit.side_effect = IntegrityError("duplicate", None, None)

        with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
            with pytest.raises(RequestServiceError) as exc_info:
                await service.assign_vehicle(1, 2, None, 1, 1)
            assert exc_info.value.status_code == 409


# === Lines 665-666: exception in WS send during approve (swallowed) ===
class TestBulkResponseApproveWsFail:
    @pytest.mark.asyncio
    async def test_approve_ws_exception_swallowed(self, service, mock_db):
        assignment = SimpleNamespace(
            id=1, request_id=10, status="pending_approval",
            vehicle_id=2, assigned_by=5,
        )
        req = SimpleNamespace(
            id=10, company_id=1, status="new",
            planned_start=datetime(2026, 11, 10, tzinfo=UTC),
            planned_end=datetime(2026, 11, 15, tzinfo=UTC),
        )
        vehicle = SimpleNamespace(id=2, current_driver_id=7)
        other_assignment = SimpleNamespace(id=2, status="pending_approval")

        def mock_get(model, pk):
            if pk == 1: return assignment
            if pk == 10: return req
            if pk == 2: return vehicle
            return None

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalars.return_value.all.return_value = [other_assignment]

        with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
            with patch("app.services.request_service.manager") as mock_mgr:
                # WS send raises exception -> lines 665-666 catch and pass
                mock_mgr.send_to_user = AsyncMock(side_effect=Exception("WS down"))
                result = await service.bulk_response_action([1], "approve", "", 1, 1)
                assert result["processed"] == 1


# === Line 678: WS send during reject ===
class TestBulkResponseRejectWs:
    @pytest.mark.asyncio
    async def test_reject_ws_send_called(self, service, mock_db):
        assignment = SimpleNamespace(
            id=1, request_id=10, status="pending_approval",
            vehicle_id=2, assigned_by=5,
        )
        req = SimpleNamespace(id=10, company_id=1, status="new")

        mock_db.get.side_effect = lambda m, i: assignment if i == 1 else req

        with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
            with patch("app.services.request_service.manager") as mock_mgr:
                mock_mgr.send_to_user = AsyncMock(return_value=None)
                result = await service.bulk_response_action(
                    [1], "reject", "Not suitable", 1, 1,
                )
                assert result["processed"] == 1
                # Line 678: send_to_user called for reject
                mock_mgr.send_to_user.assert_called()
