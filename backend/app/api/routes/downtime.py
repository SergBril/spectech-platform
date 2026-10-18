"""API endpoints для учёта простоев техники."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids
from app.core.db import get_db
from app.models.auth import User
from app.models.downtime import DowntimeStatus, FaultParty
from app.schemas.downtime import (
    DowntimeCreate,
    DowntimeEnd,
    DowntimeRead,
    DowntimeReject,
    DowntimeStats,
)
from app.services.downtime_service import downtime_service

router = APIRouter()


@router.post("", response_model=DowntimeRead, status_code=201)
def create_downtime(
    payload: DowntimeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Зафиксировать простой техники."""
    try:
        event = downtime_service.create_downtime(
            db=db,
            shift_task_id=payload.shift_task_id,
            vehicle_id=payload.vehicle_id,
            started_at=payload.started_at,
            ended_at=payload.ended_at,
            cause_category=payload.cause_category,
            fault_party=payload.fault_party,
            description=payload.description,
            photos=payload.photos,
            company_id=company_id,
            created_by=current_user.id,
        )
        return event
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("", response_model=list[DowntimeRead])
def list_downtimes(
    shift_task_id: int | None = None,
    vehicle_id: int | None = None,
    status: DowntimeStatus | None = None,
    fault_party: FaultParty | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_ids: list[int] = Depends(get_user_company_ids),
):
    """Список простоев с фильтрами."""
    from sqlalchemy import select

    from app.models.downtime import DowntimeEvent

    stmt = select(DowntimeEvent).where(DowntimeEvent.company_id.in_(company_ids))

    if shift_task_id:
        stmt = stmt.where(DowntimeEvent.shift_task_id == shift_task_id)
    if vehicle_id:
        stmt = stmt.where(DowntimeEvent.vehicle_id == vehicle_id)
    if status:
        stmt = stmt.where(DowntimeEvent.status == status)
    if fault_party:
        stmt = stmt.where(DowntimeEvent.fault_party == fault_party)

    stmt = stmt.order_by(DowntimeEvent.started_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.get("/stats", response_model=DowntimeStats)
def get_downtime_stats(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика по простоям для компании."""
    return downtime_service.get_stats(
        db=db,
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
    )


from fastapi import File, UploadFile
from pydantic import BaseModel

from app.services import storage_service


class PhotoUploadResponse(BaseModel):
    """Ответ после загрузки фото простоя."""

    path: str
    url: str
    size: int
    content_type: str
    original_filename: str


@router.post("/upload", response_model=PhotoUploadResponse, status_code=201)
async def upload_downtime_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Загружает фото-доказательство простоя в MinIO.
    Полученный `url` затем передаётся в `POST /downtime` в поле `photos`.
    """
    # Валидация типа файла (только изображения)
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
        )

    # Загружаем в MinIO
    try:
        result = storage_service.upload_file(
            file_obj=file.file,
            filename=file.filename or "unknown.jpg",
            folder=f"downtime/{company_id}",
            content_type=file.content_type,
        )
        return PhotoUploadResponse(**result)
    except Exception as e:
        logger.error(f"Photo upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.post(
    "/upload-multiple", response_model=list[PhotoUploadResponse], status_code=201
)
async def upload_multiple_downtime_photos(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Загружает несколько фото-доказательств простоя в MinIO за один запрос.
    """
    # Валидация типов файлов
    allowed_types = ["image/jpeg", "image/png", "image/webp"]

    results = []
    for file in files:
        if file.content_type not in allowed_types:
            logger.warning(
                f"Skipping invalid file type: {file.filename} ({file.content_type})"
            )
            continue

        try:
            result = storage_service.upload_file(
                file_obj=file.file,
                filename=file.filename or "unknown.jpg",
                folder=f"downtime/{company_id}",
                content_type=file.content_type,
            )
            results.append(PhotoUploadResponse(**result))
        except Exception as e:
            logger.error(f"Photo upload failed for {file.filename}: {e}")
            continue

    if not results:
        raise HTTPException(
            status_code=400,
            detail="No valid files uploaded. Check file types (allowed: jpeg, png, webp)",
        )

    return results


@router.get("/{downtime_id}", response_model=DowntimeRead)
def get_downtime(
    downtime_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить простой по ID."""
    from app.models.downtime import DowntimeEvent

    event = db.get(DowntimeEvent, downtime_id)
    if not event or event.company_id != company_id:
        raise HTTPException(status_code=404, detail="Downtime not found")
    return event


@router.post("/{downtime_id}/end", response_model=DowntimeRead)
def end_downtime(
    downtime_id: int,
    payload: DowntimeEnd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Завершить простой и пересчитать сумму."""
    from app.models.downtime import DowntimeEvent

    event = db.get(DowntimeEvent, downtime_id)
    if not event or event.company_id != company_id:
        raise HTTPException(status_code=404, detail="Downtime not found")

    try:
        return downtime_service.end_downtime(
            db=db,
            downtime_id=downtime_id,
            ended_at=payload.ended_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{downtime_id}/approve", response_model=DowntimeRead)
def approve_downtime(
    downtime_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Подтвердить простой (pending → approved)."""
    from app.models.downtime import DowntimeEvent

    event = db.get(DowntimeEvent, downtime_id)
    if not event or event.company_id != company_id:
        raise HTTPException(status_code=404, detail="Downtime not found")

    try:
        return downtime_service.approve_downtime(
            db=db,
            downtime_id=downtime_id,
            approved_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{downtime_id}/reject", response_model=DowntimeRead)
def reject_downtime(
    downtime_id: int,
    payload: DowntimeReject | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отклонить простой (pending → rejected)."""
    from app.models.downtime import DowntimeEvent

    event = db.get(DowntimeEvent, downtime_id)
    if not event or event.company_id != company_id:
        raise HTTPException(status_code=404, detail="Downtime not found")

    try:
        return downtime_service.reject_downtime(
            db=db,
            downtime_id=downtime_id,
            rejected_by=current_user.id,
            reason=payload.reason if payload else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
