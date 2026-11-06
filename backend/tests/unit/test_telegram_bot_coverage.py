"""Coverage tests for telegram_bot."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=12345, first_name="Test", full_name="Test User")
    update.message = AsyncMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = ""
    return update


@pytest.fixture
def mock_context():
    return MagicMock()


@pytest.fixture
def service():
    from app.services.telegram_bot import TelegramBotService
    return TelegramBotService()


class TestStart:
    """Cover start (lines 37-78)."""

    @pytest.mark.asyncio
    async def test_linked_user(self, service, mock_update, mock_context):
        user = SimpleNamespace(id=1, full_name="Ivan", company_id=7)
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = user
            await service.start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        db.close.assert_called()

    @pytest.mark.asyncio
    async def test_unlinked_user(self, service, mock_update, mock_context):
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            await service.start(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        assert "link_account" in mock_update.message.reply_text.call_args[0][0]


class TestLinkAccount:
    """Cover link_account (lines 80-91)."""

    @pytest.mark.asyncio
    async def test_returns_awaiting_code(self, service, mock_update, mock_context):
        from app.services.telegram_bot import AWAITING_CODE
        result = await service.link_account(mock_update, mock_context)
        assert result == AWAITING_CODE
        mock_update.message.reply_text.assert_called_once()


class TestHandleLinkCode:
    """Cover handle_link_code (lines 93-134)."""

    @pytest.mark.asyncio
    async def test_invalid_code(self, service, mock_update, mock_context):
        from app.services.telegram_bot import AWAITING_CODE
        mock_update.message.text = "bad_code"
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            result = await service.handle_link_code(mock_update, mock_context)
        assert result == AWAITING_CODE

    @pytest.mark.asyncio
    async def test_valid_code(self, service, mock_update, mock_context):
        from telegram.ext import ConversationHandler
        mock_update.message.text = "ABC123"
        user = SimpleNamespace(id=1, telegram_id=None, telegram_link_code="ABC123")
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = user
            result = await service.handle_link_code(mock_update, mock_context)
        assert result == ConversationHandler.END
        assert user.telegram_id == 12345
        db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_exception_handling(self, service, mock_update, mock_context):
        from telegram.ext import ConversationHandler
        mock_update.message.text = "CODE"
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.side_effect = Exception("DB error")
            result = await service.handle_link_code(mock_update, mock_context)
        assert result == ConversationHandler.END


class TestCancel:
    """Cover cancel (lines 136-139)."""

    @pytest.mark.asyncio
    async def test_cancel(self, service, mock_update, mock_context):
        from telegram.ext import ConversationHandler
        result = await service.cancel(mock_update, mock_context)
        assert result == ConversationHandler.END


class TestMyRentals:
    """Cover my_rentals (lines 141-193)."""

    @pytest.mark.asyncio
    async def test_not_linked(self, service, mock_update, mock_context):
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            await service.my_rentals(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_rentals(self, service, mock_update, mock_context):
        user = SimpleNamespace(id=1, company_id=7)
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            # First query: find user; Second query: rentals
            db.query.side_effect = [
                MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))),
                MagicMock(filter=MagicMock(return_value=MagicMock(order_by=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))))),
            ]
            await service.my_rentals(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called()

    @pytest.mark.asyncio
    async def test_with_rentals(self, service, mock_update, mock_context):
        from datetime import date
        from app.models.rental import RentalStatus
        user = SimpleNamespace(id=1, company_id=7)
        rental = SimpleNamespace(
            id=1, status=RentalStatus.ACTIVE,
            start_date=date(2026, 11, 1), end_date=date(2026, 11, 30),
            total_amount=50000.0,
        )
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.side_effect = [
                MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))),
                MagicMock(filter=MagicMock(return_value=MagicMock(order_by=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[rental])))))))),
            ]
            await service.my_rentals(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called()


class TestMyVehicles:
    """Cover my_vehicles (lines 195-252)."""

    @pytest.mark.asyncio
    async def test_not_linked(self, service, mock_update, mock_context):
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            await service.my_vehicles(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_vehicles(self, service, mock_update, mock_context):
        user = SimpleNamespace(id=1, company_id=7)
        vehicle = SimpleNamespace(
            name="KAMAZ", status="free", is_available_for_rent=True, hourly_rate=1500.0,
        )
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.side_effect = [
                MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))),
                MagicMock(filter=MagicMock(return_value=MagicMock(order_by=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[vehicle])))))))),
            ]
            await service.my_vehicles(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called()


class TestNewRequests:
    """Cover new_requests (lines 254-319)."""

    @pytest.mark.asyncio
    async def test_not_linked(self, service, mock_update, mock_context):
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            await service.new_requests(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_requests(self, service, mock_update, mock_context):
        user = SimpleNamespace(id=1, company_id=7)
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.side_effect = [
                MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))),
                MagicMock(filter=MagicMock(return_value=MagicMock(order_by=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))))),
            ]
            await service.new_requests(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called()

    @pytest.mark.asyncio
    async def test_with_requests(self, service, mock_update, mock_context):
        from datetime import UTC, datetime
        user = SimpleNamespace(id=1, company_id=7)
        req = SimpleNamespace(
            id=42, work_type="earthworks",
            planned_start=datetime(2026, 11, 10, 8, 0, tzinfo=UTC),
        )
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.side_effect = [
                MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=user)))),
                MagicMock(filter=MagicMock(return_value=MagicMock(order_by=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[req])))))))),
            ]
            await service.new_requests(mock_update, mock_context)
        mock_update.callback_query.edit_message_text.assert_called()


class TestHandleCallback:
    """Cover handle_callback (lines 321-339)."""

    @pytest.mark.asyncio
    async def test_my_rentals(self, service, mock_update, mock_context):
        mock_update.callback_query.data = "my_rentals"
        with patch.object(service, "my_rentals", new_callable=AsyncMock) as m:
            await service.handle_callback(mock_update, mock_context)
        m.assert_called_once()

    @pytest.mark.asyncio
    async def test_accept_request(self, service, mock_update, mock_context):
        mock_update.callback_query.data = "accept_request_42"
        with patch.object(service, "_accept_request", new_callable=AsyncMock) as m:
            await service.handle_callback(mock_update, mock_context)
        m.assert_called_once_with(mock_update, 42)

    @pytest.mark.asyncio
    async def test_reject_request(self, service, mock_update, mock_context):
        mock_update.callback_query.data = "reject_request_42"
        with patch.object(service, "_reject_request", new_callable=AsyncMock) as m:
            await service.handle_callback(mock_update, mock_context)
        m.assert_called_once_with(mock_update, 42)


class TestAcceptRejectRequest:
    """Cover _accept_request and _reject_request (lines 341-378)."""

    @pytest.mark.asyncio
    async def test_accept(self, service, mock_update, mock_context):
        req = SimpleNamespace(id=1, status="new")
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.get.return_value = req
            await service._accept_request(mock_update, 1)
        assert req.status.value == "assigned" or req.status == "assigned"
        db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_reject(self, service, mock_update, mock_context):
        req = SimpleNamespace(id=1, status="new")
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.get.return_value = req
            await service._reject_request(mock_update, 1)
        db.commit.assert_called()


class TestFindUserByTelegram:
    """Cover _find_user_by_telegram (lines 380-382)."""

    def test_found(self, service):
        db = MagicMock()
        user = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.first.return_value = user
        result = service._find_user_by_telegram(db, 12345)
        assert result == user

    def test_not_found(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = service._find_user_by_telegram(db, 12345)
        assert result is None


class TestRunBot:
    """Cover run_bot (lines 384-end)."""

    def test_no_token(self, service):
        import app.services.telegram_bot as mod
        original_token = mod.settings.TELEGRAM_BOT_TOKEN
        mod.settings.TELEGRAM_BOT_TOKEN = ""
        try:
            service.run_bot()
        finally:
            mod.settings.TELEGRAM_BOT_TOKEN = original_token
        assert service.application is None

    def test_with_token_no_proxy(self, service):
        import app.services.telegram_bot as mod
        original_token = mod.settings.TELEGRAM_BOT_TOKEN
        original_proxy = mod.settings.TELEGRAM_PROXY_URL
        mod.settings.TELEGRAM_BOT_TOKEN = "test_token"
        mod.settings.TELEGRAM_PROXY_URL = ""

        mock_app = MagicMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app.run_polling.side_effect = lambda **kw: None

        try:
            with patch.object(mod, "Application") as MockApp, \
                 patch.dict("os.environ", {}, clear=True):
                MockApp.builder.return_value = mock_builder
                service.run_bot()
        finally:
            mod.settings.TELEGRAM_BOT_TOKEN = original_token
            mod.settings.TELEGRAM_PROXY_URL = original_proxy
        assert service.application == mock_app

    def test_proxy_error_returns_early(self, service):
        import app.services.telegram_bot as mod
        original_token = mod.settings.TELEGRAM_BOT_TOKEN
        original_proxy = mod.settings.TELEGRAM_PROXY_URL
        mod.settings.TELEGRAM_BOT_TOKEN = "test_token"
        mod.settings.TELEGRAM_PROXY_URL = "socks5://proxy:1080"

        try:
            service.run_bot()
        finally:
            mod.settings.TELEGRAM_BOT_TOKEN = original_token
            mod.settings.TELEGRAM_PROXY_URL = original_proxy
        assert service.application is None


class TestGlobalSingleton:
    def test_exists(self):
        from app.services.telegram_bot import telegram_bot_service
        assert telegram_bot_service is not None



class TestHandleCallbackStartMenu:
    """Cover handle_callback start_menu branch (lines 223-227 area)."""

    @pytest.mark.asyncio
    async def test_start_menu(self, service, mock_update, mock_context):
        mock_update.callback_query.data = "start_menu"
        with patch.object(service, "start", new_callable=AsyncMock) as m:
            await service.handle_callback(mock_update, mock_context)
        m.assert_called_once()

    @pytest.mark.asyncio
    async def test_my_vehicles_callback(self, service, mock_update, mock_context):
        mock_update.callback_query.data = "my_vehicles"
        with patch.object(service, "my_vehicles", new_callable=AsyncMock) as m:
            await service.handle_callback(mock_update, mock_context)
        m.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_requests_callback(self, service, mock_update, mock_context):
        mock_update.callback_query.data = "new_requests"
        with patch.object(service, "new_requests", new_callable=AsyncMock) as m:
            await service.handle_callback(mock_update, mock_context)
        m.assert_called_once()


class TestAcceptRejectNotFound:
    """Cover _accept/_reject when request not found (lines 329, 331, 333)."""

    @pytest.mark.asyncio
    async def test_accept_not_found(self, service, mock_update, mock_context):
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.get.return_value = None
            await service._accept_request(mock_update, 999)
        db.close.assert_called()

    @pytest.mark.asyncio
    async def test_reject_not_found(self, service, mock_update, mock_context):
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.get.return_value = None
            await service._reject_request(mock_update, 999)
        db.close.assert_called()



class TestMyVehiclesEmpty:
    """Cover my_vehicles empty list branch (lines 223-227)."""

    @pytest.mark.asyncio
    async def test_no_vehicles(self, service, mock_update, mock_context):
        user = SimpleNamespace(id=1, company_id=7)
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            # First query returns user, second returns empty vehicles
            user_query = MagicMock()
            user_query.filter.return_value.first.return_value = user
            vehicles_query = MagicMock()
            vehicles_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            db.query.side_effect = [user_query, vehicles_query]
            await service.my_vehicles(mock_update, mock_context)
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "нет техники" in call_args.lower() or "РЈ РІР°СЃ РЅРµС‚" in call_args


class TestRunBotWithProxySuccess:
    """Cover run_bot proxy success path (line 409)."""

    def test_proxy_success(self, service):
        import app.services.telegram_bot as mod
        original_token = mod.settings.TELEGRAM_BOT_TOKEN
        original_proxy = mod.settings.TELEGRAM_PROXY_URL
        mod.settings.TELEGRAM_BOT_TOKEN = "test_token"
        mod.settings.TELEGRAM_PROXY_URL = "http://proxy:8080"

        mock_app = MagicMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.request.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app.run_polling.side_effect = lambda **kw: None

        try:
            with patch.object(mod, "Application") as MockApp:
                MockApp.builder.return_value = mock_builder
                service.run_bot()
        finally:
            mod.settings.TELEGRAM_BOT_TOKEN = original_token
            mod.settings.TELEGRAM_PROXY_URL = original_proxy
        assert service.application == mock_app
        mock_builder.request.assert_called_once()
