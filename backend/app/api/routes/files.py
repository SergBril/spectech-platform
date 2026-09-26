"""API для работы с файлами."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.telematics import UploadedFile
from app.services import storage_service

router = APIRouter()


class FileRead(BaseModel):
    id: int
    original_filename: str
    storage_path: str
    content_type: str
    size_bytes: int
    file_category: str
    vehicle_id: int | None = None
    invoice_id: int | None = None
    act_id: int | None = None
    contractor_id: int | None = None
    uploaded_by: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    id: int
    original_filename: str
    storage_path: str
    content_type: str
    size_bytes: int
    url: str
    presigned_url: str


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    file_category: str = Query(default="other"),
    vehicle_id: int | None = Query(default=None),
    invoice_id: int | None = Query(default=None),
    act_id: int | None = Query(default=None),
    contractor_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загружает файл в хранилище."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Определяем папку по категории
    folder_map = {
        "vehicle_photo": "vehicles/photos",
        "invoice_pdf": "finance/invoices",
        "act_pdf": "finance/acts",
        "payout_pdf": "finance/payouts",
        "contractor_doc": "contractors/docs",
    }
    folder = folder_map.get(file_category, "uploads")

    # Загружаем в MinIO
    try:
        content = await file.read()
        upload_result = storage_service.upload_bytes(
            content=content,
            filename=file.filename,
            folder=folder,
            content_type=file.content_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")

    # Сохраняем метаданные в БД
    uploaded_file = UploadedFile(
        original_filename=file.filename,
        storage_path=upload_result["path"],
        content_type=upload_result["content_type"],
        size_bytes=upload_result["size"],
        file_category=file_category,
        vehicle_id=vehicle_id,
        invoice_id=invoice_id,
        act_id=act_id,
        contractor_id=contractor_id,
        uploaded_by=current_user.id,
        company_id=current_user.company_id,
    )

    # 🆕 Дедупликация: удаляем старые версии того же документа
    if act_id:
        old_files = db.scalars(
            select(UploadedFile).where(
                UploadedFile.file_category == file_category,
                UploadedFile.act_id == act_id,
                UploadedFile.company_id == current_user.company_id,
            )
        ).all()
        for old_file in old_files:
            try:
                storage_service.delete_file(old_file.storage_path)
            except Exception:
                pass
            db.delete(old_file)

    if invoice_id and not act_id:
        old_files = db.scalars(
            select(UploadedFile).where(
                UploadedFile.file_category == file_category,
                UploadedFile.invoice_id == invoice_id,
                UploadedFile.company_id == current_user.company_id,
            )
        ).all()
        for old_file in old_files:
            try:
                storage_service.delete_file(old_file.storage_path)
            except Exception:
                pass
            db.delete(old_file)

    db.add(uploaded_file)
    db.commit()
    db.refresh(uploaded_file)

    # Генерируем подписанный URL
    presigned_url = storage_service.generate_presigned_url(
        upload_result["path"], expires_in=3600
    )

    return FileUploadResponse(
        id=uploaded_file.id,
        original_filename=uploaded_file.original_filename,
        storage_path=uploaded_file.storage_path,
        content_type=uploaded_file.content_type,
        size_bytes=uploaded_file.size_bytes,
        url=upload_result["url"],
        presigned_url=presigned_url,
    )


@router.get("/download/{file_id}")
def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Скачивает файл из хранилища."""
    uploaded_file = db.get(UploadedFile, file_id)
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = storage_service.get_file(uploaded_file.storage_path)
        return Response(
            content=content,
            media_type=uploaded_file.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{uploaded_file.original_filename}"'
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")


@router.get("/presigned-url/{file_id}")
def get_presigned_url(
    file_id: int,
    expires_in: int = Query(default=3600, ge=60, le=86400),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Возвращает временный подписанный URL."""
    uploaded_file = db.get(UploadedFile, file_id)
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")

    url = storage_service.generate_presigned_url(
        uploaded_file.storage_path, expires_in=expires_in
    )
    return {
        "file_id": file_id,
        "presigned_url": url,
        "expires_in_seconds": expires_in,
    }


@router.get("/", response_model=list[FileRead])
def list_files(
    file_category: str | None = None,
    vehicle_id: int | None = None,
    invoice_id: int | None = None,
    act_id: int | None = None,  # 🆕 ДОБАВЛЕНО
    contractor_id: int | None = None,  # 🆕 ДОБАВЛЕНО
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список загруженных файлов с фильтрацией по сущностям."""
    stmt = select(UploadedFile).where(
        UploadedFile.company_id == current_user.company_id
    )

    if file_category:
        stmt = stmt.where(UploadedFile.file_category == file_category)
    if vehicle_id:
        stmt = stmt.where(UploadedFile.vehicle_id == vehicle_id)
    if invoice_id:
        stmt = stmt.where(UploadedFile.invoice_id == invoice_id)
    if act_id:  # 🆕
        stmt = stmt.where(UploadedFile.act_id == act_id)  # 🆕
    if contractor_id:  # 🆕
        stmt = stmt.where(UploadedFile.contractor_id == contractor_id)  # 🆕

    stmt = stmt.order_by(UploadedFile.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удаляет файл из хранилища и БД."""
    uploaded_file = db.get(UploadedFile, file_id)
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Удаляем из хранилища
    storage_service.delete_file(uploaded_file.storage_path)

    # Удаляем из БД
    db.delete(uploaded_file)
    db.commit()


@router.get("/stats")
def storage_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статистика хранилища."""
    stats = storage_service.get_storage_stats()

    # Добавляем статистику по БД
    from sqlalchemy import func

    db_files_count = db.query(func.count(UploadedFile.id)).scalar() or 0

    return {
        "storage": stats,
        "database": {
            "uploaded_files_count": db_files_count,
        },
    }
