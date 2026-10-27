"""Tests for maintenance API coverage improvement."""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token
    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_auth_token(admin_user):
    from app.services.auth_service import create_access_token
    return create_access_token(admin_user)


@pytest.fixture
def admin_auth_headers(admin_auth_token):
    return {"Authorization": f"Bearer {admin_auth_token}"}


class TestListMaintenanceOrders:
    """Cover list_maintenance_orders (lines 77-135)."""

    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_filter_by_status(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders?status=planned", headers=auth_headers)
        assert resp.status_code == 200

    def test_filter_by_priority(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders?priority=high", headers=auth_headers)
        assert resp.status_code == 200

    def test_pagination(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders?skip=0&limit=10", headers=auth_headers)
        assert resp.status_code == 200


class TestCreateMaintenanceOrder:
    """Cover create_maintenance_order (lines 136-224)."""

    def test_create_basic(self, client, admin_auth_headers, sample_vehicle):
        payload = {
            "vehicle_id": sample_vehicle.id,
            "order_type": "repair",
            "priority": "medium",
            "title": "Test maintenance order",
            "description": "Test description",
        }
        resp = client.post("/api/v1/maintenance/orders", json=payload, headers=admin_auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert "order_number" in data


class TestGetMaintenanceOrder:
    """Cover get_maintenance_order (lines 225-261)."""

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/maintenance/orders/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_existing(self, client, admin_auth_headers, sample_vehicle):
        # Create first
        payload = {
            "vehicle_id": sample_vehicle.id,
            "order_type": "repair",
            "priority": "medium",
            "title": "Test order for get",
            "description": "Test description",
        }
        create_resp = client.post("/api/v1/maintenance/orders", json=payload, headers=admin_auth_headers)
        order_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/maintenance/orders/{order_id}", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == order_id


class TestGetTco:
    """Cover get_tco endpoint (lines 435-480)."""

    def test_tco(self, client, auth_headers, sample_vehicle):
        resp = client.get(f"/api/v1/maintenance/tco/{sample_vehicle.id}", headers=auth_headers)
        assert resp.status_code == 200


class TestHelperFunctions:
    """Cover helper functions _generate_order_number, _calculate_costs, _enrich_response."""

    def test_generate_order_number(self, db_session):
        from app.api.routes.maintenance import _generate_order_number
        num = _generate_order_number(db_session)
        assert "2026" in num or "2025" in num  # Contains year
        assert len(num.split("-")) == 3

    def test_calculate_costs(self, db_session):
        from app.api.routes.maintenance import _calculate_costs
        from app.models.maintenance import MaintenanceOrder
        from decimal import Decimal

        order = MaintenanceOrder(
            company_id=1,
            vehicle_id=1,
            order_type="repair",
            priority="normal",
            status="draft",
            order_number="TO-TEST-0001",
            parts=[],
            works=[],
        )
        _calculate_costs(order)
        assert order.parts_cost == Decimal("0")
        assert order.labor_cost == Decimal("0")
        assert order.total_cost == Decimal("0")
