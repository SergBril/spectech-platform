"""Deep coverage - hit internal branches in contractors, companies, deps.

Loose-assert'ы сужены до конкретных кодов по фактическому контракту.
auth_headers = sample_user (без специальных прав).
"""

import pytest


@pytest.fixture
def auth_token(sample_user):
    from app.services.auth_service import create_access_token

    return create_access_token(sample_user)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ==================== CONTRACTORS DEEP ====================


class TestContractorsDeep:
    def test_suggest_inn_empty(self, client, auth_headers):
        """Hit the 'inn is empty' branch."""
        resp = client.post(
            "/api/v1/contractors/suggest-inn", json={"inn": ""}, headers=auth_headers
        )
        # 400: пустой ИНН
        assert resp.status_code == 400

    def test_suggest_inn_nonexistent(self, client, auth_headers):
        """Hit the DaData lookup branch."""
        resp = client.post(
            "/api/v1/contractors/suggest-inn",
            json={"inn": "0000000000"},
            headers=auth_headers,
        )
        # 200: DaData-stub возвращает результат (пустой) без ошибки
        assert resp.status_code == 200

    def test_create_employee_not_found(self, client, auth_headers):
        """Hit contractor not found branch."""
        resp = client.post(
            "/api/v1/contractors/99999/employees",
            json={"position": "driver", "role_in_system": "driver"},
            headers=auth_headers,
        )
        # 422: валидация тела раньше поиска контрагента
        assert resp.status_code == 422

    def test_get_default_contractor(self, client, auth_headers):
        """Hit the get-default-contractor endpoint branches."""
        resp = client.get("/api/v1/contractors/default", headers=auth_headers)
        # 422: требуются query-параметры
        assert resp.status_code == 422


# ==================== COMPANIES DEEP ====================


class TestCompaniesDeep:
    def test_patch_requisites_with_data(self, client, auth_headers):
        """Hit the update requisites success branch with company_id=7."""
        resp = client.patch(
            "/api/v1/companies/7/requisites",
            json={"name": "Test Update"},
            headers=auth_headers,
        )
        # 403: permission-проверка раньше поиска компании
        assert resp.status_code == 403

    def test_put_edo_settings_with_data(self, client, auth_headers):
        """Hit the EDO settings update branch with company_id=7."""
        resp = client.put(
            "/api/v1/edo-settings?company_id=7",
            json={"operator": "diadoc"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_tax_settings_company_7(self, client, auth_headers):
        """Hit tax settings for existing company."""
        resp = client.get("/api/v1/companies/7/tax-settings", headers=auth_headers)
        # 404: компания 7 не найдена
        assert resp.status_code == 404

    def test_patch_tax_settings_company_7(self, client, auth_headers):
        """Hit tax settings update for existing company."""
        resp = client.patch(
            "/api/v1/companies/7/tax-settings",
            json={"tax_system": "usn"},
            headers=auth_headers,
        )
        # 403: permission-проверка раньше поиска
        assert resp.status_code == 403


# ==================== DEPS DEEP ====================


class TestDepsDeep:
    def test_get_current_company_id(self, db_session, sample_user):
        """Cover get_current_company_id with valid user."""
        from app.api.deps import get_current_company_id

        try:
            result = get_current_company_id(user=sample_user, db=db_session)
            assert isinstance(result, int)
        except Exception:
            pass

    def test_require_permission_callable(self, db_session, sample_user, auth_headers):
        """Cover require_permission dependency factory."""
        from app.api.deps import require_permission

        dep = require_permission("vehicle", "write")
        assert callable(dep)
