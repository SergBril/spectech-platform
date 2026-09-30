"""Integration tests for Payout API endpoints (Sprint 4 Task 3)."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestPayoutApproval:
    """Тесты одобрения выплат (draft → sent)."""

    def test_approve_payout_success(self, auth_client: TestClient, sample_payout):
        """✅ Одобрение draft выплаты меняет статус на sent."""
        response = auth_client.post(
            f"/api/v1/finance/payouts/{sample_payout.id}/approve"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["new_status"] == "sent"
        assert "approved" in data["message"].lower()

    def test_approve_payout_not_found(self, auth_client: TestClient):
        """❌ Одобрение несуществующей выплаты возвращает 404."""
        response = auth_client.post("/api/v1/finance/payouts/999999/approve")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_approve_already_sent_payout(
        self, auth_client: TestClient, sample_payout, db_session
    ):
        """❌ Нельзя одобрить уже отправленную выплату (409 Conflict)."""
        # Сначала одобряем
        sample_payout.status = "sent"
        db_session.commit()

        response = auth_client.post(
            f"/api/v1/finance/payouts/{sample_payout.id}/approve"
        )

        assert response.status_code == 409
        assert "draft" in response.json()["detail"].lower()

    def test_approve_paid_payout_fails(
        self, auth_client: TestClient, sample_payout, db_session
    ):
        """❌ Нельзя одобрить выплаченную выплату."""
        sample_payout.status = "paid"
        db_session.commit()

        response = auth_client.post(
            f"/api/v1/finance/payouts/{sample_payout.id}/approve"
        )

        assert response.status_code == 409


@pytest.mark.integration
class TestPayoutPayment:
    """Тесты отметки выплат как выплаченных (sent → paid)."""

    def test_pay_payout_success(
        self, auth_client: TestClient, sample_payout, db_session
    ):
        """✅ Отметка sent выплаты как paid."""
        sample_payout.status = "sent"
        db_session.commit()

        response = auth_client.post(f"/api/v1/finance/payouts/{sample_payout.id}/pay")

        assert response.status_code == 200
        data = response.json()
        assert data["new_status"] == "paid"
        assert "paid" in data["message"].lower()

    def test_pay_draft_payout_fails(self, auth_client: TestClient, sample_payout):
        """❌ Нельзя выплатить draft выплату (сначала нужно одобрить)."""
        response = auth_client.post(f"/api/v1/finance/payouts/{sample_payout.id}/pay")

        assert response.status_code == 409
        assert "sent" in response.json()["detail"].lower()

    def test_pay_nonexistent_payout(self, auth_client: TestClient):
        """❌ Выплата несуществующей выплаты возвращает 404."""
        response = auth_client.post("/api/v1/finance/payouts/999999/pay")

        assert response.status_code == 404


@pytest.mark.integration
class TestPayoutFullWorkflow:
    """Тесты полного цикла: draft → sent → paid."""

    def test_full_payout_workflow(self, auth_client: TestClient, sample_payout):
        """✅ Полный цикл выплаты через API."""
        payout_id = sample_payout.id

        # Шаг 1: draft → sent
        r1 = auth_client.post(f"/api/v1/finance/payouts/{payout_id}/approve")
        assert r1.status_code == 200
        assert r1.json()["new_status"] == "sent"

        # Шаг 2: sent → paid
        r2 = auth_client.post(f"/api/v1/finance/payouts/{payout_id}/pay")
        assert r2.status_code == 200
        assert r2.json()["new_status"] == "paid"

        # Проверка финального статуса
        assert r2.json()["payout_id"] == payout_id


@pytest.mark.integration
class TestPayoutsSummary:
    """Тесты сводки по выплатам."""

    def test_get_payouts_summary(self, auth_client: TestClient, sample_payout):
        """✅ Получение сводки за период."""
        from datetime import date, timedelta

        date_from = (date.today() - timedelta(days=30)).isoformat()
        date_to = (date.today() + timedelta(days=1)).isoformat()

        response = auth_client.get(
            f"/api/v1/finance/payouts/summary?date_from={date_from}&date_to={date_to}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_payouts" in data
        assert "total_gross" in data
        assert "total_commission" in data
        assert "total_net" in data
        assert "pending_payouts" in data

    def test_payouts_summary_with_data(self, auth_client: TestClient, sample_payout):
        """✅ Сводка учитывает созданную выплату."""
        from datetime import date, timedelta

        date_from = (date.today() - timedelta(days=1)).isoformat()
        date_to = (date.today() + timedelta(days=1)).isoformat()

        response = auth_client.get(
            f"/api/v1/finance/payouts/summary?date_from={date_from}&date_to={date_to}"
        )

        data = response.json()
        assert data["total_payouts"] >= 1
        assert data["total_gross"] >= 100000
        assert data["total_commission"] >= 15000
        assert data["pending_payouts"] >= 1  # draft выплата считается pending

    def test_payouts_summary_empty_period(self, auth_client: TestClient, company):
        """✅ Сводка за пустой период возвращает нули."""
        response = auth_client.get(
            "/api/v1/finance/payouts/summary?date_from=2020-01-01&date_to=2020-01-31"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_payouts"] == 0
        assert data["total_net"] == 0
