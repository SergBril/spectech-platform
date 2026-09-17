# 📧 Настройка Email-уведомлений

## Обзор

Система отправляет следующие типы писем:

| Тип | Триггер | Получатель |
|-----|---------|------------|
| Создание счёта | POST `/invoices` | Клиент (contact_email) |
| Повторная отправка счёта | POST `/invoices/{id}/resend-email` | Клиент |
| Подписание акта | POST `/acts/{id}/sign` | Клиент |
| Повторная отправка акта | POST `/acts/{id}/resend-email` | Клиент |
| Просроченный счёт | Cron (в разработке) | Клиент |
| Смена статуса заявки | PUT `/requests/{id}` | Автор заявки |

Все письма содержат **PDF-вложение** с полным документом (MIME-тип `application/pdf`).

## Локальная разработка: MailHog

MailHog — локальный SMTP-сервер для тестирования. Письма не уходят в интернет.

### Запуск

MailHog уже включён в `docker-compose.yml`:

```yaml
mailhog:
  image: mailhog/mailhog
  ports:
    - "1025:1025"  # SMTP
    - "8025:8025"  # Web UI

Конфигурация .env

EMAIL_ENABLED=true
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@spectech.pro
SMTP_FROM_NAME=СпецТехника Про
SMTP_USE_TLS=false

Использование
Откройте http://localhost:8025
Создайте счёт/отправьте акт
Письмо появится в Inbox
Вкладка MIME покажет HTML + PDF вложение
Production: Настройка SMTP
Вариант 1: Yandex SMTP

EMAIL_ENABLED=true
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USER=your-email@yandex.ru
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@yandex.ru
SMTP_FROM_NAME=СпецТехника Про
SMTP_USE_TLS=true

Важно: нужен "пароль приложения" (не пароль от почты). Создаётся в Яндекс.ID → Безопасность → Пароли приложений.
Вариант 2: Gmail

EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=СпецТехника Про
SMTP_USE_TLS=true

Вариант 3: Mailgun (рекомендуется для production)

EMAIL_ENABLED=true
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@mg.yourdomain.com
SMTP_PASSWORD=your-mailgun-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=СпецТехника Про
SMTP_USE_TLS=true

Вариант 4: SendGrid

EMAIL_ENABLED=true
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=СпецТехника Про
SMTP_USE_TLS=true

Тестирование отправки
Через UI
Откройте "Счета" или "Финансы → Акты"
Найдите документ со статусом "Отправлен" / "Оплачен"
Нажмите кнопку 📧
Подтвердите отправку
Проверьте почтовый ящик получателя
Через curl

# Получить токен
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@spectech.dev","password":"admin123"}' \
  | jq -r .access_token)

# Отправить счёт повторно
curl -X POST "http://localhost:8000/api/v1/invoices/25/resend-email" \
  -H "Authorization: Bearer $TOKEN"

Через Python shell

from app.services.email_service import email_service
from app.core.db import SessionLocal
from app.models.finance import Invoice

db = SessionLocal()
invoice = db.get(Invoice, 25)

email_service.send_invoice_created(
    invoice=invoice,
    client_email="test@example.com",
    client_name="Тестовый Клиент"
)
db.close()

Troubleshooting
Письма не отправляются
Проверьте EMAIL_ENABLED=true в .env
Проверьте логи: docker-compose logs backend | grep -i email
Проверьте доступность SMTP-сервера:

   docker-compose exec backend nc -zv smtp.yandex.ru 465

PDF не прикрепляется
Убедитесь, что для документа существует запись в uploaded_files
Проверьте, что PDF загружен в MinIO:

   docker exec spectech-platform-minio-1 mc ls myminio/spectech-docs/finance/invoices/

Письмо приходит без PDF
Проверьте, что в email_service.py используется правильный MIME-тип:

if file_path.suffix.lower() == ".pdf":
    part = MIMEBase("application", "pdf")

Кастомизация шаблонов
Шаблоны писем находятся в backend/app/templates/email/:
invoice_created.html — новый счёт
act_signed.html — акт подписан
act_created.html — акт создан
invoice_overdue.html — просроченный счёт
request_status_changed.html — смена статуса заявки
base.html — базовый шаблон (layout)
Редактируйте HTML/CSS для кастомизации внешнего вида.
