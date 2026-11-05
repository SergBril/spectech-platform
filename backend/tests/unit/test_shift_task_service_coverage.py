"""Coverage tests for shift_task_service."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


class TestShiftTaskServiceError:
    """Cover ShiftTaskServiceError (lines 14-21)."""

    def test_init_str(self):
        from app.services.shift_task_service import ShiftTaskServiceError

        err = ShiftTaskServiceError(404, "Not found")
        assert err.status_code == 404
        assert str(err) == "Not found"

    def test_init_dict(self):
        from app.services.shift_task_service import ShiftTaskServiceError

        err = ShiftTaskServiceError(409, {"conflicts": ["busy"]})
        assert err.status_code == 409


class TestUpdateShiftTask:
    """Cover update_shift_task (lines 23-148)."""

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
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
            vehicle_id=1,
            shift_date=date(2026, 11, 5),
            operator_id=None,
            status="planned",
        )
        vehicle = SimpleNamespace(company_id=1, name="KAMAZ")
        conflict = SimpleNamespace(id=2)

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return task if call_count["n"] == 1 else vehicle
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
            vehicle_id=1,
            shift_date=date(2026, 11, 5),
            operator_id=None,
            status="planned",
            planned_start=None,
            planned_end=None,
        )
        vehicle = SimpleNamespace(company_id=1, name="KAMAZ")

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return task if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with (
            patch(
                "app.services.notification_service.create_notification",
                new_callable=AsyncMock,
            ),
            patch("app.services.websocket_manager.manager") as mock_mgr,
        ):
            mock_mgr.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                mock_db,
                1,
                1,
                1,
                shift_date="2026-11-06",
                status="in_progress",
                driver_id=10,
            )

        assert result["message"] == "Смена обновлена"
        assert len(result["changes"]) > 0
        mock_db.commit.assert_called()


class TestAutoAssignDriver:
    """Cover auto_assign_driver (lines 150-end)."""

    def test_not_found(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            auto_assign_driver,
        )

        mock_db.get.return_value = None
        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 999, 1)
        assert exc.value.status_code == 404

    def test_access_denied(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            auto_assign_driver,
        )

        task = SimpleNamespace(vehicle_id=1)
        vehicle = SimpleNamespace(company_id=2)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return task if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get

        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 1, 1)
        assert exc.value.status_code == 403

    def test_already_assigned(self, mock_db):
        from app.services.shift_task_service import (
            ShiftTaskServiceError,
            auto_assign_driver,
        )

        task = SimpleNamespace(vehicle_id=1, operator_id=5)
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
        vehicle = SimpleNamespace(company_id=1)
        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return task if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get
        # No drivers found
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 1, 1)
        assert exc.value.status_code == 404

    def test_success_with_scoring(self, mock_db):
        from app.services.shift_task_service import auto_assign_driver

        task = SimpleNamespace(
            vehicle_id=1, operator_id=None, shift_date=date(2026, 11, 5)
        )
        vehicle = SimpleNamespace(company_id=1, category="B")
        profile = SimpleNamespace(employee_contractor_id=10, license_category="B")
        emp = SimpleNamespace(first_name="Ivan", last_name="Petrov")
        rule = SimpleNamespace(
            rule_type="priority_driver", priority=5, config_json='{"driver_ids": [10]}'
        )

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return task
            if call_count["n"] == 2:
                return vehicle
            return emp

        mock_db.get.side_effect = mock_get

        exec_count = {"n": 0}

        def mock_execute(stmt):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] == 1:
                mr.scalars.return_value.all.return_value = [profile]
            elif exec_count["n"] == 2:
                mr.scalars.return_value.all.return_value = [rule]
            elif exec_count["n"] == 3:
                mr.scalar_one_or_none.return_value = None  # not busy
            else:
                mr.scalar.return_value = 2  # week shifts
            return mr

        mock_db.execute.side_effect = mock_execute

        result = auto_assign_driver(mock_db, 1, 1)
        assert result["driver_id"] == 10
        assert "Ivan" in result["driver_name"]
        assert result["score"] > 0
        mock_db.commit.assert_called()

    def test_blacklist_excluded(self, mock_db):
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
            rule_type="blacklist", priority=1, config_json='{"driver_ids": [10]}'
        )

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            return task if call_count["n"] == 1 else vehicle

        mock_db.get.side_effect = mock_get

        exec_count = {"n": 0}

        def mock_execute(stmt):
            exec_count["n"] += 1
            mr = MagicMock()
            if exec_count["n"] == 1:
                mr.scalars.return_value.all.return_value = [profile]
            else:
                mr.scalars.return_value.all.return_value = [rule]
            return mr

        mock_db.execute.side_effect = mock_execute

        with pytest.raises(ShiftTaskServiceError) as exc:
            auto_assign_driver(mock_db, 1, 1)
        assert exc.value.status_code == 404
