"""Extra tests for mobile_shift_service missing lines -> 100%."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mobile_shift_service import (
    get_pre_shift_checklist,
    submit_mobile_shift_report,
)


def _setup_submit_mocks(mock_db, dispatchers=None, profile=None):
    mock_task = MagicMock()
    mock_task.vehicle_id = 10
    mock_task.operator_id = 42
    mock_task.status = "in_progress"
    mock_vehicle = MagicMock()
    mock_vehicle.company_id = 7
    if profile is None:
        profile = MagicMock()
        profile.employee_contractor_id = 42

    def get_side_effect(model, id):
        name = getattr(model, "__name__", str(model))
        if name == "ShiftTask": return mock_task
        if name == "Vehicle": return mock_vehicle
        return None

    mock_db.get = MagicMock(side_effect=get_side_effect)
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = profile
    dispatchers_result = MagicMock()
    dispatchers_result.scalars.return_value.all.return_value = dispatchers or []
    mock_db.execute.side_effect = [profile_result, dispatchers_result]
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock(side_effect=lambda r: setattr(r, "id", 99) if not hasattr(r, "id") or r.id is None else None)
    return mock_task


class TestSubmitBroadcastException:
    """Cover lines 104-105: except Exception after broadcast."""

    @pytest.mark.asyncio
    async def test_broadcast_exception_swallowed(self):
        mock_db = MagicMock()
        _setup_submit_mocks(mock_db)
        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.fcm_service.fcm_service") as mock_fcm,
        ):
            mock_mgr.broadcast_to_company = AsyncMock(side_effect=RuntimeError("ws down"))
            mock_fcm.send_to_user = AsyncMock()
            result = await submit_mobile_shift_report(
                db=mock_db, task_id=1, user_id=5,
                odometer_start=10000.0, odometer_end=10150.5,
            )
        assert result["message"] == "Отчёт отправлен"


class TestSubmitFCMNotification:
    """Cover lines 118-126: FCM send + except."""

    @pytest.mark.asyncio
    async def test_fcm_sent_to_dispatchers(self):
        mock_db = MagicMock()
        _setup_submit_mocks(mock_db, dispatchers=[100, 200])
        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.fcm_service.fcm_service") as mock_fcm,
        ):
            mock_mgr.broadcast_to_company = AsyncMock()
            mock_fcm.send_to_user = AsyncMock()
            result = await submit_mobile_shift_report(
                db=mock_db, task_id=1, user_id=5,
                odometer_start=10000.0, odometer_end=10150.5,
            )
        assert result["message"] == "Отчёт отправлен"
        assert mock_fcm.send_to_user.call_count == 2

    @pytest.mark.asyncio
    async def test_fcm_exception_swallowed(self):
        mock_db = MagicMock()
        _setup_submit_mocks(mock_db, dispatchers=[100])
        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.fcm_service.fcm_service") as mock_fcm,
        ):
            mock_mgr.broadcast_to_company = AsyncMock()
            mock_fcm.send_to_user = AsyncMock(side_effect=RuntimeError("fcm down"))
            result = await submit_mobile_shift_report(
                db=mock_db, task_id=1, user_id=5,
                odometer_start=10000.0, odometer_end=10150.5,
            )
        assert result["message"] == "Отчёт отправлен"


class TestGetPreShiftChecklistJsonParse:
    """Cover lines 168-171: json.loads success + exception."""

    def test_valid_items_json(self):
        mock_db = MagicMock()
        items = [{"key": "brakes", "label": "Тормоза", "required": True}]
        mock_config = MagicMock()
        mock_config.items_json = json.dumps(items)
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.operator_id = 42
        mock_vehicle = MagicMock()
        mock_vehicle.category_id = 5
        mock_vehicle.company_id = 7
        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask": return mock_task
            if name == "Vehicle": return mock_vehicle
            return None
        mock_db.get = MagicMock(side_effect=get_se)
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = mock_config
        submitted_result = MagicMock()
        submitted_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [submitted_result, config_result]
        result = get_pre_shift_checklist(mock_db, task_id=1, company_id=7)
        assert result["items"] == items

    def test_invalid_items_json(self):
        mock_db = MagicMock()
        mock_config = MagicMock()
        mock_config.items_json = "not valid json{{{"
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.operator_id = 42
        mock_vehicle = MagicMock()
        mock_vehicle.category_id = 5
        mock_vehicle.company_id = 7
        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask": return mock_task
            if name == "Vehicle": return mock_vehicle
            return None
        mock_db.get = MagicMock(side_effect=get_se)
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = mock_config
        submitted_result = MagicMock()
        submitted_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [submitted_result, config_result]
        result = get_pre_shift_checklist(mock_db, task_id=1, company_id=7)
        assert result["items"] == []
