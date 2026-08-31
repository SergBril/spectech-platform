from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.contractor import Contractor
from app.models.finance import Act, DocumentStatus
from app.schemas.finance import ActCreate, ActRead, ActSign
from app.services.finance_service import generate_document_number
from app.services.pdf_service import generate_act_pdf

router = APIRouter()


@router.get("", response_model=List[ActRead])
def list_acts(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список актов."""
    stmt = select(Act)
    
    if status_filter:
        stmt = stmt.where(Act.status == status_filter)
    
    stmt = stmt.order_by(Act.created_at.desc()).offset(offset).limit(limit)
    return db.scalars(stmt).all()


@router.post("", response_model=ActRead, status_code=201)
def create_act(
    payload: ActCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать акт выполненных работ."""
    act = Act(
        document_number=generate_document_number(db, "ACT"),
        request_id=payload.request_id,
        client_id=payload.client_id,
        company_id=current_user.company_id,
        act_date=payload.act_date,
        total_amount=payload.total_amount,
        status=DocumentStatus.draft,
        comment=payload.comment,
        created_by=current_user.id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


@router.get("/{act_id}", response_model=ActRead)
def get_act(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить акт по ID."""
    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")
    return act


@router.post("/{act_id}/sign", response_model=ActRead)
def sign_act(
    act_id: int,
    payload: ActSign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Подписать акт (со стороны клиента или исполнителя)."""
    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")
    
    now = datetime.now(timezone.utc)
    
    if payload.signed_by == "client":
        if act.signed_by_client_at:
            raise HTTPException(status_code=409, detail="Act already signed by client")
        act.signed_by_client_at = now
    elif payload.signed_by == "executor":
        if act.signed_by_executor_at:
            raise HTTPException(status_code=409, detail="Act already signed by executor")
        act.signed_by_executor_at = now
    
    # Если обе стороны подписали — акт завершён
    if act.signed_by_client_at and act.signed_by_executor_at:
        act.status = DocumentStatus.paid
    
    db.commit()
    db.refresh(act)
    return act


@router.get("/{act_id}/pdf", response_class=FileResponse)
def download_act_pdf(
    act_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Скачать акт в формате PDF."""
    act = db.get(Act, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Act not found")
    
    client = db.get(Contractor, act.client_id)
    client_name = client.name if client else ""
    
    pdf_path = generate_act_pdf(act, client_name=client_name)
    
    # Сохраняем путь к PDF в модели
    relative_path = f"documents/{Path(pdf_path).name}"
    if act.pdf_url != relative_path:
        act.pdf_url = relative_path
        db.commit()
    
    return FileResponse(
        path=pdf_path,
        filename=f"act_{act.document_number}.pdf",
        media_type="application/pdf",
    )