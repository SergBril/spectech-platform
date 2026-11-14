"""Срок действия кода привязки чата (Telegram/MAX).

Код - единственный секрет для захвата аккаунта, поэтому он ограничен по
времени. Коды без срока (выданные до этой правки) недействительны: они были
вечными, и это осознанный fail-closed.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import (
    LINK_CODE_TTL_MINUTES,
    link_code_expiry,
    link_code_is_valid,
)
from app.services.telegram_bot import telegram_bot_service


class TestLinkCodeValidity:
    def test_fresh_code_is_valid(self):
        assert link_code_is_valid(link_code_expiry()) is True

    def test_expired_code_is_invalid(self):
        assert link_code_is_valid(datetime.now(UTC) - timedelta(seconds=1)) is False

    def test_legacy_code_without_expiry_is_invalid(self):
        assert link_code_is_valid(None) is False

    def test_naive_datetime_is_treated_as_utc(self):
        assert (
            link_code_is_valid(
                datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5)
            )
            is True
        )
        assert (
            link_code_is_valid(
                datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
            )
            is False
        )

    def test_iso_string_is_accepted(self):
        assert link_code_is_valid(link_code_expiry().isoformat()) is True
        assert link_code_is_valid("not-a-date") is False

    def test_ttl_is_one_hour(self):
        assert LINK_CODE_TTL_MINUTES == 60
        delta = link_code_expiry() - datetime.now(UTC)
        assert timedelta(minutes=59) < delta <= timedelta(minutes=60)


class TestTelegramHandlerEnforcesExpiry:
    def _update(self, code):
        u = MagicMock()
        u.effective_user = SimpleNamespace(id=12345)
        u.message = AsyncMock()
        u.message.text = code
        return u

    @pytest.mark.asyncio
    async def test_expired_code_does_not_link(self):
        user = SimpleNamespace(
            id=1,
            telegram_id=None,
            telegram_link_code="EXP",
            telegram_link_code_expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = user
            await telegram_bot_service.handle_link_code(
                self._update("EXP"), MagicMock()
            )
        assert (
            user.telegram_id is None
        ), "просроченный код не должен привязывать аккаунт"
        assert user.telegram_link_code == "EXP", "код не должен гаситься при отказе"
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_code_without_expiry_does_not_link(self):
        user = SimpleNamespace(
            id=1,
            telegram_id=None,
            telegram_link_code="OLD",
            telegram_link_code_expires_at=None,
        )
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = user
            await telegram_bot_service.handle_link_code(
                self._update("OLD"), MagicMock()
            )
        assert user.telegram_id is None
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_fresh_code_links(self):
        user = SimpleNamespace(
            id=1,
            telegram_id=None,
            telegram_link_code="OK",
            telegram_link_code_expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        with patch("app.services.telegram_bot.SessionLocal") as MockDB:
            db = MagicMock()
            MockDB.return_value = db
            db.query.return_value.filter.return_value.first.return_value = user
            await telegram_bot_service.handle_link_code(self._update("OK"), MagicMock())
        assert user.telegram_id == 12345
        assert user.telegram_link_code is None
        db.commit.assert_called()
