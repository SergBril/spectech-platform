"""Точечные тесты для request_service.py: 233, 665-666, 678."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# === Line 233: re-raise RequestServiceError in assign_vehicle ===
class TestAssignVehicleReraise:
    @pytest.mark.asyncio
    async def test_reraise_request_service_error(self, db_session, company):
        from app.services.request_service import RequestService, RequestServiceError
        from app.models.catalog import Vehicle
        from app.models.dispatch import Request

        svc = RequestService(db_session)

        req = Request(company_id=company.id, status="open")
        db_session.add(req)
        v = Vehicle(name="Test", company_id=company.id, status="free", id_type="internal", id_value="TEST-RERAISE")
        db_session.add(v)
        db_session.commit()
        db_session.refresh(req)
        db_session.refresh(v)

        # First assign
        try:
            await svc.assign_vehicle(req.id, v.id, None, company.id, 1)
        except Exception:
            pass

        # Second assign -> IntegrityError -> RequestServiceError(409) -> line 233
        with pytest.raises(RequestServiceError) as exc_info:
            await svc.assign_vehicle(req.id, v.id, None, company.id, 1)
        assert exc_info.value.status_code == 409


# === Lines 665-666: exception in WS send during approve ===
class TestBulkResponseApproveWsFail:
    @pytest.mark.asyncio
    async def test_approve_ws_exception_swallowed(self, db_session, company):
        from app.services.request_service import RequestService
        from app.models.dispatch import RequestAssignment, Request

        svc = RequestService(db_session)

        req = Request(company_id=company.id, status="open")
        db_session.add(req)
        db_session.flush()

        assignment = RequestAssignment(
            request_id=req.id, assigned_by=999, status="pending",
            company_id=company.id,
        )
        db_session.add(assignment)
        db_session.commit()
        db_session.refresh(assignment)

        with patch("app.services.request_service.manager") as mock_mgr:
            mock_mgr.send_to_user = AsyncMock(side_effect=Exception("WS down"))
            with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
                result = await svc.bulk_response_action(
                    assignment_ids=[assignment.id],
                    action="approve",
                    reason="",
                    company_id=company.id,
                    user_id=1,
                )
                assert result is not None


# === Line 678: WS send during reject ===
class TestBulkResponseRejectWs:
    @pytest.mark.asyncio
    async def test_reject_ws_send(self, db_session, company):
        from app.services.request_service import RequestService
        from app.models.dispatch import RequestAssignment, Request

        svc = RequestService(db_session)

        req = Request(company_id=company.id, status="open")
        db_session.add(req)
        db_session.flush()

        assignment = RequestAssignment(
            request_id=req.id, assigned_by=888, status="pending",
            company_id=company.id,
        )
        db_session.add(assignment)
        db_session.commit()
        db_session.refresh(assignment)

        with patch("app.services.request_service.manager") as mock_mgr:
            mock_mgr.send_to_user = AsyncMock(return_value=None)
            with patch("app.services.request_service.create_notification", new_callable=AsyncMock):
                result = await svc.bulk_response_action(
                    assignment_ids=[assignment.id],
                    action="reject",
                    reason="Выбран другой",
                    company_id=company.id,
                    user_id=1,
                )
                assert result is not None
                mock_mgr.send_to_user.assert_called()
