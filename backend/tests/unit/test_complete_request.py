"""Unit tests for RequestService.complete_request."""

from decimal import Decimal
from unittest.mock import Mock, patch

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
        return db

    @pytest.fixture
    def request_service(self, mock_db):
        from app.services.request_service import RequestService

        return RequestService(mock_db)

    @pytest.mark.asyncio
    async def test_complete_request_not_found(self, request_service, mock_db):
        """Request not found raises 404."""
        mock_db.get = Mock(return_value=None)

        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc_info:
            await request_service.complete_request(
                request_id=999, company_id=1, user_id=1
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_request_wrong_company(self, request_service, mock_db):
        """Request from another company raises 404."""
        from app.models.dispatch import Request

        request = Mock(spec=Request)
        request.id = 1
        request.company_id = 2  # Different company
        mock_db.get = Mock(return_value=request)

        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc_info:
            await request_service.complete_request(
                request_id=1, company_id=1, user_id=1
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_request_wrong_status(self, request_service, mock_db):
        """Request in wrong status raises 409."""
        from app.models.dispatch import Request, RequestStatus

        request = Mock(spec=Request)
        request.id = 1
        request.company_id = 1
        request.status = RequestStatus.new  # Not allowed
        mock_db.get = Mock(return_value=request)

        from app.services.request_service import RequestServiceError

        with pytest.raises(RequestServiceError) as exc_info:
            await request_service.complete_request(
                request_id=1, company_id=1, user_id=1
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_complete_request_with_explicit_amount(
        self, request_service, mock_db
    ):
        """Complete request with explicitly provided final_amount."""
        from app.models.dispatch import Request, RequestStatus

        request = Mock(spec=Request)
        request.id = 1
        request.company_id = 1
        request.client_id = 10
        request.status = RequestStatus.assigned
        request.estimated_amount = None
        request.client_rate = None
        request.shift_duration_hours = None

        mock_db.get = Mock(return_value=request)

        # Mock Act creation
        with patch(
            "app.services.request_service.generate_document_number",
            return_value="ACT-2026-0001",
        ):
            with patch(
                "app.services.request_service.generate_and_save_act_pdf",
                return_value=None,
            ):
                result = await request_service.complete_request(
                    request_id=1,
                    company_id=1,
                    user_id=1,
                    final_amount=50000.0,
                    comment="Test completion",
                )

        assert result.status == RequestStatus.completed
        assert result.final_amount == Decimal("50000")
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_complete_request_with_estimated_amount(
        self, request_service, mock_db
    ):
        """Complete request uses estimated_amount if no explicit amount."""
        from app.models.dispatch import Request, RequestStatus

        request = Mock(spec=Request)
        request.id = 1
        request.company_id = 1
        request.client_id = 10
        request.status = RequestStatus.in_progress
        request.estimated_amount = Decimal("75000")
        request.client_rate = None
        request.shift_duration_hours = None

        mock_db.get = Mock(return_value=request)

        with patch(
            "app.services.request_service.generate_document_number",
            return_value="ACT-2026-0002",
        ):
            with patch(
                "app.services.request_service.generate_and_save_act_pdf",
                return_value=None,
            ):
                result = await request_service.complete_request(
                    request_id=1, company_id=1, user_id=1
                )

        assert result.final_amount == Decimal("75000")

    @pytest.mark.asyncio
    async def test_complete_request_calculated_from_rate(
        self, request_service, mock_db
    ):
        """Complete request calculates final_amount from rate * hours."""
        from app.models.dispatch import Request, RequestStatus

        request = Mock(spec=Request)
        request.id = 1
        request.company_id = 1
        request.client_id = 10
        request.status = RequestStatus.confirmed
        request.estimated_amount = None
        request.client_rate = Decimal("5000")
        request.shift_duration_hours = Decimal("8")

        mock_db.get = Mock(return_value=request)

        with patch(
            "app.services.request_service.generate_document_number",
            return_value="ACT-2026-0003",
        ):
            with patch(
                "app.services.request_service.generate_and_save_act_pdf",
                return_value=None,
            ):
                result = await request_service.complete_request(
                    request_id=1, company_id=1, user_id=1
                )

        assert result.final_amount == Decimal("40000")  # 5000 * 8

    @pytest.mark.asyncio
    async def test_complete_request_no_act_if_zero_amount(
        self, request_service, mock_db
    ):
        """No Act created if final_amount is zero."""
        from app.models.dispatch import Request, RequestStatus

        request = Mock(spec=Request)
        request.id = 1
        request.company_id = 1
        request.client_id = 10
        request.status = RequestStatus.assigned
        request.estimated_amount = None
        request.client_rate = None
        request.shift_duration_hours = None

        mock_db.get = Mock(return_value=request)
        mock_db.add = Mock()

        result = await request_service.complete_request(
            request_id=1, company_id=1, user_id=1
        )

        # final_amount should be 0, no Act created
        assert result.final_amount == Decimal("0")
        # Check that no Act was added (only RequestStatusLog)
        added_objects = [call[0][0] for call in mock_db.add.call_args_list]
        act_added = any("Act" in type(obj).__name__ for obj in added_objects)
        assert not act_added
