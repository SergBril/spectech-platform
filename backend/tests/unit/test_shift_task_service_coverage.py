"""Tests for shift_task_service."""

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestShiftTaskServiceError:
    """Cover ShiftTaskServiceError (lines 14-21)."""

    def test_init(self):
        from app.services.shift_task_service import ShiftTaskServiceError

        err = ShiftTaskServiceError(404, "Not found")
        assert err.status_code == 404
        assert err.detail == "Not found"

    def test_dict_detail(self):
        from app.services.shift_task_service import ShiftTaskServiceError

        err = ShiftTaskServiceError(409, {"conflicts": ["test"]})
        assert err.status_code == 409


class TestUpdateShiftTask:
    """Cover update_shift_task (lines 23-148)."""

    @pytest.mark.asyncio
    async def test_task_not_found(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            update_shift_task,
        )

        mock_db.get.return_value = None
        with pytest.raises(ShiftTaskServiceError) as exc:
            await update_shift_task(mock_db, 999, 1, 1)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_access_denied(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            update_shift_task,
        )

        task = SimpleNamespace(vehicle_id=1, shift_date=date(2026, 11, 5))
        vehicle = SimpleNamespace(company_id=2)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return task if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get

        with pytest.raises(ShiftTaskServiceError) as exc:
            await update_shift_task(mock_db, 1, 1, 1)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_vehicle_conflict(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            update_shift_task,
        )

        task = SimpleNamespace(
            id=1,
            vehicle_id=1,
            shift_date=date(2026, 11, 5),
            status="planned",
            operator_id=None,
        )
        vehicle = SimpleNamespace(company_id=1, name="KAMAZ")
        conflict = SimpleNamespace(id=2)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return task
            return vehicle

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalar_one_or_none.return_value = conflict

        with pytest.raises(ShiftTaskServiceError) as exc:
            await update_shift_task(mock_db, 1, 1, 1, shift_date="2026-11-05")
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_success_with_changes(self, mock_db):
        from app.services.shift_task_service import update_shift_task

        task = SimpleNamespace(
            id=1,
            vehicle_id=1,
            shift_date=date(2026, 11, 5),
            status="planned",
            operator_id=None,
            planned_start=None,
            planned_end=None,
        )
        vehicle = SimpleNamespace(company_id=1, name="KAMAZ")

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return task
            if call_count["n"] == 2:
                return vehicle
            return None  # DriverProfile / Employee lookups

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalar_one_or_none.return_value = (
            None  # no conflict
        )

        with patch("app.services.websocket_manager.manager") as mock_mgr:
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                mock_db,
                1,
                1,
                1,
                shift_date="2026-11-06",
                status="in_progress",
            )

        assert result["message"] == "Смена обновлена"
        assert len(result["changes"]) == 2
        mock_db.commit.assert_called()


class TestAutoAssignDriver:
    """Cover auto_assign_driver (lines 150-269)."""

    def test_task_not_found(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            auto_assign_driver,
        )

        mock_db.get.return_value = None
        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 999, 1)
        assert exc.value.status_code == 404

    def test_already_assigned(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            auto_assign_driver,
        )

        task = SimpleNamespace(
            vehicle_id=1, operator_id=10, shift_date=date(2026, 11, 5)
        )
        vehicle = SimpleNamespace(company_id=1)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return task if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get

        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 1, 1)
        assert exc.value.status_code == 409

    def test_no_available_drivers(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            auto_assign_driver,
        )

        task = SimpleNamespace(
            vehicle_id=1, operator_id=None, shift_date=date(2026, 11, 5)
        )
        vehicle = SimpleNamespace(company_id=1, category="B")

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return task
            return vehicle

        mock_db.get.side_effect = mock_get

        # No drivers found
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 1, 1)
        assert exc.value.status_code == 404

    def test_success_assigns_best_driver(self, mock_db):
        from app.services.shift_task_service import auto_assign_driver

        task = SimpleNamespace(
            vehicle_id=1, operator_id=None, shift_date=date(2026, 11, 5)
        )
        vehicle = SimpleNamespace(company_id=1, category="C")
        profile = SimpleNamespace(employee_contractor_id=10, license_category="C")
        emp = SimpleNamespace(first_name="Иван", last_name="Петров")
        rule = SimpleNamespace(
            rule_type="priority_driver",
            priority=5,
            config_json=json.dumps({"driver_ids": [10]}),
        )

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return task
            if call_count["n"] == 2:
                return vehicle
            return emp  # Employee lookup at end

        mock_db.get.side_effect = mock_get

        execute_count = {"n": 0}

        def mock_execute(stmt):
            execute_count["n"] += 1
            mr = MagicMock()
            if execute_count["n"] == 1:
                mr.scalars.return_value.all.return_value = [profile]  # drivers
            elif execute_count["n"] == 2:
                mr.scalars.return_value.all.return_value = [rule]  # rules
            elif execute_count["n"] == 3:
                mr.scalar_one_or_none.return_value = None  # not busy
            else:
                mr.scalar.return_value = 2  # week shifts
            return mr

        mock_db.execute.side_effect = mock_execute

        result = auto_assign_driver(mock_db, 1, 1)
        assert result["driver_id"] == 10
        assert result["driver_name"] == "Иван Петров"
        assert result["score"] > 0
        mock_db.commit.assert_called()

    def test_blacklisted_driver_skipped(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            auto_assign_driver,
        )

        task = SimpleNamespace(
            vehicle_id=1, operator_id=None, shift_date=date(2026, 11, 5)
        )
        vehicle = SimpleNamespace(company_id=1, category="B")
        profile = SimpleNamespace(employee_contractor_id=10, license_category="B")
        rule = SimpleNamespace(
            rule_type="blacklist",
            priority=1,
            config_json=json.dumps({"driver_ids": [10]}),
        )

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return task
            return vehicle

        mock_db.get.side_effect = mock_get

        execute_count = {"n": 0}

        def mock_execute(stmt):
            execute_count["n"] += 1
            mr = MagicMock()
            if execute_count["n"] == 1:
                mr.scalars.return_value.all.return_value = [profile]
            elif execute_count["n"] == 2:
                mr.scalars.return_value.all.return_value = [rule]
            else:
                mr.scalar.return_value = 0
            return mr

        mock_db.execute.side_effect = mock_execute

        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 1, 1)
        assert exc.value.status_code == 404
