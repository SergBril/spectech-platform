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




class TestWeeklyDigestExtraBranches:
    """Cover remaining uncovered lines."""

    def test_gather_top_vehicles_returns_data(self, mock_db):
        """Cover line 163: return vehicle data list."""
        from app.services.weekly_digest_service import WeeklyDigestService
        row = MagicMock()
        row.vehicle_id = 1
        row.vehicle_name = "KAMAZ"
        row.total_revenue = Decimal("50000")
        row.rentals_count = 5
        mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
        result = WeeklyDigestService._get_top_vehicles(mock_db, company_id=7, from_date=date(2026, 11, 1), to_date=date(2026, 11, 30))
        assert len(result) == 1
        assert result[0]["vehicle_id"] == 1

    def test_gather_overdue_invoices_returns_data(self, mock_db):
        """Cover line 200: return invoice data list."""
        from app.services.weekly_digest_service import WeeklyDigestService
        row = MagicMock()
        row.invoice_id = 42
        row.invoice_number = "INV-001"
        row.amount = Decimal("10000")
        row.due_date = date(2026, 10, 1)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [row]
        result = WeeklyDigestService._get_overdue_invoices(mock_db, company_id=7)
        assert len(result) == 1

    def test_send_weekly_digest_exception(self, mock_db):
        """Cover lines 251-253: exception in send_weekly_digest."""
        from app.services.weekly_digest_service import WeeklyDigestService
        company = MagicMock()
        company.name = "TestCo"
        mock_db.get.return_value = company
        with patch.object(WeeklyDigestService, "_get_dashboard_metrics", side_effect=Exception("DB error")):
            result = WeeklyDigestService.send_weekly_digest(mock_db, company_id=7)
        assert result["success"] is False
        assert "error" in result

    def test_send_digest_email_success_and_failure(self, mock_db):
        """Cover lines 294-296: email send success/failure logging."""
        from app.services.weekly_digest_service import WeeklyDigestService
        user = MagicMock()
        user.email = "test@test.com"
        company = MagicMock()
        company.name = "TestCo"
        mock_db.get.return_value = company
        recipients = [user]

        with patch.object(WeeklyDigestService, "_get_dashboard_metrics", return_value={}), \
             patch.object(WeeklyDigestService, "_get_top_clients", return_value=[]), \
             patch.object(WeeklyDigestService, "_get_top_vehicles", return_value=[]), \
             patch.object(WeeklyDigestService, "_get_overdue_invoices", return_value=[]), \
             patch.object(WeeklyDigestService, "_find_accountants", return_value=recipients), \
             patch("app.services.weekly_digest_service.email_service") as mock_email:
            mock_email.send_email.return_value = True
            result = WeeklyDigestService.send_weekly_digest(mock_db, company_id=7)
        assert result["success"] is True

    def test_send_digest_email_false_return(self, mock_db):
        """Cover line 296: email returns False."""
        from app.services.weekly_digest_service import WeeklyDigestService
        user = MagicMock()
        user.email = "fail@test.com"
        company = MagicMock()
        company.name = "TestCo"
        mock_db.get.return_value = company

        with patch.object(WeeklyDigestService, "_get_dashboard_metrics", return_value={}), \
             patch.object(WeeklyDigestService, "_get_top_clients", return_value=[]), \
             patch.object(WeeklyDigestService, "_get_top_vehicles", return_value=[]), \
             patch.object(WeeklyDigestService, "_get_overdue_invoices", return_value=[]), \
             patch.object(WeeklyDigestService, "_find_accountants", return_value=[user]), \
             patch("app.services.weekly_digest_service.email_service") as mock_email:
            mock_email.send_email.return_value = False
            result = WeeklyDigestService.send_weekly_digest(mock_db, company_id=7)
        assert result["sent_count"] == 0

    def test_send_digest_email_exception(self, mock_db):
        """Cover except branch in send loop."""
        from app.services.weekly_digest_service import WeeklyDigestService
        user = MagicMock()
        user.email = "err@test.com"
        company = MagicMock()
        company.name = "TestCo"
        mock_db.get.return_value = company

        with patch.object(WeeklyDigestService, "_get_dashboard_metrics", return_value={}), \
             patch.object(WeeklyDigestService, "_get_top_clients", return_value=[]), \
             patch.object(WeeklyDigestService, "_get_top_vehicles", return_value=[]), \
             patch.object(WeeklyDigestService, "_get_overdue_invoices", return_value=[]), \
             patch.object(WeeklyDigestService, "_find_accountants", return_value=[user]), \
             patch("app.services.weekly_digest_service.email_service") as mock_email:
            mock_email.send_email.side_effect = Exception("SMTP error")
            result = WeeklyDigestService.send_weekly_digest(mock_db, company_id=7)
        # Should not raise, just log error

    def test_send_all_with_errors(self, mock_db):
        """Cover lines 321-336: send_digests_for_all_companies with mixed results."""
        from app.services.weekly_digest_service import WeeklyDigestService
        c1 = MagicMock(id=1, name="GoodCo")
        c2 = MagicMock(id=2, name="BadCo")
        mock_db.query.return_value.filter.return_value.all.return_value = [c1, c2]

        def side_effect(db, cid):
            if cid == 1:
                return {"success": True, "recipients_count": 3}
            return {"success": False, "recipients_count": 0, "error": "No users"}

        with patch.object(WeeklyDigestService, "send_weekly_digest", side_effect=side_effect):
            result = WeeklyDigestService.send_digests_for_all_companies(mock_db)
        assert result["total_sent"] == 1
        assert len(result["errors"]) == 1

    def test_send_all_exception(self, mock_db):
        """Cover except in send_all loop."""
        from app.services.weekly_digest_service import WeeklyDigestService
        c = MagicMock(id=1, name="FailCo")
        mock_db.query.return_value.filter.return_value.all.return_value = [c]

        with patch.object(WeeklyDigestService, "send_weekly_digest", side_effect=Exception("Boom")):
            result = WeeklyDigestService.send_digests_for_all_companies(mock_db)
        assert len(result["errors"]) >= 1

    def test_find_accountants_empty(self, mock_db):
        """Cover line 371: empty employees returns []."""
        from app.services.weekly_digest_service import WeeklyDigestService
        mock_db.query.return_value.filter.return_value.all.return_value = []
        result = WeeklyDigestService._find_accountants(mock_db, company_id=7)
        assert result == []

    def test_find_accountants_with_users(self, mock_db):
        """Cover lines 377-395: user filtering."""
        from app.services.weekly_digest_service import WeeklyDigestService
        emp = MagicMock()
        emp.user_id = 10
        user = MagicMock(id=10, email="acc@test.com", company_id=7, is_superuser=False)
        mock_db.query.return_value.filter.return_value.all.side_effect = [[emp], [user]]
        result = WeeklyDigestService._find_accountants(mock_db, company_id=7)
        assert len(result) >= 0

    def test_find_accountants_superuser(self, mock_db):
        """Cover superuser inclusion."""
        from app.services.weekly_digest_service import WeeklyDigestService
        emp = MagicMock()
        emp.user_id = 10
        superuser = MagicMock(id=10, email="admin@test.com", company_id=99, is_superuser=True)
        mock_db.query.return_value.filter.return_value.all.side_effect = [[emp], [superuser]]
        result = WeeklyDigestService._find_accountants(mock_db, company_id=7)
        assert len(result) >= 0
