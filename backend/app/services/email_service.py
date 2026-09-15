"""Email service для отправки уведомлений через SMTP."""

import logging
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from premailer import transform as premailer_transform

from app.core.config import settings

logger = logging.getLogger("spectech.email")


class EmailService:
    """Сервис для отправки email уведомлений."""

    def __init__(self):
        self.enabled = settings.EMAIL_ENABLED
        self.template_dir = Path(__file__).parent.parent / "templates"

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        if not self.enabled:
            logger.warning("⚠️ Email notifications disabled (EMAIL_ENABLED=false)")
        else:
            logger.info("✅ Email notifications enabled")

    def _render_template(self, template_name: str, context: dict) -> str:
        """Рендерит HTML шаблон и инлайнит CSS."""
        template = self.jinja_env.get_template(template_name)
        html = template.render(**context)
        return premailer_transform(html)

    def _create_message(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: list[Path] | None = None,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if attachments:
            for file_path in attachments:
                if not file_path.exists():
                    continue
                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{file_path.name}"',
                )
                msg.attach(part)

        return msg

    def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: dict,
        attachments: list[Path] | None = None,
    ) -> bool:
        """Отправляет email используя шаблон."""
        if not self.enabled:
            logger.info(f"📧 Email skipped (disabled): {subject} -> {to_email}")
            return False

        try:
            context_with_defaults = {
                "frontend_url": settings.FRONTEND_URL,
                **context,
            }
            html_body = self._render_template(template_name, context_with_defaults)
            msg = self._create_message(to_email, subject, html_body, attachments)

            if settings.SMTP_USE_TLS:
                context_ssl = ssl.create_default_context()
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.starttls(context=context_ssl)
                    if settings.SMTP_USER and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.send_message(msg)

            logger.info(f"✅ Email sent: {subject} -> {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return False

    def send_invoice_created(
        self, invoice, client_email: str, client_name: str
    ) -> bool:
        """Уведомление о создании счёта."""
        subject = f"Новый счёт {invoice.document_number} от СпецТехника Про"
        return self.send_email(
            to_email=client_email,
            subject=subject,
            template_name="email/invoice_created.html",
            context={
                "invoice": invoice,
                "client_name": client_name,
                "subject": subject,
            },
        )

    def send_act_signed(self, act, user_email: str, user_name: str) -> bool:
        """Уведомление о подписании акта."""
        subject = f"Акт {act.document_number} подписан"
        return self.send_email(
            to_email=user_email,
            subject=subject,
            template_name="email/act_signed.html",
            context={
                "act": act,
                "user_name": user_name,
                "subject": subject,
            },
        )

    def send_act_created(
        self, act, executor_email: str, executor_name: str, client_name: str
    ) -> bool:
        """Уведомление о создании акта (исполнителю)."""
        subject = f"📋 Акт {act.document_number} создан и готов к подписанию"
        return self.send_email(
            to_email=executor_email,
            subject=subject,
            template_name="email/act_created.html",
            context={
                "act": act,
                "executor_name": executor_name,
                "client_name": client_name,
                "subject": subject,
            },
        )

    def send_invoice_overdue(
        self, invoice, client_email: str, client_name: str, overdue_days: int
    ) -> bool:
        """Уведомление о просроченном счёте."""
        subject = f"⏰ Напоминание: счёт {invoice.document_number} просрочен"
        return self.send_email(
            to_email=client_email,
            subject=subject,
            template_name="email/invoice_overdue.html",
            context={
                "invoice": invoice,
                "client_name": client_name,
                "overdue_days": overdue_days,
                "subject": subject,
            },
        )

    def send_request_status_changed(
        self,
        request,
        user_email: str,
        user_name: str,
        old_status: str,
        new_status: str,
        comment: str = "",
    ) -> bool:
        """Уведомление о смене статуса заявки."""
        subject = f"📋 Заявка #{request.id}: статус изменён на {new_status}"
        return self.send_email(
            to_email=user_email,
            subject=subject,
            template_name="email/request_status_changed.html",
            context={
                "request": request,
                "user_name": user_name,
                "old_status": old_status,
                "new_status": new_status,
                "comment": comment,
                "subject": subject,
            },
        )


# Singleton instance
email_service = EmailService()
