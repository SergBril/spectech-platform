"""Unit tests for RequestService.complete_request."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest


class TestCompleteRequest:
    """Cover request_service.py complete_request method."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.add = Mock()
        db.flush = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.get = Mock()
        db.scalar = Mock(return_value=None)
        return db

    @pytest.fixture
    def request_service(self, mock_db):
        from app.services.request_service import RequestService

        return RequestService(mock_db)

    def _make_request(self, status, **kwargs):
        from app.models.dispatch import Request

        req = Mock(spec=Request)
        req.id = kwargs.get("id", 1)
        req.company_id = kwargs.get("company_id", 1)
        req.client_id = kwargs.get("client_id", 10)
        req.status = status
        req.estimated_amount = kwargs.get("estimated_amount")
        req.client_rate = kwargs.get("client_rate")
        req.shift_duration_hours = kwargs.get("shift_duration_hours")
        req.final_amount = None
        req.actual_end = None
        return req

    @pytest.mark.asyncio
    async def test_not_found(self, request_service, mock_db):
        mock_db.get = Mock(return_value=None)
        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc:
            await request_service.complete_request(999, 1, 1)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_company(self, request_service, mock_db):
        from app.models.dispatch import RequestStatus

        req = self._make_request(RequestStatus.assigned, company_id=2)
        mock_db.get = Mock(return_value=req)
        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc:
            await request_service.complete_request(1, 1, 1)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_status(self, request_service, mock_db):
        from app.models.dispatch import RequestStatus

        req = self._make_request(RequestStatus.new)
        mock_db.get = Mock(return_value=req)
        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc:
            await request_service.complete_request(1, 1, 1)
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_completed_status_blocked(self, request_service, mock_db):
        """Cannot complete already completed request."""
        from app.models.dispatch import RequestStatus

        req = self._make_request(RequestStatus.completed)
        mock_db.get = Mock(return_value=req)
        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc:
            await request_service.complete_request(1, 1, 1)
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_explicit_amount(self, request_service, mock_db):
        from app.models.dispatch import RequestStatus

        req = self._make_request(RequestStatus.assigned)
        mock_db.get = Mock(return_value=req)

        result = await request_service.complete_request(1, 1, 1, final_amount=50000.0)

        assert result.status == RequestStatus.completed
        assert result.final_amount == Decimal("50000")
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_uses_estimated_amount(self, request_service, mock_db):
        from app.models.dispatch import RequestStatus

        req = self._make_request(
            RequestStatus.in_progress,
            estimated_amount=Decimal("75000"),
        )
        mock_db.get = Mock(return_value=req)

        result = await request_service.complete_request(1, 1, 1)

        assert result.final_amount == Decimal("75000")

    @pytest.mark.asyncio
    async def test_calculated_from_rate_and_hours(self, request_service, mock_db):
        from app.models.dispatch import RequestStatus

        req = self._make_request(
            RequestStatus.confirmed,
            client_rate=Decimal("5000"),
            shift_duration_hours=Decimal("8"),
        )
        mock_db.get = Mock(return_value=req)

        result = await request_service.complete_request(1, 1, 1)

        assert result.final_amount == Decimal("40000")

    @pytest.mark.asyncio
    async def test_zero_amount_no_act(self, request_service, mock_db):
        """No Act created when final_amount is zero."""
        from app.models.dispatch import RequestStatus

        req = self._make_request(RequestStatus.assigned)
        mock_db.get = Mock(return_value=req)

        result = await request_service.complete_request(1, 1, 1)

        assert result.final_amount == Decimal("0")
        added = [call[0][0] for call in mock_db.add.call_args_list]
        assert not any(type(obj).__name__ == "Act" for obj in added)

    @pytest.mark.asyncio
    async def test_positive_amount_creates_act(self, request_service, mock_db):
        """Act is created when final_amount > 0."""
        from app.models.dispatch import RequestStatus
        from app.models.finance import Act

        req = self._make_request(
            RequestStatus.assigned,
            estimated_amount=Decimal("10000"),
        )
        mock_db.get = Mock(return_value=req)

        await request_service.complete_request(1, 1, 1)

        added = [call[0][0] for call in mock_db.add.call_args_list]
        acts = [obj for obj in added if isinstance(obj, Act)]
        assert len(acts) == 1
        assert acts[0].request_id == 1
        assert acts[0].total_amount == Decimal("10000")

    @pytest.mark.asyncio
    async def test_status_log_created(self, request_service, mock_db):
        """Status transition logged in RequestStatusLog."""
        from app.models.dispatch import RequestStatus, RequestStatusLog

        req = self._make_request(RequestStatus.assigned)
        mock_db.get = Mock(return_value=req)

        await request_service.complete_request(1, 1, 42, comment="done")

        added = [call[0][0] for call in mock_db.add.call_args_list]
        logs = [obj for obj in added if isinstance(obj, RequestStatusLog)]
        assert len(logs) == 1
        assert logs[0].to_status == "completed"
        assert logs[0].changed_by_user_id == 42
        assert logs[0].comment == "done"

    @pytest.mark.asyncio
    async def test_actual_end_set(self, request_service, mock_db):
        """actual_end is set to current time."""
        from app.models.dispatch import RequestStatus

        req = self._make_request(RequestStatus.assigned)
        mock_db.get = Mock(return_value=req)

        result = await request_service.complete_request(1, 1, 1)

        assert result.actual_end is not None
        assert isinstance(result.actual_end, datetime)
