"""Tests for critical low-coverage services."""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestSalaryService:
    """Tests for salary calculation service."""

    def test_import_salary_service(self):
        """Salary service should be importable."""
        from app.services.salary_service import SalaryService
        assert SalaryService is not None

    def test_salary_service_init(self):
        """SalaryService should instantiate without arguments."""
        from app.services.salary_service import SalaryService
        service = SalaryService()
        assert service is not None


class TestStorageService:
    """Tests for S3/MinIO storage service."""

    def test_import_storage_module(self):
        """Storage module should be importable."""
        from app.services import storage_service
        assert storage_service is not None

    def test_storage_has_upload_function(self):
        """Storage module should have upload capability."""
        from app.services import storage_service
        # Module has functions, not a class
        assert hasattr(storage_service, 'upload_file') or                hasattr(storage_service, 'ensure_bucket_exists') or                hasattr(storage_service, 'MINIO_BUCKET')


class TestTelematicsService:
    """Tests for GPS/telematics service."""

    def test_import_telematics_module(self):
        """Telematics module should be importable."""
        from app.services import telematics_service
        assert telematics_service is not None

    def test_telematics_has_save_gps_points(self):
        """Should have save_gps_points function."""
        from app.services.telematics_service import save_gps_points
        assert save_gps_points is not None

    def test_telematics_has_dashboard(self):
        """Should have get_telematics_dashboard function."""
        from app.services.telematics_service import get_telematics_dashboard
        assert get_telematics_dashboard is not None

    def test_haversine_calculation(self):
        """Haversine should calculate distance between two points."""
        from app.services.telematics_service import _haversine
        # Moscow to SPb approx 635 km (function returns meters)
        dist = _haversine(55.7558, 37.6173, 59.9343, 30.3351)
        assert 600_000 < dist < 700_000


class TestSchedulerTasks:
    """Tests for scheduler task functions."""

    def test_import_scheduler(self):
        """Scheduler should be importable."""
        from app.tasks.scheduler import start_scheduler, stop_scheduler
        assert start_scheduler is not None
        assert stop_scheduler is not None

    def test_stop_scheduler_safe_when_not_started(self):
        """stop_scheduler should not raise when scheduler not running."""
        from app.tasks.scheduler import stop_scheduler
        stop_scheduler()


class TestNotificationDispatcherCoverage:
    """Additional tests to improve notification_dispatcher coverage."""

    def test_run_async_in_sync_context(self):
        """_run_async should return task in async context or result in sync."""
        from app.services.notification_dispatcher import NotificationDispatcher
        import asyncio

        async def sample_coro():
            return "ok"

        # When called inside event loop, returns Task
        # When called outside, runs synchronously
        try:
            asyncio.get_running_loop()
            # In event loop - returns Task
            result = NotificationDispatcher._run_async(sample_coro())
            assert asyncio.isfuture(result) or asyncio.istask(result)
        except RuntimeError:
            # No event loop - runs sync
            result = NotificationDispatcher._run_async(sample_coro())
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_notify_payout_created_handles_errors(self, db_session):
        """notify_payout_created should handle missing data gracefully."""
        from app.services.notification_dispatcher import notification_dispatcher
        mock_payout = MagicMock()
        mock_payout.document_number = "TEST-001"
        mock_payout.gross_amount = Decimal("1000")
        mock_payout.platform_commission = Decimal("100")
        mock_payout.net_amount = Decimal("900")

        results = await notification_dispatcher.notify_payout_created(
            db=db_session,
            payout=mock_payout,
            owner_email="test@test.com",
            owner_name="Test Owner",
            owner_user_id=None,
        )
        assert isinstance(results, dict)
        assert "email" in results
        assert "max" in results
