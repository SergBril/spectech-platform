"""Tests for TelegramBotService."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def bot_service():
    from app.services.telegram_bot import TelegramBotService

    return TelegramBotService()


def _make_update(telegram_id=12345, text=None, callback_data=None):
    """Helper to create mock Update object."""
    user = SimpleNamespace(id=telegram_id, first_name="Test", full_name="Test User")
    message = AsyncMock() if text else None
    if message:
        message.text = text
        message.reply_text = AsyncMock()

    callback_query = None
    if callback_data is not None:
        callback_query = AsyncMock()
        callback_query.data = callback_data
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()

    update = SimpleNamespace(
        effective_user=user,
        message=message,
        callback_query=callback_query,
    )
    return update


class TestStart:
    """Cover start command (lines 37-79)."""

    @pytest.mark.asyncio
    async def test_start_linked_user(self, bot_service):
        update = _make_update(text="/start")
        context = MagicMock()
        linked_user = SimpleNamespace(id=1, full_name="Иван Иванов")

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)

            with patch.object(
                bot_service, "_find_user_by_telegram", return_value=linked_user
            ):
                await bot_service.start(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "Иван Иванов" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_start_unlinked_user(self, bot_service):
        update = _make_update(text="/start")
        context = MagicMock()

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)

            with patch.object(bot_service, "_find_user_by_telegram", return_value=None):
                await bot_service.start(update, context)

        update.message.reply_text.assert_called_once()
        call_args = update.message.reply_text.call_args
        assert "link_account" in call_args[0][0]


class TestLinkAccount:
    """Cover link_account command (lines 80-92)."""

    @pytest.mark.asyncio
    async def test_link_account_prompt(self, bot_service):
        from app.services.telegram_bot import AWAITING_CODE

        update = _make_update(text="/link_account")
        context = MagicMock()

        result = await bot_service.link_account(update, context)
        assert result == AWAITING_CODE
        update.message.reply_text.assert_called_once()


class TestHandleLinkCode:
    """Cover handle_link_code (lines 93-135)."""

    @pytest.mark.asyncio
    async def test_invalid_code(self, bot_service):
        from app.services.telegram_bot import AWAITING_CODE

        update = _make_update(text="wrong_code")
        context = MagicMock()

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = None

            result = await bot_service.handle_link_code(update, context)

        assert result == AWAITING_CODE

    @pytest.mark.asyncio
    async def test_valid_code(self, bot_service):
        from telegram.ext import ConversationHandler

        update = _make_update(text="valid_code_123")
        context = MagicMock()
        user = SimpleNamespace(
            id=1,
            telegram_id=None,
            telegram_link_code="valid_code_123",
            telegram_link_code_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = user

            result = await bot_service.handle_link_code(update, context)

        assert result == ConversationHandler.END
        assert user.telegram_id == 12345
        assert user.telegram_link_code is None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_handling(self, bot_service):
        from telegram.ext import ConversationHandler

        update = _make_update(text="some_code")
        context = MagicMock()

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.query.side_effect = Exception("DB error")

            result = await bot_service.handle_link_code(update, context)

        assert result == ConversationHandler.END


class TestCancel:
    """Cover cancel command (lines 136-140)."""

    @pytest.mark.asyncio
    async def test_cancel(self, bot_service):
        from telegram.ext import ConversationHandler

        update = _make_update(text="/cancel")
        context = MagicMock()

        result = await bot_service.cancel(update, context)
        assert result == ConversationHandler.END


class TestMyRentals:
    """Cover my_rentals (lines 141-194)."""

    @pytest.mark.asyncio
    async def test_no_rentals(self, bot_service):
        update = _make_update(callback_data="my_rentals")
        context = MagicMock()
        user = SimpleNamespace(id=1, company_id=1)

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)

            with patch.object(bot_service, "_find_user_by_telegram", return_value=user):
                mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
                    []
                )
                await bot_service.my_rentals(update, context)

        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_unlinked_user(self, bot_service):
        update = _make_update(callback_data="my_rentals")
        context = MagicMock()

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)

            with patch.object(bot_service, "_find_user_by_telegram", return_value=None):
                await bot_service.my_rentals(update, context)

        update.callback_query.edit_message_text.assert_called_once()
        assert "link_account" in update.callback_query.edit_message_text.call_args[0][0]


class TestHandleCallback:
    """Cover handle_callback (lines 321-340)."""

    @pytest.mark.asyncio
    async def test_my_rentals_callback(self, bot_service):
        update = _make_update(callback_data="my_rentals")
        context = MagicMock()

        with patch.object(
            bot_service, "my_rentals", new_callable=AsyncMock
        ) as mock_method:
            await bot_service.handle_callback(update, context)
        mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_accept_request_callback(self, bot_service):
        update = _make_update(callback_data="accept_request_42")
        context = MagicMock()

        with patch.object(
            bot_service, "_accept_request", new_callable=AsyncMock
        ) as mock_method:
            await bot_service.handle_callback(update, context)
        mock_method.assert_called_once_with(update, 42)

    @pytest.mark.asyncio
    async def test_reject_request_callback(self, bot_service):
        update = _make_update(callback_data="reject_request_99")
        context = MagicMock()

        with patch.object(
            bot_service, "_reject_request", new_callable=AsyncMock
        ) as mock_method:
            await bot_service.handle_callback(update, context)
        mock_method.assert_called_once_with(update, 99)


class TestAcceptRejectRequest:
    """Cover _accept_request and _reject_request (lines 341-379)."""

    @pytest.mark.asyncio
    async def test_accept_request_success(self, bot_service):
        from app.models.dispatch import RequestStatus

        update = _make_update(callback_data="accept_request_1")
        request_obj = SimpleNamespace(id=1, status=RequestStatus.new)

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.get.return_value = request_obj

            await bot_service._accept_request(update, 1)

        assert request_obj.status == RequestStatus.assigned
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_request_success(self, bot_service):
        from app.models.dispatch import RequestStatus

        update = _make_update(callback_data="reject_request_1")
        request_obj = SimpleNamespace(id=1, status=RequestStatus.new)

        with patch("app.services.telegram_bot.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.get.return_value = request_obj

            await bot_service._reject_request(update, 1)

        assert request_obj.status == RequestStatus.cancelled
        mock_db.commit.assert_called_once()


class TestFindUserByTelegram:
    """Cover _find_user_by_telegram (lines 380-382)."""

    def test_found(self, bot_service):
        mock_db = MagicMock()
        user = SimpleNamespace(id=1, telegram_id=12345)
        mock_db.query.return_value.filter.return_value.first.return_value = user

        result = bot_service._find_user_by_telegram(mock_db, 12345)
        assert result == user

    def test_not_found(self, bot_service):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = bot_service._find_user_by_telegram(mock_db, 99999)
        assert result is None


class TestRunBot:
    """Cover run_bot (lines 384-end)."""

    def test_no_token(self, bot_service):
        with patch("app.services.telegram_bot.settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = None
            bot_service.run_bot()
        assert bot_service.application is None

    def test_with_token_no_proxy(self, bot_service):
        mock_app = MagicMock()
        mock_builder = MagicMock()
        mock_builder.build.return_value = mock_app

        with (
            patch("app.services.telegram_bot.settings") as mock_settings,
            patch("app.services.telegram_bot.Application") as MockApp,
            patch("app.services.telegram_bot.os.getenv", return_value=None),
            patch("app.services.telegram_bot.getattr", return_value=None),
        ):
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token"
            MockApp.builder.return_value = mock_builder
            mock_builder.token.return_value = mock_builder

            bot_service.run_bot()

        assert bot_service.application == mock_app
