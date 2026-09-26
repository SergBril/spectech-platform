"""API endpoints для работы с email-логами."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, require_permission
from app.core.db import get_db
from app.models.auth import User
from app.models.email import EmailLog

router = APIRouter()


@router.get("/logs")
def get_email_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("email_logs", "view")),
):
    """Получить список отправленных email (только своей компании)."""
    stmt = select(EmailLog).where(EmailLog.company_id == company_id)

    if status_filter:
        stmt = stmt.where(EmailLog.status == status_filter)

    # Подсчёт общего количества
    count_stmt = select(func.count(EmailLog.id)).where(
        EmailLog.company_id == company_id
    )
    if status_filter:
        count_stmt = count_stmt.where(EmailLog.status == status_filter)
    total = db.scalar(count_stmt) or 0

    # Получение записей
    stmt = stmt.order_by(EmailLog.created_at.desc()).offset(offset).limit(limit)
    logs = db.scalars(stmt).all()

    return {
        "items": [
            {
                "id": log.id,
                "to_email": log.to_email,
                "to_name": log.to_name,
                "subject": log.subject,
                "status": log.status.value if log.status else None,
                "error_message": log.error_message,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                "invoice_id": log.invoice_id,
                "act_id": log.act_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/logs/{log_id}")
def get_email_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить детали email-лога (только своей компании)."""
    log = db.get(EmailLog, log_id)
    if not log or log.company_id != company_id:
        raise HTTPException(status_code=404, detail="Email log not found")

    return {
        "id": log.id,
        "to_email": log.to_email,
        "to_name": log.to_name,
        "subject": log.subject,
        "html_body": log.html_body,
        "text_body": log.text_body,
        "status": log.status.value if log.status else None,
        "error_message": log.error_message,
        "sent_at": log.sent_at.isoformat() if log.sent_at else None,
        "delivered_at": log.delivered_at.isoformat() if log.delivered_at else None,
        "invoice_id": log.invoice_id,
        "act_id": log.act_id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


@router.delete("/logs/{log_id}")
def delete_email_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    _: None = Depends(require_permission("email_logs", "delete")),
):
    """Удалить запись из email-лога (только своей компании)."""
    log = db.get(EmailLog, log_id)
    if not log or log.company_id != company_id:
        raise HTTPException(status_code=404, detail="Email log not found")

    db.delete(log)
    db.commit()
    return {"status": "success", "message": "Email log deleted"}
