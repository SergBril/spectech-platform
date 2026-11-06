"""Coverage tests for max_messenger_service."""
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Mock UserCompany if not in auth module
_auth_mod = sys.modules.get("app.models.auth")
if _auth_mod and not hasattr(_auth_mod, "UserCompany"):
    class _MockUserCompany:
        user_id = MagicMock()
        company_id = MagicMock()
    _auth_mod.UserCompany = _MockUserCompany


from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def service():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.MAX_BOT_TOKEN = "test_token"
        from app.services.max_messenger_service import MaxMessengerService
        svc = MaxMessengerService()
    return svc


@pytest.fixture
def disabled_service():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.MAX_BOT_TOKEN = ""
        from app.services.max_messenger_service import MaxMessengerService
        svc = MaxMessengerService()
    return svc


class TestInit:
    """Cover __init__ (lines 20-24)."""

    def test_enabled_with_token(self, service):
        assert service.enabled is True

    def test_disabled_without_token(self, disabled_service):
        assert disabled_service.enabled is False


class TestSendMessage:
    """Cover send_message (lines 26-65)."""

    @pytest.mark.asyncio
    async def test_stub_when_disabled(self, disabled_service):
        result = await disabled_service.send_message("chat1", "Hello")
        assert result["status"] == "stub"
        assert result["chat_id"] == "chat1"

    @pytest.mark.asyncio
    async def test_success(self, service):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "msg_123"}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_message("chat1", "Hello")
        assert result["status"] == "sent"
        assert result["message_id"] == "msg_123"

    @pytest.mark.asyncio
    async def test_error_returns_error(self, service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Network fail")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.send_message("chat1", "Hello")
        assert result["status"] == "error"
        assert "Network fail" in result["error"]


class TestNotifyUser:
    """Cover notify_user (lines 67-86)."""

    @pytest.mark.asyncio
    async def test_user_not_found(self, service):
        db = MagicMock()
        db.get.return_value = None
        result = await service.notify_user(db, 999, "Title", "Body")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_no_max_chat_id(self, service):
        db = MagicMock()
        user = SimpleNamespace(id=1, max_chat_id=None)
        db.get.return_value = user
        result = await service.notify_user(db, 1, "Title", "Body")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_sends_message(self, service):
        db = MagicMock()
        user = SimpleNamespace(id=1, max_chat_id="chat_42")
        db.get.return_value = user
        with patch.object(service, "send_message", new_callable=AsyncMock, return_value={"status": "sent"}) as mock:
            result = await service.notify_user(db, 1, "Title", "Body")
        assert result["status"] == "sent"
        mock.assert_called_once()
        text = mock.call_args[0][1]
        assert "Title" in text


class TestNotifyCompanyDispatchers:
    """Cover notify_company_dispatchers (lines 88-115)."""

    @pytest.mark.asyncio
    async def test_notifies_all(self, service):
        db = MagicMock()
        # Mock the entire select+execute chain to avoid SQLAlchemy issues with mock UserCompany
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [1, 2, 3]
        db.execute.return_value = mock_result
        with patch.object(service, "notify_user", new_callable=AsyncMock, return_value={"status": "sent"}) as mock_notify:
            # Patch select to return something SQLAlchemy won't reject
            with patch("app.services.max_messenger_service.select", return_value=MagicMock()):
                results = await service.notify_company_dispatchers(db, 7, "Alert", "Body")
        assert len(results) == 3
        assert mock_notify.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_dispatchers(self, service):
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result
        with patch("app.services.max_messenger_service.select", return_value=MagicMock()):
            results = await service.notify_company_dispatchers(db, 7, "Alert", "Body")
        assert results == []


class TestMaxNotificationTemplates:
    """Cover all template methods (lines 120-240)."""

    def test_request_created(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.request_created(1, "Earthworks", "Moscow", "2026-11-07")
        assert "#1" in body
        assert "Earthworks" in body

    def test_offer_received(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.offer_received(1, "OOO Test", 50000.0, "KAMAZ")
        assert "50,000" in body
        assert "KAMAZ" in body

    def test_payment_received(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.payment_received("INV-001", 100000.0, "Payer")
        assert "100,000" in body

    def test_shift_completed(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.shift_completed(42, "Excavator", "2026-11-06", 8.5)
        assert "8.5" in body

    def test_salary_approved(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.salary_approved(1, "Ivanov", 87000.0, "Nov 2026")
        assert "87,000" in body

    def test_geofence_alert_enter(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.geofence_alert("KAMAZ", "Site A", "enter", "12:00")
        assert "🟢" in title

    def test_geofence_alert_exit(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.geofence_alert("KAMAZ", "Site A", "exit", "12:00")
        assert "🔴" in title

    def test_maintenance_due(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.maintenance_due("KAMAZ", 500.0, 480.0, 20.0)
        assert "500" in body

    def test_engine_hours_warning(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.engine_hours_warning("KAMAZ", 12.5, 10.0)
        assert "12.5" in body

    def test_sync_error(self):
        from app.services.max_messenger_service import MaxNotificationTemplates
        title, body = MaxNotificationTemplates.sync_error("Wialon", "Timeout", 5)
        assert "Wialon" in body
        assert "5" in body


class TestGlobalSingletons:
    def test_templates_exist(self):
        from app.services.max_messenger_service import notification_templates
        assert notification_templates is not None

    def test_service_exists(self):
        from app.services.max_messenger_service import max_messenger_service
        assert max_messenger_service is not None
