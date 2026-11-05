"""Tests for WeeklyDigestService."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGetDashboardMetrics:
    """Cover _get_dashboard_metrics (lines 25-95)."""

    def test_success(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        call_count = {"n": 0}

        def mock_query(*args, **kwargs):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                # revenue query .one()
                mq.filter.return_value.one.return_value = (100000, 80000)
            elif call_count["n"] == 2:
                # commission .scalar()
                mq.filter.return_value.scalar.return_value = 15000
            elif call_count["n"] == 3:
                # active_rentals .scalar()
                mq.filter.return_value.scalar.return_value = 5
            else:
                # overdue query .one()
                mq.filter.return_value.one.return_value = (2, 5000)
            return mq

        mock_db.query.side_effect = mock_query

        result = WeeklyDigestService._get_dashboard_metrics(
            mock_db, 1, date(2026, 10, 28), date(2026, 11, 4)
        )
        assert result["total_revenue"] == 100000.0
        assert result["total_paid"] == 80000.0
        assert result["active_rentals"] == 5

    def test_exception_returns_zeros(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.query.side_effect = Exception("DB error")

        result = WeeklyDigestService._get_dashboard_metrics(
            mock_db, 1, date(2026, 10, 28), date(2026, 11, 4)
        )
        assert result["total_revenue"] == 0
        assert result["active_rentals"] == 0


class TestGetTopClients:
    """Cover _get_top_clients (lines 96-131)."""

    def test_success(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        row1 = SimpleNamespace(
            client_id=1, client_name="ООО Клиент", total_revenue=50000, invoices_count=3
        )
        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            row1
        ]
        mock_db.query.return_value = mock_query

        result = WeeklyDigestService._get_top_clients(
            mock_db, 1, date(2026, 10, 28), date(2026, 11, 4)
        )
        assert len(result) == 1
        assert result[0]["client_name"] == "ООО Клиент"

    def test_exception_returns_empty(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.query.side_effect = Exception("DB error")

        result = WeeklyDigestService._get_top_clients(
            mock_db, 1, date(2026, 10, 28), date(2026, 11, 4)
        )
        assert result == []


class TestSendWeeklyDigest:
    """Cover send_weekly_digest (lines 220-309)."""

    def test_company_not_found(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.get.return_value = None

        result = WeeklyDigestService.send_weekly_digest(mock_db, 999)
        assert result["success"] is False
        assert result["recipients_count"] == 0

    def test_no_accountants(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        company = SimpleNamespace(id=1, name="TestCo")
        mock_db.get.return_value = company

        with (
            patch.object(
                WeeklyDigestService,
                "_get_dashboard_metrics",
                return_value={"total_revenue": 0},
            ),
            patch.object(WeeklyDigestService, "_get_top_clients", return_value=[]),
            patch.object(WeeklyDigestService, "_get_top_vehicles", return_value=[]),
            patch.object(WeeklyDigestService, "_get_overdue_invoices", return_value=[]),
            patch.object(WeeklyDigestService, "_find_accountants", return_value=[]),
        ):

            result = WeeklyDigestService.send_weekly_digest(mock_db, 1)

        assert result["success"] is True
        assert result["recipients_count"] == 0

    def test_sends_to_accountants(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        company = SimpleNamespace(id=1, name="TestCo")
        accountant = SimpleNamespace(email="acc@test.com")
        mock_db.get.return_value = company

        with (
            patch.object(
                WeeklyDigestService,
                "_get_dashboard_metrics",
                return_value={"total_revenue": 100},
            ),
            patch.object(WeeklyDigestService, "_get_top_clients", return_value=[]),
            patch.object(WeeklyDigestService, "_get_top_vehicles", return_value=[]),
            patch.object(WeeklyDigestService, "_get_overdue_invoices", return_value=[]),
            patch.object(
                WeeklyDigestService, "_find_accountants", return_value=[accountant]
            ),
            patch("app.services.weekly_digest_service.email_service") as mock_email,
        ):

            mock_email.send_email.return_value = True
            result = WeeklyDigestService.send_weekly_digest(mock_db, 1)

        assert result["success"] is True
        assert result["recipients_count"] == 1

    def test_data_gathering_exception(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        company = SimpleNamespace(id=1, name="TestCo")
        mock_db.get.return_value = company

        with patch.object(
            WeeklyDigestService, "_get_dashboard_metrics", side_effect=Exception("Fail")
        ):
            result = WeeklyDigestService.send_weekly_digest(mock_db, 1)

        assert result["success"] is False


class TestSendDigestsForAllCompanies:
    """Cover send_digests_for_all_companies (lines 310-356)."""

    def test_multiple_companies(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        companies = [
            SimpleNamespace(id=1, name="Co1"),
            SimpleNamespace(id=2, name="Co2"),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = companies

        with patch.object(WeeklyDigestService, "send_weekly_digest") as mock_send:
            mock_send.side_effect = [
                {"success": True, "recipients_count": 2},
                {"success": True, "recipients_count": 1},
            ]
            result = WeeklyDigestService.send_digests_for_all_companies(mock_db)

        assert result["total_companies"] == 2
        assert result["successful"] == 2
        assert result["total_recipients"] == 3

    def test_with_errors(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        companies = [SimpleNamespace(id=1, name="Co1")]
        mock_db.query.return_value.filter.return_value.all.return_value = companies

        with patch.object(WeeklyDigestService, "send_weekly_digest") as mock_send:
            mock_send.return_value = {
                "success": False,
                "recipients_count": 0,
                "error": "Fail",
            }
            result = WeeklyDigestService.send_digests_for_all_companies(mock_db)

        assert result["successful"] == 0
        assert len(result["errors"]) == 1


class TestFindAccountants:
    """Cover _find_accountants (lines 357-end)."""

    def test_no_employees(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = WeeklyDigestService._find_accountants(mock_db, 1)
        assert result == []

    def test_finds_users(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        employee = SimpleNamespace(user_id=5, role_in_system="accountant")
        user = SimpleNamespace(
            id=5, email="acc@test.com", company_id=1, is_superuser=False
        )

        call_count = {"n": 0}

        def mock_query(model):
            call_count["n"] += 1
            mq = MagicMock()
            if call_count["n"] == 1:
                mq.filter.return_value.all.return_value = [employee]
            else:
                mq.filter.return_value.all.return_value = [user]
            return mq

        mock_db.query.side_effect = mock_query

        result = WeeklyDigestService._find_accountants(mock_db, 1)
        assert len(result) == 1
        assert result[0].email == "acc@test.com"
