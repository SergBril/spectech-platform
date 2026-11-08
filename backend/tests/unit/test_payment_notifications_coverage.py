"""Coverage tests for payment_notifications."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def invoice_paid():
    return SimpleNamespace(
        id=1,
        client_id=10,
        document_number="INV-001",
        total=Decimal("50000.00"),
        paid_amount=Decimal("50000.00"),
        status=SimpleNamespace(value="paid"),
    )


@pytest.fixture
def invoice_partial():
    return SimpleNamespace(
        id=2,
        client_id=10,
        document_number="INV-002",
        total=Decimal("100000.00"),
        paid_amount=Decimal("30000.00"),
        status=SimpleNamespace(value="partial"),
    )


@pytest.fixture
def client():
    return SimpleNamespace(id=10, name="OOO Test", email="client@test.com")


class TestNotifyInvoicePaid:
    """Cover notify_invoice_paid (lines 22-126)."""

    @pytest.mark.asyncio
    async def test_client_not_found(self, mock_db, invoice_paid):
        from app.services.payment_notifications import PaymentNotificationService

        mock_db.get.return_value = None
        result = await PaymentNotificationService.notify_invoice_paid(
            mock_db, invoice_paid, Decimal("50000"), "2026-11-06", "Payer"
        )
        assert result == {"email": False, "telegram": False, "in_app": False}

    @pytest.mark.asyncio
    async def test_full_paid_all_channels(self, mock_db, invoice_paid, client):
        from app.services.payment_notifications import PaymentNotificationService

        mock_db.get.return_value = client

        with (
            patch("app.services.payment_notifications.email_service") as mock_email,
            patch("app.services.payment_notifications.telegram_service") as mock_tg,
            patch(
                "app.services.payment_notifications.create_notification",
                new_callable=AsyncMock,
            ) as mock_notif,
        ):
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=True)
            result = await PaymentNotificationService.notify_invoice_paid(
                mock_db,
                invoice_paid,
                Decimal("50000"),
                "2026-11-06",
                "Payer",
                payer_inn="7701234567",
                client_user_id=42,
            )

        assert result["email"] is True
        assert result["telegram"] is True
        assert result["in_app"] is True
        mock_notif.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_payment(self, mock_db, invoice_partial, client):
        from app.services.payment_notifications import PaymentNotificationService

        mock_db.get.return_value = client

        with (
            patch("app.services.payment_notifications.email_service") as mock_email,
            patch("app.services.payment_notifications.telegram_service") as mock_tg,
            patch(
                "app.services.payment_notifications.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=True)
            result = await PaymentNotificationService.notify_invoice_paid(
                mock_db,
                invoice_partial,
                Decimal("30000"),
                "2026-11-06",
                "Payer",
                client_user_id=42,
            )

        assert result["email"] is True
        tg_text = mock_tg.send_message.call_args[1]["text"]
        assert "Частичная оплата" in tg_text or "Получена частичная" in tg_text

    @pytest.mark.asyncio
    async def test_fallback_email(self, mock_db, invoice_paid):
        from app.services.payment_notifications import PaymentNotificationService

        client_no_email = SimpleNamespace(id=10, name="OOO Test", email=None)
        mock_db.get.return_value = client_no_email

        with (
            patch("app.services.payment_notifications.email_service") as mock_email,
            patch("app.services.payment_notifications.telegram_service") as mock_tg,
            patch(
                "app.services.payment_notifications.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=False)
            result = await PaymentNotificationService.notify_invoice_paid(
                mock_db, invoice_paid, Decimal("50000"), "2026-11-06", "Payer"
            )

        assert result["email"] is True
        call_kwargs = mock_email.send_invoice_paid.call_args[1]
        assert "client_10@spectech.dev" in call_kwargs["client_email"]

    @pytest.mark.asyncio
    async def test_email_error_continues(self, mock_db, invoice_paid, client):
        from app.services.payment_notifications import PaymentNotificationService

        mock_db.get.return_value = client

        with (
            patch("app.services.payment_notifications.email_service") as mock_email,
            patch("app.services.payment_notifications.telegram_service") as mock_tg,
            patch(
                "app.services.payment_notifications.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            mock_email.send_invoice_paid.side_effect = Exception("SMTP fail")
            mock_tg.send_message = AsyncMock(return_value=True)
            result = await PaymentNotificationService.notify_invoice_paid(
                mock_db, invoice_paid, Decimal("50000"), "2026-11-06", "Payer"
            )

        assert result["email"] is False
        assert result["telegram"] is True

    @pytest.mark.asyncio
    async def test_telegram_error_continues(self, mock_db, invoice_paid, client):
        from app.services.payment_notifications import PaymentNotificationService

        mock_db.get.return_value = client

        with (
            patch("app.services.payment_notifications.email_service") as mock_email,
            patch("app.services.payment_notifications.telegram_service") as mock_tg,
            patch(
                "app.services.payment_notifications.create_notification",
                new_callable=AsyncMock,
            ),
        ):
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(side_effect=Exception("TG fail"))
            result = await PaymentNotificationService.notify_invoice_paid(
                mock_db, invoice_paid, Decimal("50000"), "2026-11-06", "Payer"
            )

        assert result["email"] is True
        assert result["telegram"] is False

    @pytest.mark.asyncio
    async def test_no_client_user_id_skips_in_app(self, mock_db, invoice_paid, client):
        from app.services.payment_notifications import PaymentNotificationService

        mock_db.get.return_value = client

        with (
            patch("app.services.payment_notifications.email_service") as mock_email,
            patch("app.services.payment_notifications.telegram_service") as mock_tg,
            patch(
                "app.services.payment_notifications.create_notification",
                new_callable=AsyncMock,
            ) as mock_notif,
        ):
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=True)
            result = await PaymentNotificationService.notify_invoice_paid(
                mock_db,
                invoice_paid,
                Decimal("50000"),
                "2026-11-06",
                "Payer",
                client_user_id=None,
            )

        assert result["in_app"] is False
        mock_notif.assert_not_called()

    @pytest.mark.asyncio
    async def test_in_app_error_continues(self, mock_db, invoice_paid, client):
        from app.services.payment_notifications import PaymentNotificationService

        mock_db.get.return_value = client

        with (
            patch("app.services.payment_notifications.email_service") as mock_email,
            patch("app.services.payment_notifications.telegram_service") as mock_tg,
            patch(
                "app.services.payment_notifications.create_notification",
                new_callable=AsyncMock,
                side_effect=Exception("DB fail"),
            ),
        ):
            mock_email.send_invoice_paid.return_value = True
            mock_tg.send_message = AsyncMock(return_value=True)
            result = await PaymentNotificationService.notify_invoice_paid(
                mock_db,
                invoice_paid,
                Decimal("50000"),
                "2026-11-06",
                "Payer",
                client_user_id=42,
            )

        assert result["in_app"] is False
        assert result["email"] is True


class TestGlobalSingleton:
    def test_exists(self):
        from app.services.payment_notifications import payment_notification_service

        assert payment_notification_service is not None
