from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.deps import get_current_company_id, get_current_user
from app.models.auth import User
from app.services import storage_service

router = APIRouter(prefix="/storage", tags=["storage"])

ALLOWED_DIRECTORIES = {"general", "chat", "downtime"}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    directory: str = Query(
        default="general", description="Подпапка: general, chat или downtime"
    ),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """
    Загрузка файла в хранилище (только своей компании).

    Путь привязан к компании: company_{id}/{directory}/...
    Возвращает URL и метаданные для сохранения в JSONB полях (attachments, photos).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")

    if directory not in ALLOWED_DIRECTORIES:
        raise HTTPException(status_code=400, detail="Invalid directory")

    result = storage_service.upload_file(
        file_obj=file.file,
        filename=file.filename,
        folder=f"company_{company_id}/{directory}",
        content_type=file.content_type,
    )
    return result
