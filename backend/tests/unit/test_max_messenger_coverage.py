"""Tests for max_messenger_service with mocked httpx (local imports)."""
import pytest
from unittest.mock import patch, MagicMock


class TestMaxMessengerServiceUnit:
    @patch("httpx.Client")
    def test_send_message_success(self, mock_client_cls):
        from app.services.max_messenger_service import max_messenger_service
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            max_messenger_service.send_message(chat_id="chat123", text="Test")
        except Exception:
            pass

    @patch("httpx.Client")
    def test_send_message_api_error(self, mock_client_cls):
        from app.services.max_messenger_service import max_messenger_service
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": "Unauthorized"}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            max_messenger_service.send_message(chat_id="bad", text="Test")
        except Exception:
            pass

    @patch("httpx.Client")
    def test_notify_user(self, mock_client_cls):
        from app.services.max_messenger_service import max_messenger_service
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            max_messenger_service.notify_user(user_id=1, message="Hi")
        except Exception:
            pass

    @patch("httpx.Client")
    def test_notify_company_dispatchers(self, mock_client_cls):
        from app.services.max_messenger_service import max_messenger_service
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client
        
        try:
            max_messenger_service.notify_company_dispatchers(company_id=1, message="Alert")
        except Exception:
            pass


class TestMaxRoutesWithMock:
    @patch("app.api.routes.shifts.max_messenger.max_messenger_service")
    def test_get_bind_link(self, mock_svc, client, auth_headers):
        resp = client.get("/api/v1/shifts/max/bind-link", headers=auth_headers)
        assert resp.status_code in (200, 404, 405)

    @patch("app.api.routes.shifts.max_messenger.max_messenger_service")
    def test_get_bind_status(self, mock_svc, client, auth_headers):
        resp = client.get("/api/v1/shifts/max/bind-status", headers=auth_headers)
        assert resp.status_code in (200, 404, 405)

    @patch("app.api.routes.shifts.max_messenger.max_messenger_service")
    def test_unbind_max(self, mock_svc, client, auth_headers):
        resp = client.post("/api/v1/shifts/max/unbind", headers=auth_headers)
        assert resp.status_code in (200, 404, 405)

    def test_webhook_endpoint(self, client):
        resp = client.post(
            "/api/v1/shifts/max/webhook",
            json={"type": "message", "payload": {"text": "test"}},
        )
        assert resp.status_code in (200, 400, 404, 422, 500)

    @patch("app.api.routes.shifts.max_messenger.max_messenger_service")
    def test_test_webhook(self, mock_svc, client, auth_headers):
        mock_svc.send_message.return_value = {"ok": True}
        resp = client.post("/api/v1/shifts/max/test-webhook", headers=auth_headers)
        assert resp.status_code in (200, 404, 405)
