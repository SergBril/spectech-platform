"""Тестовый скрипт для проверки Email сервиса."""

import os

os.environ.setdefault("ENVIRONMENT", "development")

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.email_service import email_service


def test_invoice_email():
    """Тестирует отправку email о создании счёта."""
    invoice = SimpleNamespace(
        id=1,
        document_number="INV-2026-0001",
        invoice_date=datetime.now(),
        due_date=datetime.now() + timedelta(days=14),
        total=125000.50,
        status="Отправлен",
    )

    # Email получателя — может быть любым для Mailhog
    test_email = "test@example.com"

    print(f"📧 Отправка тестового email на {test_email}...")
    print("📬 Mailhog Web UI: http://localhost:8025")

    success = email_service.send_invoice_created(
        invoice=invoice,
        client_email=test_email,
        client_name="Тестовый Клиент",
    )

    if success:
        print("✅ Email успешно отправлен!")
        print("👉 Откройте http://localhost:8025 чтобы увидеть письмо")
    else:
        print("❌ Не удалось отправить email.")


if __name__ == "__main__":
    test_invoice_email()
