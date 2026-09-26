"""Email service для отправки уведомлений через SMTP."""

import logging
import smtplib
import ssl
from datetime import datetime
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
        from app.core.config import settings

        # Добавляем frontend_url если его нет
        if "frontend_url" not in context:
            context["frontend_url"] = settings.FRONTEND_URL

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
                    # 🆕 Определяем правильный MIME-тип
                    if file_path.suffix.lower() == ".pdf":
                        part = MIMEBase("application", "pdf")
                    else:
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
        body: str | None = None,
        html_body: str | None = None,
        template_name: str | None = None,
        context: dict | None = None,
        attachments: list | None = None,
    ) -> bool:
        """
        Универсальный метод отправки email через SMTP.

        Поддерживает два режима:
        1. Прямой: body + html_body
        2. Шаблонный: template_name + context (для обратной совместимости)
        """
        # 🆕 Логирование в EmailLog (создаём запись со статусом pending)
        log_id = None
        try:
            from app.core.db import SessionLocal
            from app.models.email import EmailLog, EmailStatus

            db_log = SessionLocal()
            # Рендерим HTML заранее для логирования
            rendered_html = None
            if template_name and context:
                rendered_html = self._render_template(template_name, context)
            elif html_body:
                rendered_html = html_body

            email_log = EmailLog(
                company_id=1,  # TODO: получать из контекста
                to_email=to_email,
                subject=subject,
                html_body=rendered_html,
                status=EmailStatus.pending,
                invoice_id=(
                    context.get("invoice").id
                    if context
                    and context.get("invoice")
                    and hasattr(context.get("invoice"), "id")
                    else None
                ),
                act_id=(
                    context.get("act").id
                    if context
                    and context.get("act")
                    and hasattr(context.get("act"), "id")
                    else None
                ),
            )
            db_log.add(email_log)
            db_log.commit()
            log_id = email_log.id
            db_log.close()
        except Exception as log_err:
            logger.warning(f"⚠️ Failed to create email log entry: {log_err}")

        try:  # === Режим 2: Шаблонный ===
            if template_name and context:
                html_body = rendered_html  # Используем уже отрендеренный
                # Преобразуем Path-вложения в dict-формат
                if attachments:
                    converted_attachments = []
                    for file_path in attachments:
                        if isinstance(file_path, Path) and file_path.exists():
                            with open(file_path, "rb") as f:
                                converted_attachments.append(
                                    {
                                        "filename": file_path.name,
                                        "content": f.read(),
                                    }
                                )
                    attachments = converted_attachments

            # === Режим 1: Прямой (новая архитектура) ===
            elif not body and not html_body:
                raise ValueError(
                    "Either (body/html_body) or (template_name/context) must be provided"
                )

            # Создаём MIME-сообщение
            msg = MIMEMultipart("mixed")
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            # Текстовое тело
            if body:
                msg.attach(MIMEText(body, "plain", "utf-8"))

            # HTML-версия
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Вложения (всегда в dict-формате)
            if attachments:
                for attachment in attachments:
                    if isinstance(attachment, dict):
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment["content"])
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename="{attachment["filename"]}"',
                        )
                        msg.attach(part)

            # === КЛЮЧЕВОЕ: правильный выбор SMTP-соединения ===
            port = settings.SMTP_PORT

            if port == 465:
                # Mail.ru, Яндекс: SSL с самого начала (НЕ starttls!)
                server = smtplib.SMTP_SSL(
                    settings.SMTP_HOST,
                    port,
                    timeout=30,
                    context=ssl.create_default_context(),
                )
            else:
                # Gmail (587): обычный SMTP + STARTTLS
                server = smtplib.SMTP(settings.SMTP_HOST, port, timeout=30)
                server.ehlo()
                if port == 587:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()

            # Аутентификация
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

            # Отправка
            server.send_message(msg)
            server.quit()

            logger.info(f"✅ Email sent to {to_email}: {subject}")

            # 🆕 Обновляем статус в EmailLog на sent
            if log_id:
                try:
                    db_log = SessionLocal()
                    email_log = db_log.get(EmailLog, log_id)
                    if email_log:
                        email_log.status = EmailStatus.sent
                        email_log.sent_at = datetime.now()
                        db_log.commit()
                    db_log.close()
                except Exception as log_err:
                    logger.warning(f"⚠️ Failed to update email log to sent: {log_err}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}", exc_info=True)

            # 🆕 Обновляем статус в EmailLog на failed
            if log_id:
                try:
                    db_log = SessionLocal()
                    email_log = db_log.get(EmailLog, log_id)
                    if email_log:
                        email_log.status = EmailStatus.failed
                        email_log.error_message = str(e)
                        db_log.commit()
                    db_log.close()
                except Exception as log_err:
                    logger.warning(f"⚠️ Failed to update email log to failed: {log_err}")

            raise

    def send_invoice_created(
        self, invoice, client_email: str, client_name: str
    ) -> bool:
        """Уведомление о создании счёта с PDF вложением."""
        from app.models.telematics import UploadedFile

        subject = f"Новый счёт {invoice.document_number} от СпецТехника Про"

        # Загружаем PDF из MinIO
        pdf_path = None
        try:
            # Ищем последний загруженный PDF для этого счёта
            from app.core.db import SessionLocal

            db = SessionLocal()
            uploaded_file = (
                db.query(UploadedFile)
                .filter(
                    UploadedFile.invoice_id == invoice.id,
                    UploadedFile.file_category == "invoice_pdf",
                )
                .order_by(UploadedFile.created_at.desc())
                .first()
            )
            db.close()

            if uploaded_file:
                # Скачиваем из MinIO во временный файл
                from app.services import storage_service

                pdf_bytes = storage_service.get_file(
                    uploaded_file.storage_path
                )  # ← get_file!
                if pdf_bytes:
                    import tempfile

                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix=".pdf",
                        prefix=f"{invoice.document_number}_",
                    )
                    temp_file.write(pdf_bytes)
                    temp_file.close()
                    pdf_path = Path(temp_file.name)
        except Exception as e:
            logger.warning(f"⚠️ Could not attach PDF to email: {e}")

        attachments = [pdf_path] if pdf_path else None

        result = self.send_email(
            to_email=client_email,
            subject=subject,
            template_name="email/invoice_created.html",
            context={
                "invoice": invoice,
                "client_name": client_name,
                "subject": subject,
            },
            attachments=attachments,
        )

        # Удаляем временный файл
        if pdf_path and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass

        return result

    def send_act_signed(self, act, user_email: str, user_name: str) -> bool:
        """Уведомление о подписании акта с PDF вложением."""
        from app.models.telematics import UploadedFile

        subject = f"Акт {act.document_number} подписан"

        # Загружаем PDF из MinIO
        pdf_path = None
        try:
            from app.core.db import SessionLocal

            db = SessionLocal()
            uploaded_file = (
                db.query(UploadedFile)
                .filter(
                    UploadedFile.act_id == act.id,
                    UploadedFile.file_category == "act_pdf",
                )
                .order_by(UploadedFile.created_at.desc())
                .first()
            )
            db.close()

            if uploaded_file:
                from app.services import storage_service

                pdf_bytes = storage_service.get_file(uploaded_file.storage_path)
                if pdf_bytes:
                    import tempfile

                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf", prefix=f"{act.document_number}_"
                    )
                    temp_file.write(pdf_bytes)
                    temp_file.close()
                    pdf_path = Path(temp_file.name)
        except Exception as e:
            logger.warning(f"⚠️ Could not attach PDF to act email: {e}")

        attachments = [pdf_path] if pdf_path else None

        result = self.send_email(
            to_email=user_email,
            subject=subject,
            template_name="email/act_signed.html",
            context={
                "act": act,
                "user_name": user_name,
                "subject": subject,
            },
            attachments=attachments,
        )

        if pdf_path and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass

        return result

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
