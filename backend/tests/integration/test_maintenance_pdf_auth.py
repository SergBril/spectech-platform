"""AF: maintenance PDF — Authorization header вместо ?token= (вариант A отчёта AB).

Регресс-тесты на закрытие вектора утечки сессионного JWT в URL
(nginx access.log, история браузера, Referer). PDF генерируется реально.
"""

import pytest
from fastapi.testclient import TestClient

from app.models.company import Company
from app.models.maintenance import (
    MaintenanceOrder,
    MaintenanceOrderStatus,
    MaintenanceOrderType,
    MaintenancePriority,
)

pytestmark = [pytest.mark.integration]


def _make_order(db_session, company_id, vehicle_id, number, status, created_by_id):
    order = MaintenanceOrder(
        company_id=company_id,
        vehicle_id=vehicle_id,
        order_number=number,
        title="Тестовый наряд",
        order_type=MaintenanceOrderType.repair,
        priority=MaintenancePriority.medium,
        status=status,
        created_by_id=created_by_id,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def order(db_session, company, sample_vehicle, admin_user):
    return _make_order(
        db_session,
        company.id,
        sample_vehicle.id,
        "TO-AUTH-0001",
        MaintenanceOrderStatus.planned,
        admin_user.id,
    )


@pytest.fixture
def completed_order(db_session, company, sample_vehicle, admin_user):
    return _make_order(
        db_session,
        company.id,
        sample_vehicle.id,
        "TO-AUTH-0002",
        MaintenanceOrderStatus.completed,
        admin_user.id,
    )


@pytest.fixture
def foreign_order(db_session, sample_vehicle, admin_user):
    other = Company(
        name="PDF Other Co",
        legal_name="ООО Другая",
        inn="9999999991",
        is_active=True,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    return _make_order(
        db_session,
        other.id,
        sample_vehicle.id,
        "TO-AUTH-0003",
        MaintenanceOrderStatus.planned,
        admin_user.id,
    )


class TestMaintenancePdfAuth:
    def test_no_auth_401(self, client: TestClient, order):
        resp = client.get(f"/api/v1/maintenance/orders/{order.id}/pdf")
        assert resp.status_code == 401

    def test_header_auth_200_pdf(self, client: TestClient, auth_headers, order):
        resp = client.get(
            f"/api/v1/maintenance/orders/{order.id}/pdf", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    def test_foreign_order_404(self, client: TestClient, auth_headers, foreign_order):
        resp = client.get(
            f"/api/v1/maintenance/orders/{foreign_order.id}/pdf", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_token_in_url_401(self, client: TestClient, auth_token, order):
        """Регресс: сессионный JWT в ?token= больше не принимается."""
        resp = client.get(
            f"/api/v1/maintenance/orders/{order.id}/pdf?token={auth_token}"
        )
        assert resp.status_code == 401

    def test_token_in_url_with_header_401(
        self, client: TestClient, auth_headers, auth_token, order
    ):
        """Явный запрет ?token= даже при валидном заголовке."""
        resp = client.get(
            f"/api/v1/maintenance/orders/{order.id}/pdf?token={auth_token}",
            headers=auth_headers,
        )
        assert resp.status_code == 401


class TestMaintenanceActPdfAuth:
    def test_no_auth_401(self, client: TestClient, completed_order):
        resp = client.get(f"/api/v1/maintenance/orders/{completed_order.id}/act/pdf")
        assert resp.status_code == 401

    def test_completed_200_pdf(self, client: TestClient, auth_headers, completed_order):
        resp = client.get(
            f"/api/v1/maintenance/orders/{completed_order.id}/act/pdf",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    def test_not_completed_400(self, client: TestClient, auth_headers, order):
        resp = client.get(
            f"/api/v1/maintenance/orders/{order.id}/act/pdf", headers=auth_headers
        )
        assert resp.status_code == 400

    def test_foreign_404(self, client: TestClient, auth_headers, foreign_order):
        resp = client.get(
            f"/api/v1/maintenance/orders/{foreign_order.id}/act/pdf",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_token_in_url_401(self, client: TestClient, auth_token, completed_order):
        resp = client.get(
            f"/api/v1/maintenance/orders/{completed_order.id}/act/pdf?token={auth_token}"
        )
        assert resp.status_code == 401
