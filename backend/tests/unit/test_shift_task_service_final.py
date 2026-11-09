"""Extra tests for shift_task_service missing lines -> 100%."""

import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.shift_task_service import auto_assign_driver, update_shift_task


def _make_update_mocks(task=None, vehicle=None, profile=None, emp=None):
    if task is None:
        task = MagicMock()
        task.id = 1
        task.vehicle_id = 10
        task.operator_id = 42
        task.status = "scheduled"
        task.shift_date = date(2026, 11, 9)
        task.company_id = 7
    if vehicle is None:
        vehicle = MagicMock()
        vehicle.company_id = 7

    mock_db = MagicMock()
    def get_se(model, id):
        name = getattr(model, "__name__", str(model))
        if name == "ShiftTask": return task
        if name == "Vehicle": return vehicle
        if name == "DriverProfile": return profile
        if name == "Employee": return emp
        return None
    mock_db.get = MagicMock(side_effect=get_se)
    # execute: conflict check returns None
    conflict_result = MagicMock()
    conflict_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = conflict_result
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    return mock_db, task


class TestUpdatePlannedStartEnd:
    """Cover lines 76-78: planned_start/planned_end update."""

    @pytest.mark.asyncio
    async def test_planned_start_and_end(self):
        mock_db, task = _make_update_mocks()
        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.notification_service.create_notification", new_callable=AsyncMock),
        ):
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                db=mock_db, task_id=1, user_id=5, company_id=7,
                planned_start="2026-11-09T08:00:00",
                planned_end="2026-11-09T18:00:00",
            )
        assert task.planned_start == datetime(2026, 11, 9, 8, 0, 0)
        assert task.planned_end == datetime(2026, 11, 9, 18, 0, 0)


class TestUpdateCommitException:
    """Cover lines 109-110: exception after db.commit."""

    @pytest.mark.asyncio
    async def test_commit_exception_swallowed(self):
        mock_db, task = _make_update_mocks()
        # commit raises inside try block -> caught by except Exception: pass
        mock_db.commit.side_effect = RuntimeError("db error")
        # ShiftAuditLog constructor needs to work
        with (
            patch("app.models.shift.ShiftAuditLog"),
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.notification_service.create_notification", new_callable=AsyncMock),
        ):
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                db=mock_db, task_id=1, user_id=5, company_id=7,
                status="in_progress",
            )
        assert result["message"] == "Смена обновлена"


class TestUpdateDriverNotification:
    """Cover lines 119-129: notify driver via employee."""

    @pytest.mark.asyncio
    async def test_notification_sent_to_driver(self):
        profile = MagicMock()
        profile.employee_contractor_id = 42
        emp = MagicMock()
        emp.user_id = 99
        mock_db, task = _make_update_mocks(profile=profile, emp=emp)
        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.notification_service.create_notification", new_callable=AsyncMock) as mock_notify,
        ):
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                db=mock_db, task_id=1, user_id=5, company_id=7,
                status="in_progress",
            )
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["user_id"] == 99

    @pytest.mark.asyncio
    async def test_notification_exception_swallowed(self):
        profile = MagicMock()
        profile.employee_contractor_id = 42
        emp = MagicMock()
        emp.user_id = 99
        mock_db, task = _make_update_mocks(profile=profile, emp=emp)
        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.notification_service.create_notification", new_callable=AsyncMock, side_effect=RuntimeError("notify fail")),
        ):
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                db=mock_db, task_id=1, user_id=5, company_id=7,
                status="in_progress",
            )
        assert result["message"] == "Смена обновлена"


class TestUpdateWSBroadcastException:
    """Cover lines 144-145: WS broadcast exception."""

    @pytest.mark.asyncio
    async def test_ws_exception_swallowed(self):
        mock_db, task = _make_update_mocks()
        with (
            patch("app.services.websocket_manager.manager") as mock_mgr,
            patch("app.services.notification_service.create_notification", new_callable=AsyncMock),
        ):
            mock_mgr.broadcast_to_company = AsyncMock(side_effect=RuntimeError("ws down"))
            result = await update_shift_task(
                db=mock_db, task_id=1, user_id=5, company_id=7,
                status="completed",
            )
        assert result["message"] == "Смена обновлена"


class TestAutoAssignJsonException:
    """Cover lines 195-196: json.loads exception in auto_assign."""

    def test_invalid_config_json_uses_empty(self):
        mock_db = MagicMock()
        task = MagicMock()
        task.vehicle_id = 10
        task.operator_id = None
        task.shift_date = date(2026, 11, 9)
        task.company_id = 7
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.category_id = 5
        rule = MagicMock()
        rule.config_json = "invalid{{{"
        rule.rule_type = "blacklist"
        rule.priority = 0
        profile = MagicMock()
        profile.employee_contractor_id = 42
        profile.is_active = True
        profile.vehicle_category_id = 5
        profile.license_category = "C"

        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask": return task
            if name == "Vehicle": return vehicle
            return None
        mock_db.get = MagicMock(side_effect=get_se)
        # execute: 1=rules, 2=drivers, 3=busy check, 4=week_shifts
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [rule]
        drivers_result = MagicMock()
        drivers_result.scalars.return_value.all.return_value = [profile]
        busy_result = MagicMock()
        busy_result.scalar_one_or_none.return_value = None
        week_result = MagicMock()
        week_result.scalar.return_value = 0
        mock_db.execute.side_effect = [rules_result, drivers_result, busy_result, week_result]
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        result = auto_assign_driver(mock_db, task_id=1, company_id=7)
        assert "назначен" in result["message"]


class TestAutoAssignBusyDriver:
    """Cover line 221: continue when driver is busy."""

    def test_busy_driver_skipped(self):
        mock_db = MagicMock()
        task = MagicMock()
        task.vehicle_id = 10
        task.operator_id = None
        task.shift_date = date(2026, 11, 9)
        task.company_id = 7
        vehicle = MagicMock()
        vehicle.company_id = 7
        vehicle.category_id = 5
        busy_profile = MagicMock()
        busy_profile.employee_contractor_id = 42
        busy_profile.is_active = True
        busy_profile.vehicle_category_id = 5
        busy_profile.license_category = "C"
        free_profile = MagicMock()
        free_profile.employee_contractor_id = 43
        free_profile.is_active = True
        free_profile.vehicle_category_id = 5
        free_profile.license_category = "C"

        def get_se(model, id):
            name = getattr(model, "__name__", str(model))
            if name == "ShiftTask": return task
            if name == "Vehicle": return vehicle
            return None
        mock_db.get = MagicMock(side_effect=get_se)
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = []
        drivers_result = MagicMock()
        drivers_result.scalars.return_value.all.return_value = [busy_profile, free_profile]
        # execute order: rules, drivers, busy(busy)=hit, busy(free)=none, week_shifts(free)
        busy_hit = MagicMock()
        busy_hit.scalar_one_or_none.return_value = MagicMock()
        free_hit = MagicMock()
        free_hit.scalar_one_or_none.return_value = None
        week_result = MagicMock()
        week_result.scalar.return_value = 0
        mock_db.execute.side_effect = [rules_result, drivers_result, busy_hit, free_hit, week_result]
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        result = auto_assign_driver(mock_db, task_id=1, company_id=7)
        assert "назначен" in result["message"]
        assert task.operator_id == 43
