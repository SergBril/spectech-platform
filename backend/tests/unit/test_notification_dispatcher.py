"""Unit-тесты для notification_dispatcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_dispatcher import (
    NotificationDispatcher,
    notification_dispatcher,
)


class TestNotificationDispatcher:
    """Тесты координатора уведомлений."""

    @pytest.mark.asyncio
    async def test_notify_rental_completed_sends_all_channels(self):
        """✅ Уведомление о завершении аренды отправляется по всем каналам."""
        with patch("app.services.notification_dispatcher.email_service") as mock_email, \
             patch("app.services.notification_dispatcher.telegram_service") as mock_tg, \
             patch("app.services.notification_dispatcher.create_notification", new_callable=AsyncMock) as mock_inapp:
            
            mock_email.send_rental_completed.return_value = True
            mock_tg.send_alert = AsyncMock(return_value=True)
            
            mock_rental = MagicMock()
            mock_rental.id = 1
            mock_rental.total_amount = 20000.00
            
            mock_invoice = MagicMock()
            mock_invoice.document_number = "INV-2026-0001"
            mock_invoice.due_date = MagicMock()
            mock_invoice.due_date.strftime.return_value = "01.11.2026"
            
            mock_db = MagicMock()
            
            results = await notification_dispatcher.notify_rental_completed(
                db=mock_db,
                rental=mock_rental,
                invoice=mock_invoice,
                client_email="client@test.com",
                client_name="Test Client",
                client_user_id=1,
            )
            
            assert results["email"] is True
            assert results["telegram"] is True
            assert results["in_app"] is True
            mock_email.send_rental_completed.assert_called_once()
            mock_tg.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_degradation_email_fails(self):
        """✅ При падении email остальные каналы продолжают работать."""
        with patch("app.services.notification_dispatcher.email_service") as mock_email, \
             patch("app.services.notification_dispatcher.telegram_service") as mock_tg, \
             patch("app.services.notification_dispatcher.create_notification", new_callable=AsyncMock) as mock_inapp:
            
            mock_email.send_rental_completed.side_effect = Exception("SMTP error")
            mock_tg.send_alert = AsyncMock(return_value=True)
            
            mock_rental = MagicMock()
            mock_rental.id = 1
            mock_rental.total_amount = 20000.00
            
            mock_invoice = MagicMock()
            mock_invoice.document_number = "INV-2026-0001"
            mock_invoice.due_date = MagicMock()
            mock_invoice.due_date.strftime.return_value = "01.11.2026"
            
            results = await notification_dispatcher.notify_rental_completed(
                db=MagicMock(),
                rental=mock_rental,
                invoice=mock_invoice,
                client_email="client@test.com",
                client_name="Test Client",
                client_user_id=None,
            )
            
            assert results["email"] is False
            assert results["telegram"] is True

    @pytest.mark.asyncio
    async def test_graceful_degradation_telegram_unavailable(self):
        """✅ При недоступности Telegram email продолжает работать."""
        with patch("app.services.notification_dispatcher.email_service") as mock_email, \
             patch("app.services.notification_dispatcher.telegram_service") as mock_tg:
            
            mock_email.send_rental_completed.return_value = True
            mock_tg.send_alert = AsyncMock(return_value=False)  # Telegram unavailable
            
            mock_rental = MagicMock()
            mock_rental.id = 1
            mock_rental.total_amount = 20000.00
            
            mock_invoice = MagicMock()
            mock_invoice.document_number = "INV-2026-0001"
            mock_invoice.due_date = MagicMock()
            mock_invoice.due_date.strftime.return_value = "01.11.2026"
            
            results = await notification_dispatcher.notify_rental_completed(
                db=MagicMock(),
                rental=mock_rental,
                invoice=mock_invoice,
                client_email="client@test.com",
                client_name="Test Client",
            )
            
            assert results["email"] is True
            assert results["telegram"] is False

    @pytest.mark.asyncio
    async def test_notify_dispute_opened(self):
        """✅ Уведомление о новом споре."""
        with patch("app.services.notification_dispatcher.email_service") as mock_email, \
             patch("app.services.notification_dispatcher.telegram_service") as mock_tg:
            
            mock_email.send_dispute_opened.return_value = True
            mock_tg.send_dispute_alert = AsyncMock(return_value=True)
            
            mock_dispute = MagicMock()
            mock_dispute.id = 123
            mock_dispute.dispute_type.value = "hours"
            mock_dispute.initiator_role.value = "operator"
            
            results = await notification_dispatcher.notify_dispute_opened(
                db=MagicMock(),
                dispute=mock_dispute,
                dispatcher_email="dispatcher@test.com",
                dispatcher_name="Иван Диспетчер",
            )
            
            assert results["email"] is True
            assert results["telegram"] is True

    @pytest.mark.asyncio
    async def test_notify_dispute_escalated(self):
        """✅ Уведомление об эскалации."""
        with patch("app.services.notification_dispatcher.email_service") as mock_email, \
             patch("app.services.notification_dispatcher.telegram_service") as mock_tg:
            
            mock_email.send_dispute_escalated.return_value = True
            mock_tg.send_escalation_alert = AsyncMock(return_value=True)
            
            mock_dispute = MagicMock()
            mock_dispute.id = 123
            
            results = await notification_dispatcher.notify_dispute_escalated(
                db=MagicMock(),
                dispute=mock_dispute,
                manager_email="manager@test.com",
                manager_name="Петр Менеджер",
                from_role="dispatcher",
                to_role="manager",
            )
            
            assert results["email"] is True
            assert results["telegram"] is True

    @pytest.mark.asyncio
    async def test_notify_payout_created(self):
        """✅ Уведомление собственнику о выплате."""
        with patch("app.services.notification_dispatcher.email_service") as mock_email, \
             patch("app.services.notification_dispatcher.telegram_service") as mock_tg:
            
            mock_email.send_payout_created.return_value = True
            mock_tg.send_alert = AsyncMock(return_value=True)
            
            mock_payout = MagicMock()
            mock_payout.document_number = "PAY-2026-0001"
            mock_payout.gross_amount = 20000.00
            mock_payout.platform_commission = 2000.00
            mock_payout.net_amount = 18000.00
            
            results = await notification_dispatcher.notify_payout_created(
                db=MagicMock(),
                payout=mock_payout,
                owner_email="owner@test.com",
                owner_name="Собственник Техники",
            )
            
            assert results["email"] is True
            assert results["telegram"] is True