"""Integration tests for Contractors API."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestContractorsAPI:
    """Тесты CRUD операций для контрагентов."""

    def test_list_contractors_empty(self, auth_client: TestClient, db_session: Session):
        """Список контрагентов пуст, если ничего не создано."""
        response = auth_client.get("/api/v1/contractors")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_create_contractor_success(
        self, auth_client: TestClient, db_session: Session
    ):
        """Успешное создание контрагента."""
        payload = {
            "type": "client",
            "name": "ООО Тестовый Клиент",
            "inn": "7707083893",
            "kpp": "770701001",
            "contact_name": "Иванов Иван",
            "contact_phone": "+79991234567",
            "contact_email": "test@example.com",
        }
        response = auth_client.post("/api/v1/contractors", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["inn"] == payload["inn"]
        assert data["type"] == "client"
        assert "id" in data
        assert "created_at" in data

    def test_create_contractor_invalid_type(
        self, auth_client: TestClient, db_session: Session
    ):
        """Ошибка при создании с невалидным типом."""
        payload = {
            "type": "invalid_type",
            "name": "Test Contractor",
        }
        response = auth_client.post("/api/v1/contractors", json=payload)
        assert response.status_code == 422

    def test_get_contractor_success(self, auth_client: TestClient, sample_contractor):
        """Успешное получение контрагента по ID."""
        response = auth_client.get(f"/api/v1/contractors/{sample_contractor.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_contractor.id
        assert data["name"] == sample_contractor.name

    def test_get_contractor_not_found(self, auth_client: TestClient):
        """404 при запросе несуществующего контрагента."""
        response = auth_client.get("/api/v1/contractors/99999")
        assert response.status_code == 404

    def test_update_contractor_success(
        self, auth_client: TestClient, sample_contractor
    ):
        """Успешное обновление контрагента."""
        update_payload = {
            "name": "Обновлённое название",
            "contact_phone": "+79998887766",
        }
        response = auth_client.patch(
            f"/api/v1/contractors/{sample_contractor.id}", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_payload["name"]
        assert data["contact_phone"] == update_payload["contact_phone"]

    def test_delete_contractor_success(
        self, auth_client: TestClient, sample_contractor
    ):
        """Успешное удаление контрагента (soft delete)."""
        response = auth_client.delete(f"/api/v1/contractors/{sample_contractor.id}")
        assert response.status_code == 204

        # Проверяем, что контрагент помечен как неактивный
        response = auth_client.get(f"/api/v1/contractors/{sample_contractor.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_list_contractors_with_filter(
        self, auth_client: TestClient, sample_contractor
    ):
        """Фильтрация списка по типу."""
        response = auth_client.get("/api/v1/contractors?type=client")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(c["type"] == "client" for c in data)

    def test_suggest_contractor_by_inn_not_found(
        self, auth_client: TestClient, db_session: Session
    ):
        """Поиск контрагента по ИНН - не найден."""
        payload = {"inn": "9999999999"}
        response = auth_client.post("/api/v1/contractors/suggest-inn", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["duplicate"] is False

    def test_suggest_contractor_by_inn_empty(
        self, auth_client: TestClient, db_session: Session
    ):
        """Поиск с пустым ИНН - ошибка 400."""
        payload = {"inn": ""}
        response = auth_client.post("/api/v1/contractors/suggest-inn", json=payload)
        assert response.status_code == 400
