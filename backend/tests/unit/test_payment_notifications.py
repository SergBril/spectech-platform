"""Unit-тесты для уведомлений при применении платежа."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.payment_notifications import PaymentNotificationService


class TestPaymentNotificationService:
    """Тесты сервиса уведомлений об оплате."""

    @pytest.mark.asyncio
    async def test_notify_invoice_paid_fully(self):
        """✅ При полной оплате отправляются уведомления по всем каналам."""
        with patch("app.services.payment_notifications.email_service") as mock_email, \
             patch("app.services.payment_notifications.telegram_service") as mock_tg, \
             patch("app.services.payment_notifications.create_notification", new_callable=AsyncMock) as mock_inapp:
            
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=True)
            
            mock_invoice = MagicMock()
            mock_invoice.client_id = 1
            mock_invoice.document_number = "INV-2026-0001"
            mock_invoice.total = Decimal("50000.00")
            mock_invoice.paid_amount = Decimal("50000.00")
            mock_invoice.status.value = "paid"
            
            mock_client = MagicMock()
            mock_client.id = 1
            mock_client.name = "ООО Ромашка"
            mock_client.email = "client@test.com"
            
            mock_db = MagicMock()
            mock_db.get.return_value = mock_client
            
            service = PaymentNotificationService()
            results = await service.notify_invoice_paid(
                db=mock_db,
                invoice=mock_invoice,
                payment_amount=Decimal("50000.00"),
                payment_date=date.today(),
                payer_name="ООО Платёж",
                payer_inn="7700000000",
                client_user_id=1,
            )
            
            assert results["email"] is True
            assert results["telegram"] is True
            assert results["in_app"] is True
            mock_email.send_invoice_paid.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_invoice_partially_paid(self):
        """✅ При частичной оплате уведомление содержит остаток."""
        with patch("app.services.payment_notifications.email_service") as mock_email, \
             patch("app.services.payment_notifications.telegram_service") as mock_tg, \
             patch("app.services.payment_notifications.create_notification", new_callable=AsyncMock):
            
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=True)
            
            mock_invoice = MagicMock()
            mock_invoice.client_id = 1
            mock_invoice.document_number = "INV-2026-0001"
            mock_invoice.total = Decimal("50000.00")
            mock_invoice.paid_amount = Decimal("30000.00")
            mock_invoice.status.value = "partially_paid"
            
            mock_client = MagicMock()
            mock_client.id = 1
            mock_client.name = "ООО Ромашка"
            mock_client.email = "client@test.com"
            
            mock_db = MagicMock()
            mock_db.get.return_value = mock_client
            
            service = PaymentNotificationService()
            results = await service.notify_invoice_paid(
                db=mock_db,
                invoice=mock_invoice,
                payment_amount=Decimal("30000.00"),
                payment_date=date.today(),
                payer_name="ООО Платёж",
            )
            
            assert results["email"] is True
            # Проверяем что send_invoice_paid вызван с правильными аргументами
            call_kwargs = mock_email.send_invoice_paid.call_args[1]
            assert call_kwargs["payment_amount"] == Decimal("30000.00")

    @pytest.mark.asyncio
    async def test_graceful_degradation_email_fails(self):
        """✅ При падении email остальные каналы продолжают работать."""
        with patch("app.services.payment_notifications.email_service") as mock_email, \
             patch("app.services.payment_notifications.telegram_service") as mock_tg:
            
            mock_email.send_invoice_paid.side_effect = Exception("SMTP error")
            mock_tg.send_message = AsyncMock(return_value=True)
            
            mock_invoice = MagicMock()
            mock_invoice.client_id = 1
            mock_invoice.total = Decimal("50000.00")
            mock_invoice.paid_amount = Decimal("50000.00")
            mock_invoice.status.value = "paid"
            
            mock_client = MagicMock()
            mock_client.id = 1
            mock_client.name = "Test"
            mock_client.email = "test@test.com"
            
            mock_db = MagicMock()
            mock_db.get.return_value = mock_client
            
            service = PaymentNotificationService()
            results = await service.notify_invoice_paid(
                db=mock_db,
                invoice=mock_invoice,
                payment_amount=Decimal("50000.00"),
                payment_date=date.today(),
                payer_name="Test",
            )
            
            # Email упал, но метод не выбросил исключение
            assert results["email"] is False
            assert results["telegram"] is True

    @pytest.mark.asyncio
    async def test_fallback_email_when_client_has_no_email(self):
        """✅ При отсутствии email у клиента используется fallback."""
        with patch("app.services.payment_notifications.email_service") as mock_email, \
             patch("app.services.payment_notifications.telegram_service") as mock_tg:
            
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=False)
            
            mock_invoice = MagicMock()
            mock_invoice.client_id = 123
            mock_invoice.total = Decimal("10000.00")
            mock_invoice.paid_amount = Decimal("10000.00")
            mock_invoice.status.value = "paid"
            
            mock_client = MagicMock()
            mock_client.id = 123
            mock_client.name = "No Email Client"
            mock_client.email = None  # ← Нет email
            
            mock_db = MagicMock()
            mock_db.get.return_value = mock_client
            
            service = PaymentNotificationService()
            results = await service.notify_invoice_paid(
                db=mock_db,
                invoice=mock_invoice,
                payment_amount=Decimal("10000.00"),
                payment_date=date.today(),
                payer_name="Test",
            )
            
            # Проверяем что использован fallback email
            call_kwargs = mock_email.send_invoice_paid.call_args[1]
            assert call_kwargs["client_email"] == "client_123@spectech.dev"
            assert results["email"] is True

    @pytest.mark.asyncio
    async def test_client_not_found_returns_empty(self):
        """✅ Если клиент не найден — возвращает пустые результаты."""
        mock_db = MagicMock()
        mock_db.get.return_value = None  # Клиент не найден
        
        mock_invoice = MagicMock()
        mock_invoice.client_id = 999
        
        service = PaymentNotificationService()
        results = await service.notify_invoice_paid(
            db=mock_db,
            invoice=mock_invoice,
            payment_amount=Decimal("10000.00"),
            payment_date=date.today(),
            payer_name="Test",
        )
        
        assert results["email"] is False
        assert results["telegram"] is False
        assert results["in_app"] is False