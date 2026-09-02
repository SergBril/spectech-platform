"""API для управления Celery задачами."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_user
from app.tasks.pdf_tasks import (
    generate_invoice_pdf_async,
    generate_act_pdf_async,
    cleanup_old_pdfs,
)

router = APIRouter()


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post("/invoices/{invoice_id}/generate-pdf-async", response_model=TaskResponse)
def generate_invoice_pdf_background(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запускает генерацию PDF в фоне через Celery."""
    from app.models.finance import Invoice
    
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Запускаем задачу асинхронно
    task = generate_invoice_pdf_async.delay(
        invoice_id=invoice_id,
        company_id=current_user.company_id or 0,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"PDF generation queued for invoice {invoice_id}",
    )


@router.post("/acts/{act_id}/generate-pdf-async", response_model=TaskResponse)
def generate_act_pdf_background(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запускает генерацию PDF акта в фоне."""
    from app.models.finance import Act
    
    act = db.query(Act).filter(Act.id == act_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")
    
    task = generate_act_pdf_async.delay(
        act_id=act_id,
        company_id=current_user.company_id or 0,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"PDF generation queued for act {act_id}",
    )


@router.post("/cleanup-pdfs", response_model=TaskResponse)
def trigger_pdf_cleanup(
    days_old: int = 30,
    current_user: User = Depends(get_current_user),
):
    """Запускает очистку старых PDF."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin only")
    
    task = cleanup_old_pdfs.delay(days_old=days_old)
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"PDF cleanup queued (older than {days_old} days)",
    )


@router.get("/tasks/{task_id}/status")
def get_task_status(task_id: str):
    """Возвращает статус Celery задачи."""
    from app.core.celery_app import celery_app
    
    result = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    
    if result.ready():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    
    return response
# === Email задачи ===

@router.post("/emails/send", response_model=TaskResponse)
def send_email_task(
    to_email: str,
    subject: str,
    body: str,
    current_user: User = Depends(get_current_user),
):
    """Отправляет email через Celery."""
    from app.tasks.email_tasks import send_email_async
    
    task = send_email_async.delay(
        to_email=to_email,
        subject=subject,
        body_html=body,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Email to {to_email} queued",
    )


@router.post("/alerts/{alert_id}/notify", response_model=TaskResponse)
def notify_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправляет уведомление об алерте."""
    from app.models.telematics import Alert
    from app.tasks.email_tasks import send_alert_notification
    
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    task = send_alert_notification.delay(
        user_id=current_user.id,
        alert_id=alert_id,
        title=alert.title,
        description=alert.description or alert.title,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Alert notification queued for alert {alert_id}",
    )


# === Telematics задачи ===

@router.post("/telematics/aggregate-engine-hours/{vehicle_id}", response_model=TaskResponse)
def aggregate_engine_hours(
    vehicle_id: int,
    date: str = None,
    current_user: User = Depends(get_current_user),
):
    """Агрегирует моточасы для техники за день."""
    from app.tasks.telematics_tasks import aggregate_engine_hours as task_func
    
    task = task_func.delay(vehicle_id=vehicle_id, date_str=date)
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Engine hours aggregation queued for vehicle {vehicle_id}",
    )


@router.post("/telematics/cleanup-gps", response_model=TaskResponse)
def cleanup_gps(
    days_old: int = 90,
    current_user: User = Depends(get_current_user),
):
    """Удаляет старые GPS точки."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin only")
    
    from app.tasks.telematics_tasks import cleanup_old_gps_points
    
    task = cleanup_old_gps_points.delay(days_old=days_old)
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"GPS cleanup queued (older than {days_old} days)",
    )


@router.post("/telematics/detect-offline", response_model=TaskResponse)
def detect_offline_vehicles(
    minutes_threshold: int = 60,
    current_user: User = Depends(get_current_user),
):
    """Определяет offline технику."""
    from app.tasks.telematics_tasks import detect_offline_vehicles as task_func
    
    task = task_func.delay(minutes_threshold=minutes_threshold)
    
    return TaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Offline detection queued (>{minutes_threshold} min)",
    )