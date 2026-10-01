"""Integration tests for Companies API."""

from fastapi.testclient import TestClient


class TestCompaniesAPI:
    """Тесты для настроек компаний."""

    def test_get_company_tax_settings_success(self, auth_client: TestClient, company):
        """Успешное получение налоговых настроек компании."""
        response = auth_client.get(f"/api/v1/companies/{company.id}/tax-settings")
        assert response.status_code == 200
        data = response.json()
        assert "default_tax_system" in data
        assert "default_vat_rate" in data
        assert "default_is_vat_included" in data

    def test_get_company_tax_settings_not_found(self, auth_client: TestClient):
        """404 при запросе настроек несуществующей компании."""
        response = auth_client.get("/api/v1/companies/99999/tax-settings")
        assert response.status_code == 404

    def test_update_company_tax_settings_success(
        self, auth_client: TestClient, company
    ):
        """Успешное обновление налоговых настроек."""
        update_payload = {
            "default_tax_system": "usn_6",
            "default_vat_rate": 0,
            "default_is_vat_included": False,
        }
        response = auth_client.patch(
            f"/api/v1/companies/{company.id}/tax-settings", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_tax_system"] == update_payload["default_tax_system"]
        # Decimal сериализуется в строку в JSON, поэтому сравниваем через float
        assert float(data["default_vat_rate"]) == float(
            update_payload["default_vat_rate"]
        )
        assert (
            data["default_is_vat_included"] == update_payload["default_is_vat_included"]
        )

    def test_update_company_tax_settings_to_osno(
        self, auth_client: TestClient, company
    ):
        """Успешное обновление на ОСНО с НДС 20%."""
        update_payload = {
            "default_tax_system": "osno",
            "default_vat_rate": 20,
            "default_is_vat_included": True,
        }
        response = auth_client.patch(
            f"/api/v1/companies/{company.id}/tax-settings", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_tax_system"] == "osno"
        assert float(data["default_vat_rate"]) == 20.0
        assert data["default_is_vat_included"] is True

    def test_update_company_tax_settings_invalid_system(
        self, auth_client: TestClient, company
    ):
        """Ошибка 400 при невалидной системе налогообложения."""
        update_payload = {
            "default_tax_system": "invalid_system",
            "default_vat_rate": 20,
            "default_is_vat_included": True,
        }
        response = auth_client.patch(
            f"/api/v1/companies/{company.id}/tax-settings", json=update_payload
        )
        assert response.status_code == 400

    def test_update_company_tax_settings_patent(self, auth_client: TestClient, company):
        """Успешное обновление на Патент."""
        update_payload = {
            "default_tax_system": "patent",
            "default_vat_rate": 0,
            "default_is_vat_included": False,
        }
        response = auth_client.patch(
            f"/api/v1/companies/{company.id}/tax-settings", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_tax_system"] == "patent"

    def test_update_company_tax_settings_npd(self, auth_client: TestClient, company):
        """Успешное обновление на НПД (самозанятые)."""
        update_payload = {
            "default_tax_system": "npd",
            "default_vat_rate": 0,
            "default_is_vat_included": False,
        }
        response = auth_client.patch(
            f"/api/v1/companies/{company.id}/tax-settings", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_tax_system"] == "npd"
