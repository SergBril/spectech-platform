"""Unit-тесты сервиса еженедельного дайджеста."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.services.weekly_digest_service import WeeklyDigestService


class TestWeeklyDigestService:
    """Тесты сервиса дайджеста."""

    def test_find_accountants_returns_users(
        self, db_session, company
    ):
        """✅ Находит пользователей-бухгалтеров."""
        from app.models.auth import User
        from app.models.contractor import Contractor, Employee
        
        contractor = Contractor(
            name="Accountant Contractor",
            type="employee",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.commit()
        
        # 🆕 Добавляем full_name (обязательное поле)
        user = User(
            email="accountant@test.com",
            full_name="Accountant User",
            password_hash="hash",
            company_id=company.id,
        )
        db_session.add(user)
        db_session.commit()
        
        employee = Employee(
            contractor_id=contractor.id,
            user_id=user.id,
            role_in_system="accountant",
        )
        db_session.add(employee)
        db_session.commit()
        
        accountants = WeeklyDigestService._find_accountants(db_session, company.id)
        
        assert len(accountants) >= 1
        assert any(u.email == "accountant@test.com" for u in accountants)

    def test_find_accountants_empty_when_no_employees(
        self, db_session, company
    ):
        """✅ Возвращает пустой список, если нет сотрудников."""
        accountants = WeeklyDigestService._find_accountants(db_session, company.id)
        assert accountants == []

    def test_send_weekly_digest_no_company(
        self, db_session
    ):
        """✅ Возвращает success=False для несуществующей компании."""
        result = WeeklyDigestService.send_weekly_digest(db_session, 99999)
        assert result["success"] is False
        assert result["recipients_count"] == 0

    def test_send_weekly_digest_no_accountants(
        self, db_session, company
    ):
        """✅ Возвращает recipients_count=0 если нет бухгалтеров."""
        result = WeeklyDigestService.send_weekly_digest(db_session, company.id)
        assert result["success"] is True
        assert result["recipients_count"] == 0
        assert "period" in result

    @patch("app.services.weekly_digest_service.email_service")
    def test_send_weekly_digest_sends_to_accountants(
        self, mock_email, db_session, company
    ):
        """✅ Отправляет дайджест всем найденным бухгалтерам."""
        from app.models.auth import User
        from app.models.contractor import Contractor, Employee
        
        # Создаём 2 бухгалтеров
        users = []
        for i in range(2):
            contractor = Contractor(
                name=f"Accountant {i}",
                type="employee",
                company_id=company.id,
            )
            db_session.add(contractor)
            db_session.commit()
            
            user = User(
                email=f"acc{i}@test.com",
                full_name=f"Accountant User {i}",
                password_hash="hash",
                company_id=company.id,
            )
            db_session.add(user)
            db_session.commit()
            
            employee = Employee(
                contractor_id=contractor.id,
                user_id=user.id,
                role_in_system="accountant",
            )
            db_session.add(employee)
            db_session.commit()
            
            db_session.refresh(user)
            users.append(user)
        
        mock_email.send_email.return_value = True
        
        result = WeeklyDigestService.send_weekly_digest(db_session, company.id)
        
        assert result["success"] is True
        assert result["recipients_count"] == 2
        assert mock_email.send_email.call_count == 2
        
        call_kwargs = mock_email.send_email.call_args[1]
        assert call_kwargs["template_name"] == "email/weekly_digest.html"

    @patch("app.services.weekly_digest_service.email_service")
    def test_send_weekly_digest_handles_email_failure(
        self, mock_email, db_session, company
    ):
        """✅ Устойчив к падениям email-сервиса."""
        from app.models.auth import User
        from app.models.contractor import Contractor, Employee
        
        contractor = Contractor(
            name="Accountant",
            type="employee",
            company_id=company.id,
        )
        db_session.add(contractor)
        db_session.commit()
        
        user = User(
            email="acc@test.com",
            full_name="Accountant User",
            password_hash="hash",
            company_id=company.id,
        )
        db_session.add(user)
        db_session.commit()
        
        employee = Employee(
            contractor_id=contractor.id,
            user_id=user.id,
            role_in_system="accountant",
        )
        db_session.add(employee)
        db_session.commit()
        
        mock_email.send_email.side_effect = Exception("SMTP error")
        
        result = WeeklyDigestService.send_weekly_digest(db_session, company.id)
        
        assert result["success"] is True
        assert result["recipients_count"] == 0

    @patch("app.services.weekly_digest_service.WeeklyDigestService.send_weekly_digest")
    def test_send_digests_for_all_companies(
        self, mock_send_digest, db_session, company
    ):
        """✅ Отправляет дайджест всем активным компаниям."""
        mock_send_digest.return_value = {
            "success": True,
            "recipients_count": 2,
            "period": {"from": date.today() - timedelta(days=7), "to": date.today()},
        }
        
        result = WeeklyDigestService.send_digests_for_all_companies(db_session)
        
        assert "total_companies" in result
        assert "successful" in result
        assert "total_recipients" in result
        assert result["total_companies"] >= 1

    def test_get_dashboard_metrics_empty_db(self, db_session, company):
        """✅ Метрики возвращаются даже при пустой БД."""
        today = date.today()
        from_date = today - timedelta(days=7)
        
        metrics = WeeklyDigestService._get_dashboard_metrics(
            db_session, company.id, from_date, today
        )
        
        assert "total_revenue" in metrics
        assert "total_paid" in metrics
        assert "total_commission" in metrics
        assert metrics["total_revenue"] == 0

    def test_get_top_clients_empty(self, db_session, company):
        """✅ Топ клиентов пустой при отсутствии данных."""
        today = date.today()
        from_date = today - timedelta(days=7)
        
        clients = WeeklyDigestService._get_top_clients(
            db_session, company.id, from_date, today, limit=5
        )
        
        assert isinstance(clients, list)
        assert len(clients) == 0

    def test_get_top_vehicles_empty(self, db_session, company):
        """✅ Топ техники пустой при отсутствии данных."""
        today = date.today()
        from_date = today - timedelta(days=7)
        
        vehicles = WeeklyDigestService._get_top_vehicles(
            db_session, company.id, from_date, today, limit=5
        )
        
        assert isinstance(vehicles, list)
        assert len(vehicles) == 0

    def test_get_overdue_invoices_empty(self, db_session, company):
        """✅ Просроченные счета пустые при отсутствии данных."""
        invoices = WeeklyDigestService._get_overdue_invoices(
            db_session, company.id, limit=10
        )
        
        assert isinstance(invoices, list)
        assert len(invoices) == 0