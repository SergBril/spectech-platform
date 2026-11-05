from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.request_service import RequestService, RequestServiceError


@pytest.fixture
def mock_db():
    db = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    svc = RequestService.__new__(RequestService)
    svc.db = mock_db
    return svc


class TestCreateRequest:
    """Tests for RequestService.create_request"""

    @pytest.mark.asyncio
    async def test_create_request_success(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.id = 42
        mock_request.status = "new"
        mock_request.work_type = "earthworks"
        mock_request.planned_start = datetime(2026, 12, 1, 8, 0, tzinfo=UTC)
        mock_request.planned_end = datetime(2026, 12, 1, 18, 0, tzinfo=UTC)
        mock_request.estimated_amount = None
        mock_request.client_rate = None
        mock_request.rate_type = None
        mock_request.region = "moscow"
        mock_request.shift_duration_hours = None
        mock_request.object_address = "Moscow"

        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with (
            patch("app.services.request_service.Request") as MockRequest,
            patch("app.services.request_service.RequestStatusLog"),
            patch(
                "app.services.request_service.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            MockRequest.return_value = mock_request
            result = await service.create_request(
                payload_data={
                    "work_type": "earthworks",
                    "object_address": "Moscow, Test St",
                    "planned_start": "2026-12-01T08:00:00",
                    "planned_end": "2026-12-01T18:00:00",
                },
                company_id=7,
                user_id=1,
            )

        assert result is not None
        mock_db.add.assert_called()
        assert mock_db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_create_request_invalid_dates(self, service, mock_db):
        with pytest.raises(RequestServiceError) as exc_info:
            await service.create_request(
                payload_data={
                    "work_type": "earthworks",
                    "object_address": "Moscow",
                    "planned_start": "2026-12-02T08:00:00",
                    "planned_end": "2026-12-01T18:00:00",
                },
                company_id=7,
                user_id=1,
            )
        assert exc_info.value.status_code == 422


class TestApproveResponse:
    """Tests for RequestService.approve_response"""

    @pytest.mark.asyncio
    async def test_approve_success(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 7
        mock_request.status = "has_responses"
        mock_request.planned_start = datetime(2026, 12, 1, 8, 0, tzinfo=UTC)
        mock_request.planned_end = datetime(2026, 12, 1, 18, 0, tzinfo=UTC)

        mock_assignment = MagicMock()
        mock_assignment.request_id = 1
        mock_assignment.vehicle_id = 10
        mock_assignment.status = "pending_approval"
        mock_assignment.assigned_by = 5

        mock_vehicle = MagicMock()
        mock_vehicle.current_driver_id = 3
        mock_vehicle.name = "CAT 320"

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "Request":
                return mock_request
            if name == "RequestAssignment":
                return mock_assignment
            if name == "Vehicle":
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        with (
            patch("app.services.request_service.ShiftTask") as MockShiftTask,
            patch(
                "app.services.request_service.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            mock_shift = MagicMock()
            mock_shift.id = 99
            MockShiftTask.return_value = mock_shift

            result = await service.approve_response(
                request_id=1,
                assignment_id=100,
                company_id=7,
                user_id=1,
            )

        assert result["message"] == "Отклик одобрен, смена создана"
        assert "shift_task_id" in result
        assert mock_assignment.status == "approved"

    @pytest.mark.asyncio
    async def test_approve_not_found(self, service, mock_db):
        mock_db.get = MagicMock(return_value=None)

        with pytest.raises(RequestServiceError) as exc_info:
            await service.approve_response(
                request_id=999,
                assignment_id=100,
                company_id=7,
                user_id=1,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_already_processed(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 7

        mock_assignment = MagicMock()
        mock_assignment.request_id = 1
        mock_assignment.status = "approved"

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "Request":
                return mock_request
            return mock_assignment

        mock_db.get = MagicMock(side_effect=get_side_effect)

        with pytest.raises(RequestServiceError) as exc_info:
            await service.approve_response(
                request_id=1,
                assignment_id=100,
                company_id=7,
                user_id=1,
            )
        assert exc_info.value.status_code == 409
        assert "already" in str(exc_info.value.detail).lower()


class TestRejectResponse:
    """Tests for RequestService.reject_response"""

    @pytest.mark.asyncio
    async def test_reject_success(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 7
        mock_request.status = "has_responses"

        mock_assignment = MagicMock()
        mock_assignment.request_id = 1
        mock_assignment.status = "pending_approval"
        mock_assignment.assigned_by = 5

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "Request":
                return mock_request
            return mock_assignment

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        with patch(
            "app.services.request_service.create_notification", new_callable=AsyncMock
        ):
            result = await service.reject_response(
                request_id=1,
                assignment_id=100,
                reason="Выбран другой",
                company_id=7,
                user_id=1,
            )

        assert result["message"] == "Отклик отклонён"
        assert mock_assignment.status == "rejected"

    @pytest.mark.asyncio
    async def test_reject_access_denied(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 99

        mock_assignment = MagicMock()
        mock_assignment.request_id = 1

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "Request":
                return mock_request
            return mock_assignment

        mock_db.get = MagicMock(side_effect=get_side_effect)

        with pytest.raises(RequestServiceError) as exc_info:
            await service.reject_response(
                request_id=1,
                assignment_id=100,
                reason="",
                company_id=7,
                user_id=1,
            )
        assert exc_info.value.status_code == 404


class TestUpdateRequestPut:
    """Tests for RequestService.update_request_put"""

    def test_update_success(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 7
        mock_request.status = "draft"
        mock_request.work_type = "old_type"
        mock_request.object_address = "Old address"

        mock_db.get = MagicMock(return_value=mock_request)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        result = service.update_request_put(
            request_id=1,
            company_id=7,
            user_id=1,
            work_type="earthworks",
            object_address="New address",
        )

        assert result["message"] == "Заявка обновлена"
        assert mock_request.work_type == "earthworks"
        assert mock_request.object_address == "New address"
        mock_db.add.assert_called_once()

    def test_update_assigned_request_blocked(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 7
        mock_request.status = "assigned"

        mock_db.get = MagicMock(return_value=mock_request)

        with pytest.raises(RequestServiceError) as exc_info:
            service.update_request_put(
                request_id=1,
                company_id=7,
                user_id=1,
                work_type="new_type",
            )
        assert exc_info.value.status_code == 409

    def test_update_no_changes_no_log(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 7
        mock_request.status = "draft"
        mock_request.work_type = "same_type"

        mock_db.get = MagicMock(return_value=mock_request)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        result = service.update_request_put(
            request_id=1,
            company_id=7,
            user_id=1,
            work_type="same_type",
        )

        assert result["message"] == "Заявка обновлена"
        mock_db.add.assert_not_called()


class TestGetRequestTimeline:
    """Tests for RequestService.get_request_timeline"""

    def test_timeline_owner_access(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 7

        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.from_status = "draft"
        mock_log.to_status = "published"
        mock_log.comment = "Published"
        mock_log.changed_by_user_id = 1
        mock_log.created_at = datetime(2026, 11, 1, tzinfo=UTC)

        mock_user = MagicMock()
        mock_user.full_name = "Test User"
        mock_user.email = "test@test.com"

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "Request":
                return mock_request
            if name in ("User", "UserModel"):
                return mock_user
            return mock_user

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_log]

        result = service.get_request_timeline(request_id=1, company_id=7)

        assert len(result) == 1
        assert result[0]["from_status"] == "draft"
        assert result[0]["to_status"] == "published"
        assert result[0]["changed_by"] == "Test User"

    def test_timeline_access_denied(self, service, mock_db):
        mock_request = MagicMock()
        mock_request.company_id = 99

        mock_db.get = MagicMock(return_value=mock_request)
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with pytest.raises(RequestServiceError) as exc_info:
            service.get_request_timeline(request_id=1, company_id=7)
        assert exc_info.value.status_code == 403
