"""Tests for PayoutService."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service():
    from app.services.finance.payout_service import PayoutService

    return PayoutService()


class TestCalculatePayoutsForPeriod:
    """Cover calculate_payouts_for_period (lines 29-258)."""

    def test_no_reconciliations(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.join.return_value.join.return_value.filter.return_value.all.return_value = (
            []
        )
        mock_db.query.return_value = mock_query

        result = service.calculate_payouts_for_period(
            mock_db, 1, date(2026, 11, 1), date(2026, 11, 30)
        )
        assert result["total_payouts"] == 0
        assert result["payouts"] == []
        assert "message" in result

    def test_with_reconciliations(self, service, mock_db):
        rec = SimpleNamespace(
            shift_task_id=10,
            company_id=1,
            reconciliation_status="auto_approved",
            final_moto_hours=8.5,
        )
        shift_task = SimpleNamespace(
            vehicle_id=1, shift_date=date(2026, 11, 5), request_id=None
        )
        vehicle = SimpleNamespace(
            id=1, name="KAMAZ", owner_id=2, owner_rate=3000, company_id=1
        )

        mock_query = MagicMock()
        mock_query.join.return_value.join.return_value.filter.return_value.all.return_value = [
            rec
        ]
        mock_db.query.return_value = mock_query

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return shift_task
            return vehicle

        mock_db.get.side_effect = mock_get

        # Mock _generate_payout_number
        with patch.object(
            service, "_generate_payout_number", return_value="ВЫП-2026-0001"
        ):
            result = service.calculate_payouts_for_period(
                mock_db, 1, date(2026, 11, 1), date(2026, 11, 30)
            )

        assert result["total_payouts"] >= 1
        assert result["total_gross"] > 0
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_custom_commission_rate(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.join.return_value.join.return_value.filter.return_value.all.return_value = (
            []
        )
        mock_db.query.return_value = mock_query

        result = service.calculate_payouts_for_period(
            mock_db,
            1,
            date(2026, 11, 1),
            date(2026, 11, 30),
            commission_rate=Decimal("10.00"),
        )
        assert result["total_payouts"] == 0


class TestGetPayoutsSummary:
    """Cover get_payouts_summary (lines 281-320)."""

    def test_summary_returns_structure(self, service, mock_db):
        totals = SimpleNamespace(total=5, gross=250000, commission=37500, net=212500)

        call_count = {"n": 0}

        def mock_query(*args, **kwargs):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                mq.filter.return_value.first.return_value = totals
            else:
                mq.filter.return_value.scalar.return_value = 2
            return mq

        mock_db.query.side_effect = mock_query

        result = service.get_payouts_summary(
            mock_db, 1, date(2026, 11, 1), date(2026, 11, 30)
        )
        assert result["total_payouts"] == 5
        assert result["total_gross"] == 250000.0
        assert result["pending_payouts"] == 2

    def test_summary_empty(self, service, mock_db):
        totals = SimpleNamespace(total=0, gross=0, commission=0, net=0)

        call_count = {"n": 0}

        def mock_query(*args, **kwargs):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                mq.filter.return_value.first.return_value = totals
            else:
                mq.filter.return_value.scalar.return_value = 0
            return mq

        mock_db.query.side_effect = mock_query

        result = service.get_payouts_summary(
            mock_db, 1, date(2026, 11, 1), date(2026, 11, 30)
        )
        assert result["total_payouts"] == 0
        assert result["total_net"] == 0.0


class TestApprovePayout:
    """Cover approve_payout (lines 383-end)."""

    def test_payout_not_found(self, service, mock_db):
        mock_db.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.approve_payout(mock_db, 999, 1)

    def test_wrong_company(self, service, mock_db):
        payout = SimpleNamespace(company_id=2, status=None)
        mock_db.get.return_value = payout
        with pytest.raises(ValueError, match="not found"):
            service.approve_payout(mock_db, 1, 1)

    def test_not_draft_status(self, service, mock_db):
        from app.models.finance import DocumentStatus

        payout = SimpleNamespace(company_id=1, status=DocumentStatus.sent)
        mock_db.get.return_value = payout
        with pytest.raises(ValueError, match="Only draft"):
            service.approve_payout(mock_db, 1, 1)

    def test_approve_success(self, service, mock_db):
        from app.models.finance import DocumentStatus

        payout = SimpleNamespace(
            id=1, company_id=1, status=DocumentStatus.draft, owner_id=10
        )
        mock_db.get.return_value = payout

        with patch("app.services.email_service.email_service"):
            result = service.approve_payout(mock_db, 1, 1)

        assert result["status"] == "success"
        assert result["new_status"] == DocumentStatus.sent.value
        assert payout.status == DocumentStatus.sent
        mock_db.commit.assert_called_once()

    def test_approve_without_owner_email(self, service, mock_db):
        from app.models.finance import DocumentStatus

        payout = SimpleNamespace(
            id=1, company_id=1, status=DocumentStatus.draft, owner_id=10
        )
        owner = SimpleNamespace(contact_email=None, name="Test")

        call_count = {"n": 0}

        def mock_get(model, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return payout
            return owner

        mock_db.get.side_effect = mock_get

        result = service.approve_payout(mock_db, 1, 1)
        assert result["status"] == "success"


class TestGeneratePayoutNumber:
    """Cover _generate_payout_number (lines 259-280)."""

    def test_generates_unique_number(self, service, mock_db):
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = service._generate_payout_number(mock_db, date(2026, 11, 5))
        assert "ВЫП-2026-" in result
        # Number should be zero-padded
        parts = result.split("-")
        assert len(parts[-1]) >= 4
