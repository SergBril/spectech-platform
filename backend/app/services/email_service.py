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
        if "frontend_url" not in context:
            context["frontend_url"] = settings.FRONTEND_URL

        template = self.jinja_env.get_template(template_name)
        html = template.render(**context)
        return premailer_transform(html)

    def _attach_file(self, msg: MIMEMultipart, filename: str, content: bytes) -> None:
        """Прикрепляет файл к сообщению с правильным MIME-типом."""
        if filename.lower().endswith(".pdf"):
            part = MIMEBase("application", "pdf")
        else:
            part = MIMEBase("application", "octet-stream")
        part.set_payload(content)
        encoders.encode_base64(part)
        # Используем RFC 2231 encoding для поддержки кириллицы в именах файлов
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=("utf-8", "", filename),
        )
        msg.attach(part)

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
        2. Шаблонный: template_name + context

        Вложения поддерживаются в двух форматах:
        - dict: {"filename": "name.pdf", "content": b"..."}
        - Path: путь к файлу на диске
        """
        # Логирование в EmailLog (создаём запись со статусом pending)
        log_id = None
        try:
            from app.core.db import SessionLocal
            from app.models.email import EmailLog, EmailStatus

            db_log = SessionLocal()
            rendered_html = None
            if template_name and context:
                rendered_html = self._render_template(template_name, context)
            elif html_body:
                rendered_html = html_body

            email_log = EmailLog(
                company_id=1,
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

        try:
            # === Режим 2: Шаблонный ===
            if template_name and context:
                html_body = rendered_html

            # === Режим 1: Прямой ===
            elif not body and not html_body:
                raise ValueError(
                    "Either (body/html_body) or (template_name/context) must be provided"
                )

            # Нормализуем вложения в единый формат: list[dict]
            normalized_attachments = []
            if attachments:
                for att in attachments:
                    if isinstance(att, dict) and "filename" in att and "content" in att:
                        # Уже dict — используем как есть
                        normalized_attachments.append(att)
                    elif isinstance(att, Path) and att.exists():
                        # Path объект — читаем в dict
                        with open(att, "rb") as f:
                            normalized_attachments.append({
                                "filename": att.name,
                                "content": f.read(),
                            })
                    elif isinstance(att, str) and Path(att).exists():
                        # Строковый путь — читаем в dict
                        p = Path(att)
                        with open(p, "rb") as f:
                            normalized_attachments.append({
                                "filename": p.name,
                                "content": f.read(),
                            })
                    else:
                        logger.warning(f"⚠️ Skipping invalid attachment: {type(att)}")

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

            # Вложения
            for att in normalized_attachments:
                self._attach_file(msg, att["filename"], att["content"])
                logger.debug(f"📎 Attached: {att['filename']} ({len(att['content'])} bytes)")

            # === Выбор SMTP-соединения ===
            port = settings.SMTP_PORT

            if port == 465:
                server = smtplib.SMTP_SSL(
                    settings.SMTP_HOST,
                    port,
                    timeout=30,
                    context=ssl.create_default_context(),
                )
            else:
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

            # Обновляем статус в EmailLog на sent
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

        pdf_path = None
        try:
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
                from app.services import storage_service

                pdf_bytes = storage_service.get_file(uploaded_file.storage_path)
                if pdf_bytes:
                    import tempfile

                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf", prefix=f"{invoice.document_number}_"
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

    def send_rental_completed(
        self, rental, invoice, client_email: str, client_name: str
    ) -> bool:
        """Уведомление клиенту о завершении аренды + счёт."""
        subject = f"✅ Аренда #{rental.id} завершена — счёт {invoice.document_number}"
        return self.send_email(
            to_email=client_email,
            subject=subject,
            template_name="email/rental_completed.html",
            context={
                "rental": rental,
                "invoice": invoice,
                "client_name": client_name,
                "subject": subject,
            },
        )

    def send_payout_created(
        self, payout, owner_email: str, owner_name: str
    ) -> bool:
        """Уведомление собственнику о созданной выплате."""
        subject = f"💰 Выплата {payout.document_number} на {payout.net_amount} ₽"
        return self.send_email(
            to_email=owner_email,
            subject=subject,
            template_name="email/payout_created.html",
            context={
                "payout": payout,
                "owner_name": owner_name,
                "subject": subject,
            },
        )

    def send_payout_approved(
        self, payout, owner_email: str, owner_name: str
    ) -> bool:
        """Уведомление собственнику об одобренной выплате с PDF-вложением."""
        from app.services.pdf_service import generate_payout_pdf
        from app.models.catalog import Vehicle
        from app.models.contractor import Contractor
        from app.core.db import SessionLocal

        subject = f"✅ Выплата {payout.document_number} одобрена — {payout.net_amount} ₽"

        pdf_attachment = None
        temp_path_to_cleanup = None

        try:
            db_tmp = SessionLocal()
            owner = db_tmp.get(Contractor, payout.owner_id)
            owner_name_full = owner.name if owner else owner_name
            vehicle = db_tmp.get(Vehicle, payout.vehicle_id)
            vehicle_name = vehicle.name if vehicle else ""
            db_tmp.close()

            pdf_result = generate_payout_pdf(
                payout, owner_name=owner_name_full, vehicle_name=vehicle_name
            )

            if isinstance(pdf_result, bytes):
                # ⚠️ КРИТИЧНО: Не прикрепляем пустой PDF — это ломает MIME заголовки
                if len(pdf_result) > 100:  # Минимальный размер валидного PDF
                    pdf_attachment = {
                        "filename": f"{payout.document_number}.pdf",
                        "content": pdf_result,
                    }
                    logger.info(f"📎 PDF attached from memory ({len(pdf_result)} bytes)")
                else:
                    logger.warning(f"⚠️ PDF too small or empty ({len(pdf_result)} bytes), sending WITHOUT attachment")

            elif isinstance(pdf_result, (str, Path)):
                pdf_path = Path(pdf_result)
                if pdf_path.exists() and pdf_path.stat().st_size > 100:
                    with open(pdf_path, "rb") as f:
                        pdf_content = f.read()
                    pdf_attachment = {
                        "filename": f"{payout.document_number}.pdf",
                        "content": pdf_content,
                    }
                    temp_path_to_cleanup = pdf_path
                    logger.info(f"📎 PDF attached from file: {pdf_path.name} ({len(pdf_content)} bytes)")
                else:
                    logger.warning(f"⚠️ PDF file missing or empty: {pdf_path}")
            else:
                logger.warning(f"⚠️ Unexpected PDF result type: {type(pdf_result)}")

        except Exception as e:
            logger.warning(f"⚠️ Could not generate payout PDF for email: {e}", exc_info=True)

        if temp_path_to_cleanup and temp_path_to_cleanup.exists():
            try:
                temp_path_to_cleanup.unlink()
            except Exception:
                pass

        attachments = [pdf_attachment] if pdf_attachment else None

        return self.send_email(
            to_email=owner_email,
            subject=subject,
            template_name="email/payout_created.html",
            context={
                "payout": payout,
                "owner_name": owner_name,
                "subject": subject,
            },
            attachments=attachments,
        )

    def send_dispute_opened(
        self, dispute, dispatcher_email: str, dispatcher_name: str
    ) -> bool:
        """Уведомление диспетчеру о новом споре."""
        subject = f"⚖️ Новый спор #{dispute.id} требует вашего участия"
        return self.send_email(
            to_email=dispatcher_email,
            subject=subject,
            template_name="email/dispute_opened.html",
            context={
                "dispute": dispute,
                "dispatcher_name": dispatcher_name,
                "subject": subject,
            },
        )

    def send_dispute_escalated(
        self, dispute, manager_email: str, manager_name: str,
        from_role: str, to_role: str, reason: str = "SLA breach"
    ) -> bool:
        """Уведомление менеджеру/CEO об эскалации спора."""
        subject = f"🚨 ЭСКАЛАЦИЯ: спор #{dispute.id} требует внимания"
        return self.send_email(
            to_email=manager_email,
            subject=subject,
            template_name="email/dispute_escalated.html",
            context={
                "dispute": dispute,
                "manager_name": manager_name,
                "from_role": from_role,
                "to_role": to_role,
                "reason": reason,
                "subject": subject,
            },
        )

    def send_invoice_paid(
        self,
        invoice,
        payment_amount,
        payment_date,
        payer_name: str,
        payer_inn: str | None,
        client_email: str,
        client_name: str,
    ) -> bool:
        """Уведомление клиенту о получении оплаты по счёту."""
        if invoice.status.value == "paid":
            subject = f"✅ Счёт {invoice.document_number} полностью оплачен"
        else:
            subject = f"💰 Получена оплата по счёту {invoice.document_number}"

        return self.send_email(
            to_email=client_email,
            subject=subject,
            template_name="email/invoice_paid.html",
            context={
                "invoice": invoice,
                "payment_amount": payment_amount,
                "payment_date": payment_date,
                "payer_name": payer_name,
                "payer_inn": payer_inn,
                "client_name": client_name,
                "subject": subject,
            },
        )


# Singleton instance
email_service = EmailService()