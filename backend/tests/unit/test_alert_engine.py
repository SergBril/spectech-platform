"""Unit tests for alert_engine."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.services.alert_engine import (
    RULE_ENGINE,
    RULE_FUEL,
    RULE_IDLE,
    RULE_OFFLINE,
    RULE_SPEED,
    _get_or_create_alert,
    seed_default_rules,
)


class TestRuleConstants:
    """Tests for rule type constants."""

    def test_rule_constants_are_unique(self):
        rules = [RULE_SPEED, RULE_FUEL, RULE_ENGINE, RULE_IDLE, RULE_OFFLINE]
        assert len(rules) == len(set(rules))

    def test_rule_constants_are_strings(self):
        for rule in [RULE_SPEED, RULE_FUEL, RULE_ENGINE, RULE_IDLE, RULE_OFFLINE]:
            assert isinstance(rule, str)
            assert len(rule) > 0


class TestGetOrCreateAlert:
    """Tests for _get_or_create_alert deduplication logic."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.scalar.return_value = None
        return db

    def test_creates_new_alert(self, mock_db):
        from app.models.telematics import AlertSeverity

        alert = _get_or_create_alert(
            mock_db,
            alert_type=RULE_SPEED,
            severity=AlertSeverity.warning,
            vehicle_id=1,
            title="Speed alert",
            description="Overspeed",
            details={"speed": 100},
            occurred_at=datetime.now(UTC),
            company_id=1,
        )
        assert alert is not None
        mock_db.add.assert_called()
        mock_db.flush.assert_called()

    def test_skips_duplicate_within_10_min(self, mock_db):
        from app.models.telematics import AlertSeverity

        existing = MagicMock()
        mock_db.scalar.return_value = existing
        alert = _get_or_create_alert(
            mock_db,
            alert_type=RULE_SPEED,
            severity=AlertSeverity.warning,
            vehicle_id=1,
            title="Speed alert",
            description="Overspeed",
            details={"speed": 100},
            occurred_at=datetime.now(UTC),
            company_id=1,
        )
        assert alert is None
        mock_db.add.assert_not_called()


class TestSeedDefaultRules:
    """Tests for seed_default_rules idempotency."""

    def test_skips_existing_rules(self):
        """Existing rules should not be duplicated."""
        db = MagicMock()
        db.scalar.return_value = MagicMock()
        seed_default_rules(db, 1)
        db.add.assert_not_called()
        db.commit.assert_called()

    def test_creates_missing_rules(self):
        """Missing rules should be created."""
        db = MagicMock()
        db.scalar.return_value = None
        seed_default_rules(db, 1)
        assert db.add.call_count == 4
        db.commit.assert_called()
