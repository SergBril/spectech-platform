"""
Multi-Channel Salary Notification Dispatcher.

При утверждении зарплаты отправляет расчётный листок
во все доступные каналы для каждого сотрудника:
  - 📧 Email (если есть)
  - 📱 Telegram (если привязан)
  - 💬 Внутреннее уведомление (всегда)
"""

import logging
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.contractor import Employee, Contractor
from app.models.salary import SalaryRecord
from app.services.salary_pdf import generate_salary_payslip
from app.services.notification_service import create_notification
from app.services.telegram_service import telegram_service
from app.services.email_service import email_service

logger = logging.getLogger("spectech.salary_notifications")


class SalaryNotificationDispatcher:
    """Координатор доставки расчётных листков по всем каналам."""

    async def notify_employee(
        self,
        db: Session,
        record: SalaryRecord,
        approved_by_name: str = "",
    ) -> dict[str, bool]:
        """
        Отправляет расчётный листок сотруднику через все доступные каналы.

        Returns:
            dict с результатами: {"email": True/False, "telegram": True/False, "internal": True/False}
        """
        results = {"email": False, "telegram": False, "internal": False}

        # Находим сотрудника и пользователя
        employee = db.query(Employee).filter(
            Employee.id == record.employee_contractor_id
        ).first()

        if not employee:
            logger.warning("Employee #%s not found for salary record #%s",
                           record.employee_contractor_id, record.id)
            return results

        contractor = db.query(Contractor).filter(
            Contractor.id == record.employee_contractor_id
        ).first()

        employee_name = contractor.name if contractor else f"Сотрудник #{employee.id}"

        # Генерируем PDF один раз
        try:
            pdf_bytes = generate_salary_payslip(record, employee_name)
        except Exception as e:
            logger.error("Failed to generate payslip PDF for record #%s: %s", record.id, e)
            pdf_bytes = None

        # Определяем доступные каналы
        user = None
        if employee.user_id:
            user = db.query(User).filter(User.id == employee.user_id).first()

        contact_email = getattr(contractor, "contact_email", None) if contractor else None
        user_email = getattr(user, "email", None) if user else None
        target_email = contact_email or user_email

        telegram_id = getattr(user, "telegram_id", None) if user else None

        period_str = f"{record.period_start.strftime('%d.%m.%Y')} — {record.period_end.strftime('%d.%m.%Y')}"
        net_amount = float(record.net_amount or 0)

        # === 1. Внутреннее уведомление (ВСЕГДА) ===
        try:
            if user:
                create_notification(
                    db=db,
                    user_id=user.id,
                    channel="system",
                    title=f"💰 Расчётный листок за {period_str}",
                    body=(
                        f"Вам начислена зарплата за период {period_str}.\n"
                        f"К выплате: {net_amount:,.2f} ₽\n"
                        f"Статус: Утверждено\n"
                        f"Утвердил: {approved_by_name}"
                    ),
                )
                results["internal"] = True
                logger.info("✅ Internal notification sent to user #%s", user.id)
        except Exception as e:
            logger.error("Failed to create internal notification: %s", e)

        # === 2. Email ===
        if target_email and pdf_bytes:
            try:
                await email_service.send_email(
                    to=target_email,
                    subject=f"Расчётный листок за {period_str} — СпецТехника Про",
                    html_body=(
                        f"<div style='font-family: Arial, sans-serif; padding: 20px;'>"
                        f"<h2>💰 Расчётный листок</h2>"
                        f"<p><strong>Сотрудник:</strong> {employee_name}</p>"
                        f"<p><strong>Период:</strong> {period_str}</p>"
                        f"<p><strong>К выплате:</strong> {net_amount:,.2f} ₽</p>"
                        f"<p><strong>Статус:</strong> Утверждено</p>"
                        f"<hr/>"
                        f"<p style='color: #666; font-size: 12px;'>"
                        f"Расчётный листок во вложении. "
                        f"Платформа «СпецТехника Про»</p>"
                        f"</div>"
                    ),
                    attachments=[("payslip.pdf", pdf_bytes)],
                )
                results["email"] = True
                logger.info("✅ Email sent to %s", target_email)
            except Exception as e:
                logger.error("Failed to send email to %s: %s", target_email, e)

        # === 3. Telegram ===
        if telegram_id and pdf_bytes:
            try:
                caption = (
                    f"💰 *Расчётный листок*\n"
                    f"📅 Период: {period_str}\n"
                    f"💵 К выплате: {net_amount:,.2f} ₽\n"
                    f"✅ Статус: Утверждено"
                )
                await telegram_service.send_document(
                    chat_id=str(telegram_id),
                    document=pdf_bytes,
                    filename=f"payslip_{period_str.replace('.', '-').replace(' — ', '_')}.pdf",
                    caption=caption,
                )
                results["telegram"] = True
                logger.info("✅ Telegram document sent to user #%s (tg:%s)", user.id, telegram_id)
            except Exception as e:
                logger.error("Failed to send Telegram to %s: %s", telegram_id, e)
        elif telegram_id and not pdf_bytes:
            # Отправляем текстовое сообщение без PDF
            try:
                text = (
                    f"💰 *Расчётный листок*\n"
                    f"📅 Период: {period_str}\n"
                    f"💵 К выплате: {net_amount:,.2f} ₽\n"
                    f"✅ Статус: Утверждено\n\n"
                    f"_PDF доступен в личном кабинете_"
                )
                await telegram_service.send_message(
                    chat_id=str(telegram_id),
                    text=text,
                )
                results["telegram"] = True
                logger.info("✅ Telegram text sent to user #%s (no PDF)", user.id)
            except Exception as e:
                logger.error("Failed to send Telegram text to %s: %s", telegram_id, e)

        # Логируем итог
        channels_used = [k for k, v in results.items() if v]
        logger.info(
            "📨 Salary notification for employee #%s (%s): channels=%s",
            record.employee_contractor_id, employee_name, channels_used
        )

        return results


# Синглтон
salary_notification_dispatcher = SalaryNotificationDispatcher()