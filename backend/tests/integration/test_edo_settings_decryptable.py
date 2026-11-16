"""AW: GET /edo-settings — флаги читаемости секретов.

Существующие поля (маска, *_set) не меняются; добавлены только
diadoc_api_key_decryptable / sbis_token_decryptable.
"""

import pytest

from app.core.crypto import ENC_PREFIX, encrypt_secret

pytestmark = [pytest.mark.integration]


def test_decryptable_true_for_readable_secret(
    client, auth_headers, db_session, company
):
    company.diadoc_api_key = encrypt_secret("readable-key")
    company.sbis_token = None
    db_session.commit()

    resp = client.get("/api/v1/edo-settings", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["diadoc_api_key_decryptable"] is True
    assert body["sbis_token_decryptable"] is True
    # существующие поля не изменились
    assert body["diadoc_api_key"] == "****-key"
    assert body["diadoc_api_key_set"] is True
    assert body["sbis_token"] == ""
    assert body["sbis_token_set"] is False


def test_decryptable_false_for_unreadable_secret(
    client, auth_headers, db_session, company
):
    company.diadoc_api_key = ENC_PREFIX + "garbage-token"
    db_session.commit()

    resp = client.get("/api/v1/edo-settings", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["diadoc_api_key_decryptable"] is False
    # существующие поля не изменились
    assert body["diadoc_api_key_set"] is True
    assert body["diadoc_api_key"] == ""
