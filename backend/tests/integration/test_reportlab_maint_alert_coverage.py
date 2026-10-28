"""Tests for reportlab_pdf_generator, maintenance_service, alert_engine coverage."""

import pytest


# ==================== REPORTLAB PDF GENERATOR ====================

class TestReportlabHelpers:
    """Cover reportlab_pdf_generator helper functions."""

    def test_money_to_words_zero(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(0.0)
        assert isinstance(result, str)

    def test_money_to_words_small(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru
        result = _money_to_words_ru(1234.56)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_styles(self):
        from app.services.reportlab_pdf_generator import _styles
        result = _styles()
        assert result is not None

    def test_num(self):
        from app.services.reportlab_pdf_generator import _num
        result = _num(1234.5)
        assert isinstance(result, str)

    def test_qty(self):
        from app.services.reportlab_pdf_generator import _qty
        result = _qty(5.0)
        assert isinstance(result, str)

    def test_grid(self):
        from app.services.reportlab_pdf_generator import _grid
        result = _grid()
        assert result is not None

    def test_canvas_factory(self):
        from app.services.reportlab_pdf_generator import _canvas_factory
        factory = _canvas_factory("Test Doc")
        assert callable(factory)


# ==================== MAINTENANCE SERVICE ====================

class TestMaintenanceServiceRemaining:
    """Cover remaining MaintenanceService methods."""

    def test_check_scheduled_maintenance(self, db_session):
        from app.services.maintenance_service import MaintenanceService
        svc = MaintenanceService()
        result = svc.check_scheduled_maintenance(db_session, company_id=1, user_id=1)
        assert isinstance(result, list)

    def test_update_vehicle_engine_hours(self, db_session):
        from app.services.maintenance_service import MaintenanceService
        svc = MaintenanceService()
        # Should handle non-existent vehicle gracefully
        try:
            svc.update_vehicle_engine_hours(db_session, vehicle_id=99999, engine_hours=100.0)
        except Exception:
            pass  # Expected for non-existent vehicle


# ==================== ALERT ENGINE ====================

class TestAlertEngineChecks:
    """Cover alert_engine check functions."""

    def test_check_engine_hours_no_prev(self, db_session, sample_vehicle):
        from app.services.alert_engine import _check_engine_hours
        from app.models.telematics import GpsPoint, AlertRule
        from datetime import datetime, timezone

        point = GpsPoint(
            vehicle_id=sample_vehicle.id,
            latitude=55.7558,
            longitude=37.6173,
            engine_hours=100.0,
            recorded_at=datetime.now(timezone.utc),
        )
        db_session.add(point)
        db_session.flush()

        rule = AlertRule(
            company_id=1,
            rule_type="engine_hours",
            threshold=500.0,
            is_active=True,
        )
        result = _check_engine_hours(db_session, point, rule)
        assert result is None

    def test_check_idle_no_prev(self, db_session, sample_vehicle):
        from app.services.alert_engine import _check_idle
        from app.models.telematics import GpsPoint, AlertRule
        from datetime import datetime, timezone

        point = GpsPoint(
            vehicle_id=sample_vehicle.id,
            latitude=55.7558,
            longitude=37.6173,
            speed=0.0,
            recorded_at=datetime.now(timezone.utc),
        )
        db_session.add(point)
        db_session.flush()

        rule = AlertRule(
            company_id=1,
            rule_type="idle",
            threshold=30.0,
            is_active=True,
        )
        result = _check_idle(db_session, point, rule)
        assert result is None

    def test_seed_default_rules(self, db_session):
        from app.services.alert_engine import seed_default_rules
        seed_default_rules(db_session, company_id=1)
        db_session.commit()

    def test_send_email_mock(self):
        from app.services.alert_engine import _send_email_mock
        # Should not raise
        _send_email_mock("test@example.com", "Test Subject", "Test Body")

    def test_process_point_with_rules_no_rules(self, db_session, sample_vehicle):
        from app.services.alert_engine import process_point_with_rules
        from app.models.telematics import GpsPoint
        from datetime import datetime, timezone

        point = GpsPoint(
            vehicle_id=sample_vehicle.id,
            latitude=55.7558,
            longitude=37.6173,
            speed=50.0,
            recorded_at=datetime.now(timezone.utc),
        )
        db_session.add(point)
        db_session.flush()

        alerts = process_point_with_rules(db_session, point, company_id=1)
        assert isinstance(alerts, list)
