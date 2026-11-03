"""Unit tests for GPS Sync Error Tracking."""

from sqlalchemy.orm import Session

from app.models.company import Company


class TestGpsSyncLog:
    """Tests for GpsSyncLog model and log_gps_sync helper."""

    def test_log_success(self, db_session: Session):
        """Успешная синхронизация записывается в лог."""
        from app.services.gps_providers.base import log_gps_sync

        company = Company(
            name="GPS Co",
            legal_name="GPS",
            inn="7700000010",
            timezone="Europe/Moscow",
            currency="RUB",
            is_active=True,
        )
        db_session.add(company)
        db_session.commit()

        log_gps_sync(
            db=db_session,
            provider_name="wialon",
            sync_type="last_position",
            status="success",
            company_id=company.id,
            points_received=1,
            duration_ms=150,
        )

        from app.models.telematics import GpsSyncLog

        log = (
            db_session.query(GpsSyncLog)
            .filter(GpsSyncLog.provider_name == "wialon")
            .first()
        )

        assert log is not None
        assert log.status == "success"
        assert log.points_received == 1
        assert log.duration_ms == 150
        assert log.error_message is None

    def test_log_error(self, db_session: Session):
        """Ошибка синхронизации записывается с сообщением."""
        from app.services.gps_providers.base import log_gps_sync

        log_gps_sync(
            db=db_session,
            provider_name="mapix",
            sync_type="track",
            status="error",
            error_message="Connection timeout after 30s",
            duration_ms=30000,
        )

        from app.models.telematics import GpsSyncLog

        log = (
            db_session.query(GpsSyncLog)
            .filter(GpsSyncLog.provider_name == "mapix")
            .first()
        )

        assert log is not None
        assert log.status == "error"
        assert "timeout" in log.error_message.lower()

    def test_log_truncates_long_error(self, db_session: Session):
        """Длинные сообщения об ошибках обрезаются до 2000 символов."""
        from app.services.gps_providers.base import log_gps_sync

        long_error = "x" * 5000
        log_gps_sync(
            db=db_session,
            provider_name="gdemoi",
            sync_type="test_connection",
            status="error",
            error_message=long_error,
        )

        from app.models.telematics import GpsSyncLog

        log = (
            db_session.query(GpsSyncLog)
            .filter(GpsSyncLog.provider_name == "gdemoi")
            .first()
        )

        assert log is not None
        assert len(log.error_message) <= 2000

    def test_multiple_logs_same_provider(self, db_session: Session):
        """Можно записать несколько логов для одного провайдера."""
        from app.services.gps_providers.base import log_gps_sync

        for i in range(3):
            log_gps_sync(
                db=db_session,
                provider_name="wialon",
                sync_type="last_position",
                status="success" if i < 2 else "timeout",
                points_received=1,
                duration_ms=100 + i * 50,
            )

        from app.models.telematics import GpsSyncLog

        logs = (
            db_session.query(GpsSyncLog)
            .filter(GpsSyncLog.provider_name == "wialon")
            .all()
        )

        assert len(logs) >= 3
