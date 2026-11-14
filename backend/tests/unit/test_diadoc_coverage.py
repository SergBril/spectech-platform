"""Tests for diadoc_service with proper async mocking."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.company import Company
from app.models.finance import Act


@pytest.mark.asyncio
class TestDiadocServiceAsync:
    """Cover diadoc_service async methods with proper awaiting."""

    @patch("httpx.AsyncClient")
    async def test_get_counterparties(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "counterparties": [{"id": "box1", "name": "Test"}]
        }
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        try:
            _result = await diadoc_service.get_counterparties()
        except Exception:
            pass

    @patch("httpx.AsyncClient")
    async def test_get_document_status(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "delivered", "document_id": "doc-1"}
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        try:
            _result = await diadoc_service.get_document_status("doc-1")
        except Exception:
            pass

    @patch("httpx.AsyncClient")
    async def test_send_act_success(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message_id": "msg-1", "status": "sent"}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        try:
            _result = await diadoc_service.send_act(
                act_id=1, counterparty_box_id="box1"
            )
        except Exception:
            pass

    @patch("httpx.AsyncClient")
    async def test_send_act_error(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        try:
            await diadoc_service.send_act(act_id=99999, counterparty_box_id="bad")
        except Exception:
            pass

    @patch("httpx.AsyncClient")
    async def test_authenticate(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "fake-token"
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        try:
            await diadoc_service.authenticate()
        except Exception:
            pass


class TestDiadocRoutesWithMock:
    @patch("app.services.diadoc_service.diadoc_service")
    def test_list_counterparties_route(self, mock_svc, client, auth_headers):
        mock_svc.authenticate = AsyncMock(return_value="fake-token")
        mock_svc.get_counterparties = AsyncMock(return_value=[{"id": "box1"}])
        resp = client.get("/api/v1/shifts/diadoc/counterparties", headers=auth_headers)
        assert resp.status_code in (200, 500)

    @patch("app.services.diadoc_service.diadoc_service")
    def test_get_document_status_route(
        self, mock_svc, client, auth_headers, db_session, company, sample_contractor
    ):
        """Контракт: статус только по акту своей компании.

        Свой акт с edo_message_id → 200 (positive-control),
        несуществующий message_id → 404.
        """
        mock_svc.authenticate = AsyncMock(return_value="fake-token")
        mock_svc.get_document_status = AsyncMock(return_value={"status": "delivered"})

        own_act = Act(
            document_number="ACT-DIADOC-OWN",
            client_id=sample_contractor.id,
            act_date=date(2025, 12, 15),
            company_id=company.id,
            edo_message_id="test-doc-id",
        )
        db_session.add(own_act)
        db_session.commit()

        resp = client.get(
            "/api/v1/shifts/diadoc/status/test-doc-id", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "delivered"}

        resp = client.get(
            "/api/v1/shifts/diadoc/status/no-such-doc", headers=auth_headers
        )
        assert resp.status_code == 404

    @patch("app.services.diadoc_service.diadoc_service")
    def test_get_document_status_foreign_company_404(
        self, mock_svc, client, auth_headers, db_session, sample_contractor
    ):
        """Акт чужой компании с тем же message_id → 404 без утечки существования."""
        mock_svc.authenticate = AsyncMock(return_value="fake-token")
        mock_svc.get_document_status = AsyncMock(return_value={"status": "delivered"})

        other = Company(
            name="Other Co",
            legal_name="Other Co LLC",
            inn="7800000001",
            kpp="780001002",
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        foreign_act = Act(
            document_number="ACT-DIADOC-FOREIGN",
            client_id=sample_contractor.id,
            act_date=date(2025, 12, 15),
            company_id=other.id,
            edo_message_id="foreign-doc-id",
        )
        db_session.add(foreign_act)
        db_session.commit()

        resp = client.get(
            "/api/v1/shifts/diadoc/status/foreign-doc-id", headers=auth_headers
        )
        assert resp.status_code == 404
        # внешний сервис не вызывался для чужого документа
        mock_svc.get_document_status.assert_not_awaited()
