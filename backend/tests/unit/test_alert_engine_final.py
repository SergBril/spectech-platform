"""Coverage push for alert_engine -> 95%+."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.alert_engine import (
    RULE_ENGINE,
    RULE_FUEL,
    RULE_IDLE,
    RULE_SPEED,
    _check_engine_hours,
    _check_fuel,
    _check_idle,
    _check_speed,
    _create_notifications,
    _get_or_create_alert,
    process_point_with_rules,
    seed_default_rules,
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    return db


def _point(**kw):
    d = dict(
        id=1, vehicle_id=10, speed=50.0, fuel_level=80.0,
        engine_hours=5.0, engine_on=True,
        recorded_at=datetime(2026, 11, 9, 12, 0, tzinfo=UTC),
    )
    d.update(kw)
    return SimpleNamespace(**d)


def _rule(rule_type, threshold=50.0, severity="warning",
          notify_in_app=False, notify_email=False):
    return SimpleNamespace(
        rule_type=rule_type, threshold=threshold,
        severity=severity, is_active=True, company_id=1,
        notify_in_app=notify_in_app, notify_email=notify_email,
    )


class TestProcessPointWithRules:
    """Cover lines 48-63, 72: main processing loop."""

    def test_speed_rule_triggers_alert_with_notifications(self, mock_db):
        point = _point(speed=120.0)
        rule = _rule(RULE_SPEED, threshold=90.0, notify_in_app=True, notify_email=True)
        mock_db.scalars.return_value.all.return_value = [rule]
        # _get_or_create_alert: no existing alert
        mock_db.scalar.return_value = None
        # _create_notifications: admins query
        admin = SimpleNamespace(id=1, email="admin@test.com")
        mock_db.scalars.return_value.all.side_effect = [[rule], [admin]]

        alerts = process_point_with_rules(mock_db, point, 1)
        assert len(alerts) == 1
        mock_db.commit.assert_called()

    def test_fuel_rule_triggers(self, mock_db):
        point = _point(fuel_level=60.0)
        prev_point = SimpleNamespace(fuel_level=80.0)
        rule = _rule(RULE_FUEL, threshold=10.0, notify_in_app=True)
        # First scalars: rules, second: admins
        mock_db.scalars.return_value.all.side_effect = [[rule], [SimpleNamespace(id=1, email="a@t.com")]]
        # scalar calls: prev point, existing alert
        mock_db.scalar.side_effect = [prev_point, None]

        alerts = process_point_with_rules(mock_db, point, 1)
        assert len(alerts) == 1

    def test_engine_hours_rule_triggers(self, mock_db):
        point = _point(engine_hours=15.0)
        first_today = SimpleNamespace(engine_hours=2.0)
        rule = _rule(RULE_ENGINE, threshold=10.0)
        mock_db.scalars.return_value.all.side_effect = [[rule], []]
        mock_db.scalar.side_effect = [first_today, None]

        alerts = process_point_with_rules(mock_db, point, 1)
        assert len(alerts) == 1

    def test_idle_rule_triggers(self, mock_db):
        point = _point(speed=0.0, engine_on=True,
            recorded_at=datetime(2026, 11, 9, 14, 0, tzinfo=UTC))
        idle_start = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
        rule = _rule(RULE_IDLE, threshold=60.0)
        mock_db.scalars.return_value.all.side_effect = [[rule], []]
        mock_db.scalar.side_effect = [idle_start, None]

        alerts = process_point_with_rules(mock_db, point, 1)
        assert len(alerts) == 1

    def test_no_rules(self, mock_db):
        point = _point()
        mock_db.scalars.return_value.all.return_value = []
        alerts = process_point_with_rules(mock_db, point, 1)
        assert alerts == []
        mock_db.commit.assert_not_called()

    def test_unknown_rule_type(self, mock_db):
        point = _point()
        rule = _rule("unknown_type")
        mock_db.scalars.return_value.all.return_value = [rule]
        alerts = process_point_with_rules(mock_db, point, 1)
        assert alerts == []


class TestCheckSpeed:
    """Cover lines 80, 83."""

    def test_speed_none(self, mock_db):
        point = _point(speed=None)
        rule = _rule(RULE_SPEED, threshold=90.0)
        assert _check_speed(mock_db, point, rule) is None

    def test_threshold_none(self, mock_db):
        point = _point(speed=100.0)
        rule = _rule(RULE_SPEED, threshold=None)
        assert _check_speed(mock_db, point, rule) is None

    def test_speed_below_threshold(self, mock_db):
        point = _point(speed=50.0)
        rule = _rule(RULE_SPEED, threshold=90.0)
        assert _check_speed(mock_db, point, rule) is None

    def test_speed_above_threshold(self, mock_db):
        point = _point(speed=120.0)
        rule = _rule(RULE_SPEED, threshold=90.0)
        mock_db.scalar.return_value = None  # no existing alert
        alert = _check_speed(mock_db, point, rule)
        assert alert is not None


class TestCheckFuel:
    """Cover lines 100, 116-118."""

    def test_fuel_none(self, mock_db):
        point = _point(fuel_level=None)
        rule = _rule(RULE_FUEL, threshold=10.0)
        assert _check_fuel(mock_db, point, rule) is None

    def test_no_prev_point(self, mock_db):
        point = _point(fuel_level=60.0)
        rule = _rule(RULE_FUEL, threshold=10.0)
        mock_db.scalar.return_value = None
        assert _check_fuel(mock_db, point, rule) is None

    def test_drop_below_threshold(self, mock_db):
        point = _point(fuel_level=75.0)
        prev = SimpleNamespace(fuel_level=80.0)
        rule = _rule(RULE_FUEL, threshold=10.0)
        mock_db.scalar.return_value = prev
        assert _check_fuel(mock_db, point, rule) is None

    def test_drop_above_threshold(self, mock_db):
        point = _point(fuel_level=60.0)
        prev = SimpleNamespace(fuel_level=80.0)
        rule = _rule(RULE_FUEL, threshold=10.0)
        mock_db.scalar.side_effect = [prev, None]  # prev, then no existing alert
        alert = _check_fuel(mock_db, point, rule)
        assert alert is not None


class TestCheckEngineHours:
    """Cover lines 139, 159."""

    def test_engine_hours_none(self, mock_db):
        point = _point(engine_hours=None)
        rule = _rule(RULE_ENGINE, threshold=10.0)
        assert _check_engine_hours(mock_db, point, rule) is None

    def test_no_first_point_today(self, mock_db):
        point = _point(engine_hours=15.0)
        rule = _rule(RULE_ENGINE, threshold=10.0)
        mock_db.scalar.return_value = None
        assert _check_engine_hours(mock_db, point, rule) is None

    def test_hours_below_threshold(self, mock_db):
        point = _point(engine_hours=10.0)
        first = SimpleNamespace(engine_hours=5.0)
        rule = _rule(RULE_ENGINE, threshold=10.0)
        mock_db.scalar.return_value = first
        assert _check_engine_hours(mock_db, point, rule) is None

    def test_hours_above_threshold(self, mock_db):
        point = _point(engine_hours=20.0)
        first = SimpleNamespace(engine_hours=5.0)
        rule = _rule(RULE_ENGINE, threshold=10.0)
        mock_db.scalar.side_effect = [first, None]
        alert = _check_engine_hours(mock_db, point, rule)
        assert alert is not None


class TestCheckIdle:
    """Cover lines 176, 180-196."""

    def test_threshold_none(self, mock_db):
        point = _point()
        rule = _rule(RULE_IDLE, threshold=None)
        assert _check_idle(mock_db, point, rule) is None

    def test_engine_off(self, mock_db):
        point = _point(engine_on=False)
        rule = _rule(RULE_IDLE, threshold=60.0)
        assert _check_idle(mock_db, point, rule) is None

    def test_speed_above_1(self, mock_db):
        point = _point(speed=5.0, engine_on=True)
        rule = _rule(RULE_IDLE, threshold=60.0)
        assert _check_idle(mock_db, point, rule) is None

    def test_no_idle_start(self, mock_db):
        point = _point(speed=0.0, engine_on=True)
        rule = _rule(RULE_IDLE, threshold=60.0)
        mock_db.scalar.return_value = None
        assert _check_idle(mock_db, point, rule) is None

    def test_idle_below_threshold(self, mock_db):
        point = _point(speed=0.0, engine_on=True,
            recorded_at=datetime(2026, 11, 9, 12, 30, tzinfo=UTC))
        idle_start = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)  # 30 min
        rule = _rule(RULE_IDLE, threshold=60.0)
        mock_db.scalar.return_value = idle_start
        assert _check_idle(mock_db, point, rule) is None

    def test_idle_above_threshold(self, mock_db):
        point = _point(speed=0.0, engine_on=True,
            recorded_at=datetime(2026, 11, 9, 14, 0, tzinfo=UTC))
        idle_start = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)  # 120 min
        rule = _rule(RULE_IDLE, threshold=60.0)
        mock_db.scalar.side_effect = [idle_start, None]
        alert = _check_idle(mock_db, point, rule)
        assert alert is not None


class TestCreateNotifications:
    """Cover lines 261-285."""

    def test_in_app_and_email(self, mock_db):
        alert = SimpleNamespace(id=1, title="Test", description="Desc")
        admin = SimpleNamespace(id=1, email="admin@test.com")
        mock_db.scalars.return_value.all.return_value = [admin]

        _create_notifications(mock_db, alert, 1, in_app=True, email=True)
        # Should add 2 notifications (in_app + email)
        assert mock_db.add.call_count == 2

    def test_in_app_only(self, mock_db):
        alert = SimpleNamespace(id=1, title="Test", description="Desc")
        admin = SimpleNamespace(id=1, email="admin@test.com")
        mock_db.scalars.return_value.all.return_value = [admin]

        _create_notifications(mock_db, alert, 1, in_app=True, email=False)
        assert mock_db.add.call_count == 1

    def test_no_admins(self, mock_db):
        alert = SimpleNamespace(id=1, title="Test", description="Desc")
        mock_db.scalars.return_value.all.return_value = []
        _create_notifications(mock_db, alert, 1, in_app=True, email=True)
        mock_db.add.assert_not_called()


class TestSeedDefaultRules:
    """Cover seed_default_rules."""

    def test_seeds_new_rules(self, mock_db):
        mock_db.scalar.return_value = None  # no existing rules
        seed_default_rules(mock_db, 1)
        assert mock_db.add.call_count == 4
        mock_db.commit.assert_called()

    def test_skips_existing_rules(self, mock_db):
        existing = SimpleNamespace(id=1)
        mock_db.scalar.return_value = existing
        seed_default_rules(mock_db, 1)
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called()
