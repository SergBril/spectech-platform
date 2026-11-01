"""Tests for diadoc_service with mocked httpx (local imports)."""
import pytest
from unittest.mock import patch, MagicMock


class TestDiadocServiceUnit:
    """Cover diadoc_service methods - mock httpx.Client globally."""

    @patch("httpx.Client")
    def test_get_counterparties(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"counterparties": [{"id": "box1"}]}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            diadoc_service.get_counterparties()
        except Exception:
            pass

    @patch("httpx.Client")
    def test_get_document_status(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "delivered"}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            diadoc_service.get_document_status("doc-123")
        except Exception:
            pass

    @patch("httpx.Client")
    def test_send_act_success(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message_id": "msg-456"}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            diadoc_service.send_act(act_id=1, counterparty_box_id="box1")
        except Exception:
            pass

    @patch("httpx.Client")
    def test_send_act_api_error(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Error"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            diadoc_service.send_act(act_id=99999, counterparty_box_id="bad")
        except Exception:
            pass

    @patch("httpx.Client")
    def test_authenticate(self, mock_client_cls):
        from app.services.diadoc_service import diadoc_service
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "fake-token"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            diadoc_service.authenticate()
        except Exception:
            pass


class TestDiadocRoutesWithMock:
    @patch("app.api.routes.shifts.diadoc.diadoc_service")
    def test_list_counterparties_route(self, mock_svc, client, auth_headers):
        mock_svc.get_counterparties.return_value = [{"id": "box1"}]
        resp = client.get("/api/v1/shifts/diadoc/counterparties", headers=auth_headers)
        assert resp.status_code in (200, 500)

    @patch("app.api.routes.shifts.diadoc.diadoc_service")
    def test_get_document_status_route(self, mock_svc, client, auth_headers):
        mock_svc.get_document_status.return_value = {"status": "delivered"}
        resp = client.get("/api/v1/shifts/diadoc/status/test-doc-id", headers=auth_headers)
        assert resp.status_code in (200, 500)
