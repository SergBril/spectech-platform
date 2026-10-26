"""Модуль documents для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.shift import DocumentArchive
from app.models.finance import Act
from app.models.catalog import Vehicle
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from app.models.shift import DocumentArchive
from app.models.finance import Act
from app.models.catalog import Vehicle

router = APIRouter()

def search_document_archive(
    q: str | None = Query(default=None, description="Полнотекстовый поиск"),
    doc_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Поиск по архиву документов с полнотекстовым поиском."""
    from datetime import date as date_type
    from sqlalchemy import func, or_
    from app.models.shift import DocumentArchive

    stmt = select(DocumentArchive).where(DocumentArchive.company_id == company_id)

    if q:
        search_pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                DocumentArchive.title.ilike(search_pattern),
                DocumentArchive.doc_number.ilike(search_pattern),
                DocumentArchive.content_text.ilike(search_pattern),
            )
        )
    if doc_type:
        stmt = stmt.where(DocumentArchive.doc_type == doc_type)
    if date_from:
        stmt = stmt.where(DocumentArchive.created_at >= date_type.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(DocumentArchive.created_at <= date_type.fromisoformat(date_to))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(DocumentArchive.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    docs = db.execute(stmt).scalars().all()

    items = [{
        "id": d.id, "doc_type": d.doc_type, "doc_number": d.doc_number,
        "title": d.title, "file_path": d.file_path,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "related_act_id": d.related_act_id,
    } for d in docs]

    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page if per_page > 0 else 0}



async def add_to_archive(
    title: str = Body(...),
    doc_type: str = Body(default="report"),
    doc_number: str = Body(default=""),
    content_text: str = Body(default=""),
    related_act_id: int | None = Body(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Загрузить документ в архив."""
    import os
    from datetime import datetime
    from app.models.shift import DocumentArchive

    file_path = None
    if file:
        upload_dir = os.path.join("uploads", "archive", str(company_id))
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(file.filename or "doc")[1]
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())
        file_path = filepath

    doc = DocumentArchive(
        company_id=company_id, doc_type=doc_type, doc_number=doc_number,
        title=title, content_text=content_text, file_path=file_path,
        related_act_id=related_act_id, uploaded_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "message": "Документ добавлен в архив"}



def auto_index_acts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Автоматически добавить все акты компании в архив документов."""
    from app.models.shift import DocumentArchive

    acts = db.execute(select(Act).where(Act.company_id == company_id)).scalars().all()
    indexed = 0

    for act in acts:
        existing = db.execute(
            select(DocumentArchive).where(
                DocumentArchive.company_id == company_id,
                DocumentArchive.related_act_id == act.id,
            )
        ).scalar_one_or_none()
        if existing:
            continue

        vehicle = db.get(Vehicle, act.vehicle_id) if act.vehicle_id else None
        vname = vehicle.name if vehicle else ""
        content = f"Акт {getattr(act, 'document_number', None) or f'ACT-{act.id}'} от {act.act_date}. Техника: {vname}. Часов: {act.hours_worked}. Сумма: {act.total_amount} руб."

        doc = DocumentArchive(
            company_id=company_id, doc_type="act",
            doc_number=getattr(act, 'document_number', None) or f'ACT-{act.id}', title=f"Акт {getattr(act, 'document_number', None) or f'ACT-{act.id}'} от {act.act_date}",
            content_text=content, related_act_id=act.id,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        indexed += 1

    db.commit()
    return {"indexed": indexed, "message": f"Проиндексировано {indexed} актов"}



