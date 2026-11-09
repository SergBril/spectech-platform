"""Coverage push for notification_dispatcher -> 95%+."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_dispatcher import NotificationDispatcher


@pytest.fixture
def mock_db():
    return MagicMock()


def _rental():
    return SimpleNamespace(id=1, total_amount=5000.0)


def _invoice():
    from datetime import date
    return SimpleNamespace(document_number="INV-001", due_date=date(2026, 12, 1))


def _payout():
    return SimpleNamespace(
        document_number="PAY-001", gross_amount=10000.0,
        platform_commission=1000.0, net_amount=9000.0,
    )


def _dispute():
    return SimpleNamespace(
        id=1,
        dispute_type=SimpleNamespace(value="damage"),
        initiator_role=SimpleNamespace(value="client"),
    )


class TestRunAsync:
    """Cover line 30: asyncio.create_task path."""

    def test_create_task_in_event_loop(self):
        async def dummy():
            return 42

        async def run_test():
            result = NotificationDispatcher._run_async(dummy())
            assert isinstance(result, asyncio.Task)
            await result

        asyncio.run(run_test())


class TestNotifyRentalCompletedExceptions:
    """Cover except blocks: lines 73-74, 87-88, 101-102."""

    @pytest.mark.asyncio
    async def test_all_channels_fail(self, mock_db):
        rental = _rental()
        invoice = _invoice()

        with patch("app.services.notification_dispatcher.email_service") as es:
            es.send_rental_completed.side_effect = RuntimeError("email fail")
            with patch("app.services.notification_dispatcher.telegram_service") as ts:
                ts.send_alert = AsyncMock(side_effect=RuntimeError("tg fail"))
                with patch("app.services.notification_dispatcher.max_service") as ms:
                    ms.send_alert = AsyncMock(side_effect=RuntimeError("max fail"))
                    with patch("app.services.notification_dispatcher.create_notification",
                               new_callable=AsyncMock, side_effect=RuntimeError("inapp fail")):
                        result = await NotificationDispatcher.notify_rental_completed(
                            mock_db, rental, invoice, "test@test.com", "Test", 1,
                        )
        assert result == {"email": False, "telegram": False, "max": False, "in_app": False}


class TestNotifyPayoutCreatedExceptions:
    """Cover except blocks: lines 121-122, 134-135, 147-148, 160-161."""

    @pytest.mark.asyncio
    async def test_all_channels_fail(self, mock_db):
        payout = _payout()

        with patch("app.services.notification_dispatcher.email_service") as es:
            es.send_payout_created.side_effect = RuntimeError("email fail")
            with patch("app.services.notification_dispatcher.telegram_service") as ts:
                ts.send_alert = AsyncMock(side_effect=RuntimeError("tg fail"))
                with patch("app.services.notification_dispatcher.max_service") as ms:
                    ms.send_alert = AsyncMock(side_effect=RuntimeError("max fail"))
                    with patch("app.services.notification_dispatcher.create_notification",
                               new_callable=AsyncMock, side_effect=RuntimeError("inapp fail")):
                        result = await NotificationDispatcher.notify_payout_created(
                            mock_db, payout, "owner@test.com", "Owner", 1,
                        )
        assert result == {"email": False, "telegram": False, "max": False, "in_app": False}


class TestNotifyDisputeOpenedExceptions:
    """Cover except blocks: lines 180-181, 189-190, 198-199, 211-212."""

    @pytest.mark.asyncio
    async def test_all_channels_fail(self, mock_db):
        dispute = _dispute()

        with patch("app.services.notification_dispatcher.email_service") as es:
            es.send_dispute_opened.side_effect = RuntimeError("email fail")
            with patch("app.services.notification_dispatcher.telegram_service") as ts:
                ts.send_dispute_alert = AsyncMock(side_effect=RuntimeError("tg fail"))
                with patch("app.services.notification_dispatcher.max_service") as ms:
                    ms.send_dispute_alert = AsyncMock(side_effect=RuntimeError("max fail"))
                    with patch("app.services.notification_dispatcher.create_notification",
                               new_callable=AsyncMock, side_effect=RuntimeError("inapp fail")):
                        result = await NotificationDispatcher.notify_dispute_opened(
                            mock_db, dispute, "disp@test.com", "Dispatcher", 1,
                        )
        assert result == {"email": False, "telegram": False, "max": False, "in_app": False}
