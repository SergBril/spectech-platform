"""📧 Массовая отправка email и просмотр логов."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jinja2 import BaseLoader, Environment
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.email import EmailLog, EmailStatus, EmailTemplate
from app.schemas.email import BulkSendRequest, EmailLogRead
from app.services.email_service import email_service

logger = logging.getLogger("spectech.email_bulk")

router = APIRouter(prefix="/email-bulk", tags=["📧 Email Bulk Send"])


@router.post(
    "/send",
    response_model=dict,
    summary="Массовая отправка email",
)
async def bulk_send_email(
    payload: BulkSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Массовая отправка email по шаблону.

    Отправляет email всем указанным получателям, используя шаблон с переменными.
    """
    # Получаем шаблон
    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == payload.template_id,
            EmailTemplate.company_id == company_id,
            EmailTemplate.is_active == True,
        )
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Шаблон не найден или неактивен",
        )

    # Jinja2 для рендеринга шаблона
    jinja_env = Environment(loader=BaseLoader())

    sent_count = 0
    failed_count = 0
    results = []

    for recipient_email in payload.recipient_emails:
        try:
            # Рендерим subject и body с контекстом
            subject_template = jinja_env.from_string(template.subject)
            body_template = jinja_env.from_string(template.html_body)

            rendered_subject = subject_template.render(**payload.context)
            rendered_body = body_template.render(**payload.context)

            # Отправляем email
            success = await email_service.send_email(
                to_email=recipient_email,
                subject=rendered_subject,
                body=None,
                html_body=rendered_body,
            )

            if success:
                # Логируем успешную отправку
                email_log = EmailLog(
                    company_id=company_id,
                    template_id=template.id,
                    to_email=recipient_email,
                    subject=rendered_subject,
                    html_body=rendered_body,
                    status=EmailStatus.sent,
                    sent_at=datetime.utcnow(),
                )
                db.add(email_log)
                sent_count += 1
                results.append({"email": recipient_email, "status": "sent"})
            else:
                failed_count += 1
                results.append(
                    {
                        "email": recipient_email,
                        "status": "failed",
                        "error": "Unknown error",
                    }
                )

        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")

            # Логируем ошибку
            email_log = EmailLog(
                company_id=company_id,
                template_id=template.id,
                to_email=recipient_email,
                subject=template.subject,
                status=EmailStatus.failed,
                error_message=str(e),
            )
            db.add(email_log)
            failed_count += 1
            results.append(
                {"email": recipient_email, "status": "failed", "error": str(e)}
            )

    db.commit()

    logger.info(f"Bulk send completed: {sent_count} sent, {failed_count} failed")

    return {
        "total": len(payload.recipient_emails),
        "sent": sent_count,
        "failed": failed_count,
        "results": results,
    }


@router.get(
    "/logs",
    response_model=list[EmailLogRead],
    summary="История отправок email",
)
def list_email_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: EmailStatus | None = Query(None, alias="status"),
    template_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить историю отправок email."""
    query = select(EmailLog).where(EmailLog.company_id == company_id)

    if status_filter:
        query = query.where(EmailLog.status == status_filter)
    if template_id:
        query = query.where(EmailLog.template_id == template_id)

    query = query.order_by(EmailLog.created_at.desc()).offset(skip).limit(limit)
    logs = db.scalars(query).all()

    return logs
