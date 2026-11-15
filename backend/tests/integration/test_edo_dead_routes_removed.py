"""AU: мёртвые кросс-тенант роуты edo.py удалены — пути дают 404.

Удалены GET /edo/document-status/{message_id} и GET /edo/counterparties
(0 ссылок frontend/тесты/репо, без проверки принадлежности компании).
refresh-statuses и webhook/diadoc остаются легитимным API и покрыты
test_edo_company_passing.py и test_edo_webhook_verify.py.
"""

import pytest

pytestmark = [pytest.mark.integration]


def test_document_status_route_removed(client, auth_headers):
    resp = client.get(
        "/api/v1/edo/document-status/any-message-id", headers=auth_headers
    )
    assert resp.status_code == 404


def test_counterparties_route_removed(client, auth_headers):
    resp = client.get("/api/v1/edo/counterparties", headers=auth_headers)
    assert resp.status_code == 404
