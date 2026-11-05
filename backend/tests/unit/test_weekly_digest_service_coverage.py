"""Coverage tests for weekly_digest_service."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get = MagicMock()
    return db


class TestGetDashboardMetrics:
    """Cover _get_dashboard_metrics (lines 25-94)."""

    def test_success(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        # Mock revenue query
        revenue_result = (10000.0, 7000.0)
        commission_result = 500.0
        active_rentals_result = 3
        overdue_result = (2, 1500.0)

        call_count = {"n": 0}

        def mock_query_side_effect(*args):
            call_count["n"] += 1
            q = MagicMock()
            if call_count["n"] == 1:
                q.filter.return_value.one.return_value = revenue_result
                return q
            elif call_count["n"] == 2:
                q.filter.return_value.scalar.return_value = commission_result
                return q
            elif call_count["n"] == 3:
                q.filter.return_value.scalar.return_value = active_rentals_result
                return q
            else:
                q.filter.return_value.one.return_value = overdue_result
                return q

        mock_db.query.side_effect = mock_query_side_effect

        result = WeeklyDigestService._get_dashboard_metrics(
            mock_db,
            1,
            date(2026, 10, 29),
            date(2026, 11, 5),
        )
        assert result["total_revenue"] == 10000.0
        assert result["total_paid"] == 7000.0
        assert result["active_rentals"] == 3

    def test_exception_returns_zeros(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.query.side_effect = Exception("DB error")
        result = WeeklyDigestService._get_dashboard_metrics(
            mock_db,
            1,
            date(2026, 10, 29),
            date(2026, 11, 5),
        )
        assert result["total_revenue"] == 0
        assert result["active_rentals"] == 0


class TestGetTopClients:
    """Cover _get_top_clients (lines 96-130)."""

    def test_success(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        row = SimpleNamespace(
            client_id=1, client_name="ClientCo", total_revenue=5000, invoices_count=3
        )
        q = MagicMock()
        q.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            row
        ]
        mock_db.query.return_value = q

        result = WeeklyDigestService._get_top_clients(
            mock_db, 1, date(2026, 10, 29), date(2026, 11, 5)
        )
        assert len(result) == 1
        assert result[0]["client_name"] == "ClientCo"

    def test_exception_returns_empty(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.query.side_effect = Exception("DB error")
        result = WeeklyDigestService._get_top_clients(
            mock_db, 1, date(2026, 10, 29), date(2026, 11, 5)
        )
        assert result == []


class TestGetTopVehicles:
    """Cover _get_top_vehicles (lines 132-175)."""

    def test_exception_returns_empty(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.query.side_effect = Exception("DB error")
        result = WeeklyDigestService._get_top_vehicles(
            mock_db, 1, date(2026, 10, 29), date(2026, 11, 5)
        )
        assert result == []


class TestGetOverdueInvoices:
    """Cover _get_overdue_invoices (lines 177-218)."""

    def test_exception_returns_empty(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.query.side_effect = Exception("DB error")
        result = WeeklyDigestService._get_overdue_invoices(mock_db, 1)
        assert result == []


class TestSendWeeklyDigest:
    """Cover send_weekly_digest (lines 220-308)."""

    def test_company_not_found(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        mock_db.get.return_value = None
        result = WeeklyDigestService.send_weekly_digest(mock_db, 999)
        assert result["success"] is False
        assert result["recipients_count"] == 0

    def test_no_accountants(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        company = SimpleNamespace(name="TestCo")
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

    def test_success_with_recipients(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        company = SimpleNamespace(name="TestCo")
        accountant = SimpleNamespace(email="acc@test.com")
        mock_db.get.return_value = company

        with (
            patch.object(
                WeeklyDigestService,
                "_get_dashboard_metrics",
                return_value={"total_revenue": 1000},
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


class TestSendDigestsForAllCompanies:
    """Cover send_digests_for_all_companies (lines 310-355)."""

    def test_runs_without_error(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        # Empty companies list - simplest path
        mock_db.query.return_value.all.return_value = []
        result = WeeklyDigestService.send_digests_for_all_companies(mock_db)
        assert isinstance(result, dict)


class TestFindAccountants:
    """Cover _find_accountants (lines 357-end)."""

    def test_returns_list_empty(self, mock_db):
        from app.services.weekly_digest_service import WeeklyDigestService

        # Empty result - simplest path
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = (
            []
        )
        result = WeeklyDigestService._find_accountants(mock_db, 1)
        assert isinstance(result, list)
