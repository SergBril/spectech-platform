"""Tests for NotificationDispatcher."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


class TestRunAsync:
    """Cover _run_async (lines 25-34)."""

    def test_no_event_loop(self):
        from app.services.notification_dispatcher import NotificationDispatcher

        async def dummy():
            return 42

        result = NotificationDispatcher._run_async(dummy())
        assert result == 42


class TestNotifyRentalCompleted:
    """Cover notify_rental_completed (lines 36-106)."""

    @pytest.mark.asyncio
    async def test_all_channels_success(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        rental = SimpleNamespace(id=1, total_amount=50000.0)
        invoice = SimpleNamespace(document_number="INV-001", due_date=MagicMock())
        invoice.due_date.strftime.return_value = "01.12.2026"

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ),
        ):

            mock_email.send_rental_completed.return_value = True
            mock_tg.send_alert = AsyncMock(return_value=True)
            mock_max.send_alert = AsyncMock(return_value=True)

            result = await NotificationDispatcher.notify_rental_completed(
                mock_db, rental, invoice, "client@test.com", "Client", client_user_id=5
            )

        assert result["email"] is True
        assert result["telegram"] is True
        assert result["max"] is True
        assert result["in_app"] is True

    @pytest.mark.asyncio
    async def test_email_fails_gracefully(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        rental = SimpleNamespace(id=1, total_amount=50000.0)
        invoice = SimpleNamespace(document_number="INV-001", due_date=MagicMock())
        invoice.due_date.strftime.return_value = "01.12.2026"

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ),
        ):

            mock_email.send_rental_completed.side_effect = Exception("SMTP error")
            mock_tg.send_alert = AsyncMock(return_value=True)
            mock_max.send_alert = AsyncMock(return_value=True)

            result = await NotificationDispatcher.notify_rental_completed(
                mock_db, rental, invoice, "client@test.com", "Client"
            )

        assert result["email"] is False
        assert result["telegram"] is True

    @pytest.mark.asyncio
    async def test_no_user_id_skips_in_app(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        rental = SimpleNamespace(id=1, total_amount=50000.0)
        invoice = SimpleNamespace(document_number="INV-001", due_date=MagicMock())
        invoice.due_date.strftime.return_value = "01.12.2026"

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ) as mock_notif,
        ):

            mock_email.send_rental_completed.return_value = True
            mock_tg.send_alert = AsyncMock(return_value=True)
            mock_max.send_alert = AsyncMock(return_value=True)

            result = await NotificationDispatcher.notify_rental_completed(
                mock_db,
                rental,
                invoice,
                "client@test.com",
                "Client",
                client_user_id=None,
            )

        assert result["in_app"] is False
        mock_notif.assert_not_called()


class TestNotifyPayoutCreated:
    """Cover notify_payout_created (lines 107-165)."""

    @pytest.mark.asyncio
    async def test_all_channels_success(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        payout = SimpleNamespace(
            document_number="ВЫП-2026-0001",
            gross_amount=100000.0,
            platform_commission=15000.0,
            net_amount=85000.0,
        )

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ),
        ):

            mock_email.send_payout_created.return_value = True
            mock_tg.send_alert = AsyncMock(return_value=True)
            mock_max.send_alert = AsyncMock(return_value=True)

            result = await NotificationDispatcher.notify_payout_created(
                mock_db, payout, "owner@test.com", "Owner", owner_user_id=10
            )

        assert all(result.values())

    @pytest.mark.asyncio
    async def test_all_channels_fail(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        payout = SimpleNamespace(
            document_number="ВЫП-2026-0001",
            gross_amount=100000.0,
            platform_commission=15000.0,
            net_amount=85000.0,
        )

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ) as mock_notif,
        ):

            mock_email.send_payout_created.side_effect = Exception("fail")
            mock_tg.send_alert = AsyncMock(side_effect=Exception("fail"))
            mock_max.send_alert = AsyncMock(side_effect=Exception("fail"))
            mock_notif.side_effect = Exception("fail")

            result = await NotificationDispatcher.notify_payout_created(
                mock_db, payout, "owner@test.com", "Owner", owner_user_id=10
            )

        assert all(v is False for v in result.values())


class TestNotifyDisputeOpened:
    """Cover notify_dispute_opened (lines 166-216)."""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        dispute = SimpleNamespace(
            id=42, dispute_type=MagicMock(), initiator_role=MagicMock()
        )
        dispute.dispute_type.value = "payment"
        dispute.initiator_role.value = "contractor"

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ),
        ):

            mock_email.send_dispute_opened.return_value = True
            mock_tg.send_dispute_alert = AsyncMock(return_value=True)
            mock_max.send_dispute_alert = AsyncMock(return_value=True)

            result = await NotificationDispatcher.notify_dispute_opened(
                mock_db, dispute, "disp@test.com", "Dispatcher", dispatcher_user_id=7
            )

        assert all(result.values())


class TestNotifyDisputeEscalated:
    """Cover notify_dispute_escalated (lines 217-end)."""

    @pytest.mark.asyncio
    async def test_success(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        dispute = SimpleNamespace(id=42)

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ),
        ):

            mock_email.send_dispute_escalated.return_value = True
            mock_tg.send_escalation_alert = AsyncMock(return_value=True)
            mock_max.send_escalation_alert = AsyncMock(return_value=True)

            result = await NotificationDispatcher.notify_dispute_escalated(
                mock_db,
                dispute,
                "mgr@test.com",
                "Manager",
                from_role="dispatcher",
                to_role="ceo",
                manager_user_id=3,
            )

        assert all(result.values())

    @pytest.mark.asyncio
    async def test_no_manager_user_id(self, mock_db):
        from app.services.notification_dispatcher import NotificationDispatcher

        dispute = SimpleNamespace(id=42)

        with (
            patch("app.services.notification_dispatcher.email_service") as mock_email,
            patch("app.services.notification_dispatcher.telegram_service") as mock_tg,
            patch("app.services.notification_dispatcher.max_service") as mock_max,
            patch(
                "app.services.notification_dispatcher.create_notification",
                new_callable=AsyncMock,
            ) as mock_notif,
        ):

            mock_email.send_dispute_escalated.return_value = True
            mock_tg.send_escalation_alert = AsyncMock(return_value=True)
            mock_max.send_escalation_alert = AsyncMock(return_value=True)

            result = await NotificationDispatcher.notify_dispute_escalated(
                mock_db,
                dispute,
                "mgr@test.com",
                "Manager",
                from_role="dispatcher",
                to_role="ceo",
                manager_user_id=None,
            )

        assert result["in_app"] is False
        mock_notif.assert_not_called()
