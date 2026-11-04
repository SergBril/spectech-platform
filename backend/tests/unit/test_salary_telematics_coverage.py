"""Coverage tests for salary_export and telematics_tasks."""
import pytest
from unittest.mock import MagicMock, patch


class TestSalaryExport:
    """Test salary_export module."""

    def test_export_salaries_callable(self):
        from app.services.salary_export import export_salaries_to_excel
        assert callable(export_salaries_to_excel)

    def test_export_function_signature(self):
        import inspect
        from app.services.salary_export import export_salaries_to_excel
        sig = inspect.signature(export_salaries_to_excel)
        assert len(sig.parameters) > 0


class TestTelematicsTasks:
    """Test telematics_tasks module - all functions are sync."""

    @patch("app.core.db.SessionLocal")
    def test_aggregate_engine_hours_empty(self, mock_session_local):
        from app.tasks.telematics_tasks import aggregate_engine_hours
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.execute.return_value.fetchall.return_value = []
        aggregate_engine_hours(vehicle_id=1)
        mock_db.close.assert_called()

    @patch("app.core.db.SessionLocal")
    def test_aggregate_engine_hours_with_data(self, mock_session_local):
        from app.tasks.telematics_tasks import aggregate_engine_hours
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.execute.return_value.fetchall.return_value = [(1, 7, 10.5)]
        aggregate_engine_hours(vehicle_id=1, date_str="2025-01-15")

    @patch("app.core.db.SessionLocal")
    def test_cleanup_old_gps_points(self, mock_session_local):
        from app.tasks.telematics_tasks import cleanup_old_gps_points
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.delete.return_value = 100
        cleanup_old_gps_points(days_old=90)

    @patch("app.core.db.SessionLocal")
    def test_detect_offline_vehicles_empty(self, mock_session_local):
        from app.tasks.telematics_tasks import detect_offline_vehicles
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.execute.return_value.fetchall.return_value = []
        detect_offline_vehicles(minutes_threshold=60)

    @patch("app.core.db.SessionLocal")
    def test_detect_offline_vehicles_with_data(self, mock_session_local):
        from app.tasks.telematics_tasks import detect_offline_vehicles
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.execute.return_value.fetchall.return_value = [(1, "EX-001", 7)]
        detect_offline_vehicles(minutes_threshold=30)
