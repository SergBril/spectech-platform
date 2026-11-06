"""Coverage tests for fcm_service."""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


import types as _types


@pytest.fixture(autouse=True)
def mock_firebase():
    """Mock firebase_admin module before any test imports it."""
    mock_fb = MagicMock()
    mock_creds = MagicMock()
    # Use real types.ModuleType so 'from firebase_admin import messaging' works
    mock_messaging = _types.ModuleType("firebase_admin.messaging")
    mock_messaging.MulticastMessage = MagicMock()
    mock_messaging.Notification = MagicMock()
    mock_messaging.send_each_for_multicast = MagicMock()

    mock_fb.credentials = mock_creds
    mock_fb.messaging = mock_messaging  # Critical: 'from firebase_admin import messaging' uses this
    mock_fb.initialize_app = MagicMock(return_value=MagicMock())

    originals = {}
    for mod_name in ["firebase_admin", "firebase_admin.credentials", "firebase_admin.messaging"]:
        originals[mod_name] = sys.modules.get(mod_name)

    sys.modules["firebase_admin"] = mock_fb
    sys.modules["firebase_admin.credentials"] = mock_creds
    sys.modules["firebase_admin.messaging"] = mock_messaging

    yield {"fb": mock_fb, "creds": mock_creds, "messaging": mock_messaging}

    for mod_name, orig in originals.items():
        if orig is not None:
            sys.modules[mod_name] = orig
        elif mod_name in sys.modules:
            del sys.modules[mod_name]


class TestFCMServiceInit:
    """Cover __init__ (lines 14-19)."""

    def test_enabled_with_path(self):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/path/to/creds.json"
            svc = FCMService()
            assert svc.enabled is True

    def test_disabled_without_path(self):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = ""
            svc = FCMService()
            assert svc.enabled is False


class TestGetApp:
    """Cover _get_app (lines 21-35)."""

    def test_returns_none_when_disabled(self):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = ""
            svc = FCMService()
        assert svc._get_app() is None

    def test_initializes_firebase(self, mock_firebase):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/path/to/creds.json"
            svc = FCMService()

        mock_app = MagicMock()
        mock_firebase["fb"].initialize_app.return_value = mock_app
        result = svc._get_app()
        assert result == mock_app
        assert svc._app == mock_app

    def test_returns_cached_app(self):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/path/to/creds.json"
            svc = FCMService()
        svc._app = MagicMock()
        result = svc._get_app()
        assert result == svc._app

    def test_init_failure_disables(self, mock_firebase):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/bad/path.json"
            svc = FCMService()

        mock_firebase["creds"].Certificate.side_effect = Exception("File not found")
        result = svc._get_app()
        assert result is None
        assert svc.enabled is False


class TestSendToUser:
    """Cover send_to_user (lines 37-end)."""

    @pytest.mark.asyncio
    async def test_stub_when_disabled(self):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = ""
            svc = FCMService()
        result = await svc.send_to_user(1, "Title", "Body")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_tokens_returns_false(self):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
            svc = FCMService()
        svc._app = MagicMock()

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        result = await svc.send_to_user(1, "Title", "Body", db=mock_db)
        assert result is False

    @pytest.mark.asyncio
    async def test_success_with_tokens(self, mock_firebase):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
            svc = FCMService()
        svc._app = MagicMock()

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = ["token1", "token2"]

        from types import SimpleNamespace
        mock_response = SimpleNamespace(success_count=2, failure_count=0)
        mock_firebase["messaging"].send_each_for_multicast.return_value = mock_response

        result = await svc.send_to_user(1, "Title", "Body", data={"key": "val"}, db=mock_db)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_error_returns_false(self, mock_firebase):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
            svc = FCMService()
        svc._app = MagicMock()

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = ["token1"]

        mock_firebase["messaging"].send_each_for_multicast.side_effect = Exception("FCM error")

        result = await svc.send_to_user(1, "Title", "Body", db=mock_db)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_db_no_tokens(self):
        from app.services.fcm_service import FCMService
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
            svc = FCMService()
        svc._app = MagicMock()
        result = await svc.send_to_user(1, "Title", "Body")
        assert result is False


class TestGlobalSingleton:
    """Cover global fcm_service instance."""

    def test_singleton_exists(self):
        from app.services.fcm_service import fcm_service
        assert fcm_service is not None
