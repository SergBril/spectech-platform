from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mobile_shift_service import (
    MobileShiftServiceError,
    get_pre_shift_checklist,
    submit_mobile_shift_report,
)


@pytest.fixture
def mock_db():
    return MagicMock()


class TestSubmitMobileShiftReport:
    """Tests for submit_mobile_shift_report"""

    @pytest.mark.asyncio
    async def test_submit_success(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.operator_id = 42
        mock_task.status = "in_progress"

        mock_profile = MagicMock()
        mock_profile.employee_contractor_id = 42

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask":
                return mock_task
            if name == "Vehicle":
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.execute = MagicMock()
        # First call: profile lookup, Second: dispatchers
        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = mock_profile
        dispatchers_result = MagicMock()
        dispatchers_result.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [profile_result, dispatchers_result]
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        mock_report = MagicMock()
        mock_report.id = 99
        mock_db.refresh.side_effect = lambda r: (
            setattr(r, "id", 99) if not hasattr(r, "id") or r.id is None else None
        )

        with (
            patch("app.services.websocket_manager.manager") as mock_manager,
            patch("app.services.fcm_service.fcm_service") as mock_fcm,
        ):
            mock_manager.broadcast_to_company = AsyncMock()
            mock_fcm.send_to_user = AsyncMock()

            result = await submit_mobile_shift_report(
                db=mock_db,
                task_id=1,
                user_id=5,
                odometer_start=10000.0,
                odometer_end=10150.5,
                notes="All good",
            )

        assert result["message"] == "Отчёт отправлен"
        assert result["photos_uploaded"] == 0
        assert mock_task.status == "completed"
        assert mock_task.odometer_distance == 150.5

    @pytest.mark.asyncio
    async def test_submit_not_found(self, mock_db):
        mock_db.get = MagicMock(return_value=None)

        with pytest.raises(MobileShiftServiceError) as exc_info:
            await submit_mobile_shift_report(db=mock_db, task_id=999, user_id=5)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_access_denied(self, mock_db):
        mock_task = MagicMock()
        mock_task.operator_id = 42

        mock_profile = MagicMock()
        mock_profile.employee_contractor_id = 99  # Different driver

        mock_db.get = MagicMock(return_value=mock_task)
        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = mock_profile
        mock_db.execute = MagicMock(return_value=profile_result)

        with pytest.raises(MobileShiftServiceError) as exc_info:
            await submit_mobile_shift_report(db=mock_db, task_id=1, user_id=5)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_submit_no_profile(self, mock_db):
        mock_task = MagicMock()
        mock_task.operator_id = 42

        mock_db.get = MagicMock(return_value=mock_task)
        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = None
        mock_db.execute = MagicMock(return_value=profile_result)

        with pytest.raises(MobileShiftServiceError) as exc_info:
            await submit_mobile_shift_report(db=mock_db, task_id=1, user_id=5)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_submit_with_photos(self, mock_db, tmp_path):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.operator_id = 42
        mock_task.status = "in_progress"

        mock_profile = MagicMock()
        mock_profile.employee_contractor_id = 42

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask":
                return mock_task
            if name == "Vehicle":
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = mock_profile
        dispatchers_result = MagicMock()
        dispatchers_result.scalars.return_value.all.return_value = []
        mock_db.execute = MagicMock(side_effect=[profile_result, dispatchers_result])
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        # Mock photo file
        mock_photo = MagicMock()
        mock_photo.filename = "test.jpg"
        mock_photo.read = AsyncMock(return_value=b"fake_image_data")

        with (
            patch("app.services.websocket_manager.manager") as mock_manager,
            patch("app.services.fcm_service.fcm_service") as mock_fcm,
            patch("app.services.mobile_shift_service.os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            mock_manager.broadcast_to_company = AsyncMock()
            mock_fcm.send_to_user = AsyncMock()

            result = await submit_mobile_shift_report(
                db=mock_db,
                task_id=1,
                user_id=5,
                photo_files=[mock_photo],
            )

        assert result["photos_uploaded"] == 1


class TestGetPreShiftChecklist:
    """Tests for get_pre_shift_checklist"""

    def test_not_found(self, mock_db):
        mock_db.get = MagicMock(return_value=None)

        with pytest.raises(MobileShiftServiceError) as exc_info:
            get_pre_shift_checklist(mock_db, task_id=999, company_id=7)
        assert exc_info.value.status_code == 404

    def test_access_denied(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 99

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask":
                return mock_task
            if name == "Vehicle":
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)

        with pytest.raises(MobileShiftServiceError) as exc_info:
            get_pre_shift_checklist(mock_db, task_id=1, company_id=7)
        assert exc_info.value.status_code == 403

    def test_default_items_when_no_config(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7
        mock_vehicle.category_id = None

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask":
                return mock_task
            if name == "Vehicle":
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        # No config found, no existing checklist
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = get_pre_shift_checklist(mock_db, task_id=1, company_id=7)

        assert result["submitted"] is False
        assert len(result["items"]) == 9  # Default items
        assert any(item["key"] == "tires" for item in result["items"])

    def test_already_submitted(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7
        mock_vehicle.category_id = 1

        mock_existing = MagicMock()
        mock_existing.submitted_at = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        mock_existing.checklist_json = '[{"key": "tires", "value": "ok"}]'
        mock_existing.notes = "All good"
        mock_existing.has_issues = False

        def get_side_effect(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask":
                return mock_task
            if name == "Vehicle":
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        # Config not found, but existing checklist found
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = mock_existing
        mock_db.execute = MagicMock(
            side_effect=[config_result, config_result, existing_result]
        )

        result = get_pre_shift_checklist(mock_db, task_id=1, company_id=7)

        assert result["submitted"] is True
        assert result["has_issues"] is False
        assert result["notes"] == "All good"
        assert len(result["items"]) == 1
