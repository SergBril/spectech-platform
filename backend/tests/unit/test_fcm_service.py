from unittest.mock import MagicMock, patch

import pytest

from app.services.fcm_service import FCMService


@pytest.fixture
def mock_db():
    return MagicMock()


class TestFCMServiceInit:
    """Tests for FCMService initialization"""

    @patch("app.core.config.settings")
    def test_init_enabled(self, mock_settings):
        mock_settings.FCM_CREDENTIALS_PATH = "/path/to/creds.json"
        svc = FCMService()
        assert svc.enabled is True
        assert svc.credentials_path == "/path/to/creds.json"

    @patch("app.core.config.settings")
    def test_init_disabled_no_path(self, mock_settings):
        mock_settings.FCM_CREDENTIALS_PATH = ""
        svc = FCMService()
        assert svc.enabled is False

    @patch("app.core.config.settings")
    def test_init_disabled_missing_attr(self, mock_settings):
        del mock_settings.FCM_CREDENTIALS_PATH
        svc = FCMService()
        assert svc.enabled is False


class TestGetApp:
    """Tests for _get_app"""

    @patch("app.core.config.settings")
    def test_get_app_disabled(self, mock_settings):
        mock_settings.FCM_CREDENTIALS_PATH = ""
        svc = FCMService()
        assert svc._get_app() is None

    @patch("app.core.config.settings")
    def test_get_app_cached(self, mock_settings):
        mock_settings.FCM_CREDENTIALS_PATH = "/path/creds.json"
        svc = FCMService()
        mock_app = MagicMock()
        svc._app = mock_app
        assert svc._get_app() is mock_app

    @patch("app.core.config.settings")
    def test_get_app_init_failure(self, mock_settings):
        mock_settings.FCM_CREDENTIALS_PATH = "/bad/path.json"
        svc = FCMService()
        import sys

        mock_fb = MagicMock()
        mock_fb.initialize_app = MagicMock(side_effect=Exception("bad creds"))
        with patch.dict(
            sys.modules,
            {"firebase_admin": mock_fb, "firebase_admin.credentials": MagicMock()},
        ):
            result = svc._get_app()
        assert result is None
        assert svc.enabled is False


class TestSendToUser:
    """Tests for send_to_user"""

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_send_stub_mode(self, mock_settings):
        mock_settings.FCM_CREDENTIALS_PATH = ""
        svc = FCMService()
        result = await svc.send_to_user(user_id=5, title="Test", body="Body")
        assert result is True

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_send_no_tokens(self, mock_settings, mock_db):
        mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
        svc = FCMService()
        svc.enabled = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = MagicMock(return_value=mock_result)

        result = await svc.send_to_user(
            user_id=5, title="Test", body="Body", db=mock_db
        )
        assert result is False

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_send_success(self, mock_settings, mock_db):
        mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
        svc = FCMService()
        svc.enabled = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["token1", "token2"]
        mock_db.execute = MagicMock(return_value=mock_result)

        # Mock the entire firebase_admin.messaging module before it gets imported
        import sys

        mock_messaging = MagicMock()
        mock_response = MagicMock()
        mock_response.success_count = 2
        mock_messaging.send_each_for_multicast.return_value = mock_response
        mock_messaging.MulticastMessage = MagicMock()
        mock_messaging.Notification = MagicMock()

        # Pre-populate sys.modules so 'from firebase_admin import messaging' finds our mock
        mock_fb_admin = MagicMock()
        mock_fb_admin.messaging = mock_messaging
        with patch.dict(
            sys.modules,
            {
                "firebase_admin": mock_fb_admin,
                "firebase_admin.messaging": mock_messaging,
            },
        ):
            result = await svc.send_to_user(
                user_id=5, title="Test", body="Body", db=mock_db
            )

        assert result is True

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_send_firebase_error(self, mock_settings, mock_db):
        mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
        svc = FCMService()
        svc.enabled = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["token1"]
        mock_db.execute = MagicMock(return_value=mock_result)

        import sys

        mock_messaging = MagicMock()
        mock_messaging.send_each_for_multicast = MagicMock(
            side_effect=Exception("network error")
        )
        with patch.dict(
            sys.modules,
            {"firebase_admin": MagicMock(), "firebase_admin.messaging": mock_messaging},
        ):
            result = await svc.send_to_user(
                user_id=5, title="Test", body="Body", db=mock_db
            )

        assert result is False

    @pytest.mark.asyncio
    @patch("app.core.config.settings")
    async def test_send_no_db(self, mock_settings):
        mock_settings.FCM_CREDENTIALS_PATH = "/creds.json"
        svc = FCMService()
        svc.enabled = True

        # No db provided -> no tokens -> False
        result = await svc.send_to_user(user_id=5, title="Test", body="Body", db=None)
        assert result is False
