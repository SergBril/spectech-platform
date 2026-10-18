from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.deps import get_current_user
from app.models.auth import User
from app.services.storage_service import storage_service

router = APIRouter(prefix="/storage", tags=["Storage"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    directory: str = Query(
        default="general", description="Подпапка (chat, downtime, etc.)"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Загрузка файла в хранилище.
    Возвращает URL и метаданные для сохранения в JSONB полях (attachments, photos).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")

    # Здесь можно добавить проверки на MIME-типы и лимит размера (например, 10 МБ)
    result = await storage_service.save_file(file, directory)
    return result
