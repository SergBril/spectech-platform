"""Integration tests for Vehicles API."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestVehiclesAPI:
    """Тесты CRUD операций для техники."""

    def test_list_vehicles_empty(self, auth_client: TestClient, db_session: Session):
        """Список техники пуст, если ничего не создано."""
        response = auth_client.get("/api/v1/vehicles")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] == 0

    def test_list_vehicles_with_data(self, auth_client: TestClient, sample_vehicle):
        """Список техники с данными."""
        response = auth_client.get("/api/v1/vehicles")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_vehicle_success(self, auth_client: TestClient, sample_vehicle):
        """Успешное получение техники по ID."""
        response = auth_client.get(f"/api/v1/vehicles/{sample_vehicle.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_vehicle.id
        assert data["name"] == sample_vehicle.name
        assert "category_name" in data
        assert "attribute_values" in data

    def test_get_vehicle_not_found(self, auth_client: TestClient):
        """404 при запросе несуществующей техники."""
        response = auth_client.get("/api/v1/vehicles/99999")
        assert response.status_code == 404

    def test_create_vehicle_minimal(self, auth_client: TestClient, db_session: Session):
        """Создание техники с минимальными данными."""
        payload = {
            "name": "Тестовый экскаватор",
            "id_type": "internal",
            "id_value": "TEST-EXC-001",
            "status": "free",
        }
        response = auth_client.post("/api/v1/vehicles", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["id_value"] == payload["id_value"]
        assert "id" in data

    def test_create_vehicle_duplicate_id_value(
        self, auth_client: TestClient, sample_vehicle
    ):
        """Ошибка 409 при создании с дублирующимся id_value."""
        payload = {
            "name": "Дубликат",
            "id_type": sample_vehicle.id_type,
            "id_value": sample_vehicle.id_value,
            "status": "free",
        }
        response = auth_client.post("/api/v1/vehicles", json=payload)
        assert response.status_code == 409

    def test_update_vehicle_success(self, auth_client: TestClient, sample_vehicle):
        """Успешное обновление техники."""
        update_payload = {
            "name": "Обновлённое название",
            "status": "on_site",
        }
        response = auth_client.put(
            f"/api/v1/vehicles/{sample_vehicle.id}", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_payload["name"]
        assert data["status"] == update_payload["status"]

    def test_delete_vehicle_success(self, auth_client: TestClient, sample_vehicle):
        """Успешное удаление техники (soft delete)."""
        response = auth_client.delete(f"/api/v1/vehicles/{sample_vehicle.id}")
        assert response.status_code == 204

        # Проверяем, что техника помечена как удалённая
        response = auth_client.get(f"/api/v1/vehicles/{sample_vehicle.id}")
        assert response.status_code == 404  # Soft-deleted не возвращается

    def test_list_vehicles_with_status_filter(
        self, auth_client: TestClient, sample_vehicle
    ):
        """Фильтрация по статусу."""
        response = auth_client.get("/api/v1/vehicles?status=free")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all(v["status"] == "free" for v in data["items"])

    def test_check_vehicle_availability_success(
        self, auth_client: TestClient, sample_vehicle
    ):
        """Проверка доступности техники - доступна."""
        from datetime import datetime, timedelta

        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(hours=8)

        response = auth_client.get(
            f"/api/v1/vehicles/{sample_vehicle.id}/availability",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "vehicle_id" in data
        assert data["vehicle_id"] == sample_vehicle.id

    def test_check_vehicle_availability_not_found(self, auth_client: TestClient):
        """Проверка доступности - техника не найдена."""
        from datetime import datetime, timedelta

        start = datetime.now()
        end = start + timedelta(hours=8)

        response = auth_client.get(
            "/api/v1/vehicles/99999/availability",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )
        assert response.status_code == 404
