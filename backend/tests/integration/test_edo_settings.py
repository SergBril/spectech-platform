"""Настройки ЭДО: запись должна происходить, секрет не должен утекать.

Раньше PUT возвращал {"message": "EDO settings updated"}, но не писал ничего:
колонок не существовало, а `if hasattr(company, key)` отбрасывал все поля.
Проверено замером на живом сервере: PUT ключа -> 200, GET после -> пусто.
"""

import pytest

from app.models.company import Company

pytestmark = [pytest.mark.integration]


class TestEdoSettingsPersistence:
    def test_put_actually_stores_the_box_id(
        self, client, auth_headers, db_session, company
    ):
        r = client.put(
            "/api/v1/edo-settings",
            json={"diadoc_box_id": "box-persist-1"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        db_session.expire_all()
        assert db_session.get(Company, company.id).diadoc_box_id == "box-persist-1"

    def test_secret_is_encrypted_at_rest(
        self, client, auth_headers, db_session, company
    ):
        r = client.put(
            "/api/v1/edo-settings",
            json={"diadoc_api_key": "PLAINTEXT-KEY-9876"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        db_session.expire_all()
        raw = db_session.get(Company, company.id).diadoc_api_key
        assert (
            raw and raw != "PLAINTEXT-KEY-9876"
        ), "ключ не должен лежать открытым текстом"
        assert "PLAINTEXT-KEY-9876" not in raw

        from app.core.crypto import decrypt_secret

        assert decrypt_secret(raw) == "PLAINTEXT-KEY-9876"

    def test_get_returns_a_mask_not_the_secret(self, client, auth_headers, company):
        client.put(
            "/api/v1/edo-settings",
            json={"diadoc_api_key": "PLAINTEXT-KEY-9876"},
            headers=auth_headers,
        )
        r = client.get("/api/v1/edo-settings", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "PLAINTEXT-KEY-9876" not in str(body)
        assert body["diadoc_api_key"] == "****9876"
        assert body["diadoc_api_key_set"] is True

    def test_sending_the_mask_back_does_not_erase_the_key(
        self, client, auth_headers, db_session, company
    ):
        client.put(
            "/api/v1/edo-settings",
            json={"diadoc_api_key": "PLAINTEXT-KEY-9876"},
            headers=auth_headers,
        )
        db_session.expire_all()
        before = db_session.get(Company, company.id).diadoc_api_key

        masked = client.get("/api/v1/edo-settings", headers=auth_headers).json()[
            "diadoc_api_key"
        ]
        client.put(
            "/api/v1/edo-settings",
            json={"diadoc_api_key": masked, "diadoc_box_id": "box-2"},
            headers=auth_headers,
        )
        db_session.expire_all()
        after = db_session.get(Company, company.id)
        assert after.diadoc_api_key == before, "маска не должна затирать ключ"
        assert after.diadoc_box_id == "box-2"

    def test_defaults_before_any_save(self, client, auth_headers, company):
        body = client.get("/api/v1/edo-settings", headers=auth_headers).json()
        assert body["operator"] == "diadoc"
        assert body["diadoc_api_key"] == ""
        assert body["diadoc_api_key_set"] is False
        assert body["default_format"] == "upd_5_03"

    def test_other_company_settings_are_not_touchable(
        self, client, auth_headers, db_session, company
    ):
        # sample_company - алиас той же company, поэтому создаём отдельную.
        other = Company(name="Другая компания ЭДО", inn="7799887766")
        db_session.add(other)
        db_session.commit()
        other_id = other.id

        # PUT работает по company_id из токена, не из тела.
        client.put(
            "/api/v1/edo-settings",
            json={"diadoc_box_id": "box-mine", "company_id": other_id},
            headers=auth_headers,
        )
        db_session.expire_all()
        assert db_session.get(Company, company.id).diadoc_box_id == "box-mine"
        assert db_session.get(Company, other_id).diadoc_box_id is None


class TestEdoSecretRemoval:
    def test_empty_string_clears_the_secret(
        self, client, auth_headers, db_session, company
    ):
        client.put(
            "/api/v1/edo-settings",
            json={"diadoc_api_key": "KEY-TO-REMOVE-1234"},
            headers=auth_headers,
        )
        db_session.expire_all()
        assert db_session.get(Company, company.id).diadoc_api_key is not None

        r = client.put(
            "/api/v1/edo-settings", json={"diadoc_api_key": ""}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        db_session.expire_all()
        assert db_session.get(Company, company.id).diadoc_api_key is None

        body = client.get("/api/v1/edo-settings", headers=auth_headers).json()
        assert body["diadoc_api_key"] == ""
        assert body["diadoc_api_key_set"] is False

    def test_mask_still_does_not_clear(self, client, auth_headers, db_session, company):
        client.put(
            "/api/v1/edo-settings",
            json={"diadoc_api_key": "KEY-TO-KEEP-5678"},
            headers=auth_headers,
        )
        db_session.expire_all()
        before = db_session.get(Company, company.id).diadoc_api_key
        client.put(
            "/api/v1/edo-settings",
            json={"diadoc_api_key": "****5678"},
            headers=auth_headers,
        )
        db_session.expire_all()
        assert db_session.get(Company, company.id).diadoc_api_key == before
