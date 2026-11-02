import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import date, datetime, UTC

from app.services.shift_task_service import (
    update_shift_task,
    auto_assign_driver,
    ShiftTaskServiceError,
)


@pytest.fixture
def mock_db():
    return MagicMock()


class TestUpdateShiftTask:
    """Tests for update_shift_task"""

    @pytest.mark.asyncio
    async def test_update_success(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.shift_date = date(2026, 11, 1)
        mock_task.operator_id = None
        mock_task.status = "planned"

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7
        mock_vehicle.name = "CAT 320"

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('app.services.websocket_manager.manager') as mock_manager:
            mock_manager.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                db=mock_db, task_id=1, company_id=7, user_id=1,
                status="completed",
            )

        assert result["message"] == "Смена обновлена"
        assert result["id"] == 1
        assert len(result["changes"]) > 0
        assert mock_task.status == "completed"

    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_db):
        mock_db.get = MagicMock(return_value=None)

        with pytest.raises(ShiftTaskServiceError) as exc_info:
            await update_shift_task(db=mock_db, task_id=999, company_id=7, user_id=1)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_access_denied(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 99  # Different company

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)

        with pytest.raises(ShiftTaskServiceError) as exc_info:
            await update_shift_task(db=mock_db, task_id=1, company_id=7, user_id=1)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_vehicle_conflict(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.shift_date = date(2026, 11, 1)
        mock_task.id = 1

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7
        mock_vehicle.name = "CAT 320"

        mock_conflict = MagicMock()

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_conflict

        with pytest.raises(ShiftTaskServiceError) as exc_info:
            await update_shift_task(
                db=mock_db, task_id=1, company_id=7, user_id=1,
                shift_date="2026-11-01",
            )
        assert exc_info.value.status_code == 409
        assert "conflicts" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_date_change(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.shift_date = date(2026, 11, 1)
        mock_task.operator_id = None
        mock_task.status = "planned"

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch('app.services.websocket_manager.manager') as mock_manager:
            mock_manager.broadcast_to_company = AsyncMock()
            result = await update_shift_task(
                db=mock_db, task_id=1, company_id=7, user_id=1,
                shift_date="2026-11-05",
            )

        assert any("date" in c for c in result["changes"])


class TestAutoAssignDriver:
    """Tests for auto_assign_driver"""

    def test_not_found(self, mock_db):
        mock_db.get = MagicMock(return_value=None)

        with pytest.raises(ShiftTaskServiceError) as exc_info:
            auto_assign_driver(mock_db, task_id=999, company_id=7)
        assert exc_info.value.status_code == 404

    def test_access_denied(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 99

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)

        with pytest.raises(ShiftTaskServiceError) as exc_info:
            auto_assign_driver(mock_db, task_id=1, company_id=7)
        assert exc_info.value.status_code == 403

    def test_already_assigned(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.operator_id = 5  # Already assigned

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)

        with pytest.raises(ShiftTaskServiceError) as exc_info:
            auto_assign_driver(mock_db, task_id=1, company_id=7)
        assert exc_info.value.status_code == 409

    def test_no_available_drivers(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.operator_id = None
        mock_task.shift_date = date(2026, 11, 1)

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)
        # No drivers found
        mock_db.execute = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        with pytest.raises(ShiftTaskServiceError) as exc_info:
            auto_assign_driver(mock_db, task_id=1, company_id=7)
        assert exc_info.value.status_code == 404
        assert "No available" in str(exc_info.value.detail)

    def test_successful_assignment(self, mock_db):
        mock_task = MagicMock()
        mock_task.vehicle_id = 10
        mock_task.operator_id = None
        mock_task.shift_date = date(2026, 11, 1)

        mock_vehicle = MagicMock()
        mock_vehicle.company_id = 7
        mock_vehicle.category = "EXCAVATOR"

        mock_driver = MagicMock()
        mock_driver.employee_contractor_id = 42
        mock_driver.license_category = "EXCAVATOR"

        mock_emp = MagicMock()
        mock_emp.first_name = "Ivan"
        mock_emp.last_name = "Petrov"

        def get_side_effect(model, id):
            name = getattr(model, '__name__', str(model))
            if name == 'ShiftTask':
                return mock_task
            if name == 'Vehicle':
                return mock_vehicle
            if name == 'Employee':
                return mock_emp
            return None

        mock_db.get = MagicMock(side_effect=get_side_effect)

        # First execute: drivers list, Second: rules, Third: busy check, Fourth: week shifts
        drivers_result = MagicMock()
        drivers_result.scalars.return_value.all.return_value = [mock_driver]

        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = []

        busy_result = MagicMock()
        busy_result.scalar_one_or_none.return_value = None

        week_result = MagicMock()
        week_result.scalar.return_value = 2

        mock_db.execute = MagicMock(side_effect=[drivers_result, rules_result, busy_result, week_result])
        mock_db.commit = MagicMock()

        result = auto_assign_driver(mock_db, task_id=1, company_id=7)

        assert result["driver_id"] == 42
        assert "Ivan" in result["driver_name"]
        assert result["score"] > 0
        assert mock_task.operator_id == 42
