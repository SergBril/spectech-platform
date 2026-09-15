"""Сервис для работы с объектным хранилищем (MinIO/S3)."""

import logging
import mimetypes
import uuid
from datetime import UTC, datetime
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("spectech.storage")

# Конфигурация (в production — через переменные окружения)
MINIO_ENDPOINT = "minio:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_BUCKET = "spectech-docs"
MINIO_USE_SSL = False


def _get_s3_client():
    """Создаёт S3 клиент для MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=f"{'https' if MINIO_USE_SSL else 'http'}://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name="ru-central1",
    )


def ensure_bucket_exists():
    """Создаёт bucket если его нет."""
    s3 = _get_s3_client()
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
        logger.info(f"Bucket '{MINIO_BUCKET}' already exists")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404":
            logger.info(f"Creating bucket '{MINIO_BUCKET}'")
            s3.create_bucket(Bucket=MINIO_BUCKET)
        else:
            logger.error(f"Error checking bucket: {e}")
            raise


def upload_file(
    file_obj: BinaryIO,
    filename: str,
    folder: str = "uploads",
    content_type: str | None = None,
) -> dict:
    """
    Загружает файл в хранилище.

    Args:
        file_obj: Файловый объект
        filename: Исходное имя файла
        folder: Папка в bucket (префикс)
        content_type: MIME тип (автоопределение если None)

    Returns:
        dict с path, url, size, content_type
    """
    ensure_bucket_exists()
    s3 = _get_s3_client()

    # Генерируем уникальное имя
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    storage_path = f"{folder}/{datetime.now(UTC).strftime('%Y/%m/%d')}/{unique_name}"

    # Определяем MIME тип
    if not content_type:
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    try:
        # Получаем содержимое для определения размера
        content = file_obj.read()
        size = len(content)
        file_obj.seek(0)

        # Транслитерируем имя файла для метаданных S3 (S3 требует ASCII)
        import re

        ascii_filename = re.sub(r"[^\x00-\x7F]+", "", filename) or "file.pdf"

        s3.put_object(
            Bucket=MINIO_BUCKET,
            Key=storage_path,
            Body=content,
            ContentType=content_type,
            Metadata={
                "original-filename": ascii_filename,  # Только ASCII
                "uploaded-at": datetime.now(UTC).isoformat(),
            },
        )

        # Публичный URL (если bucket публичный)
        # Для генерации URL, доступных из браузера, используем localhost
        PUBLIC_ENDPOINT = "localhost:9000"  # Минимальное изменение для dev-среды
        public_url = f"{'https' if MINIO_USE_SSL else 'http'}://{PUBLIC_ENDPOINT}/{MINIO_BUCKET}/{storage_path}"

        logger.info(f"File uploaded: {storage_path} ({size} bytes)")

        return {
            "path": storage_path,
            "url": public_url,
            "size": size,
            "content_type": content_type,
            "original_filename": filename,
        }
    except ClientError as e:
        logger.error(f"Upload failed: {e}")
        raise


def upload_bytes(
    content: bytes,
    filename: str,
    folder: str = "uploads",
    content_type: str | None = None,
) -> dict:
    """Загружает байты в хранилище."""
    from io import BytesIO

    return upload_file(BytesIO(content), filename, folder, content_type)


def get_file(storage_path: str) -> bytes:
    """
    Скачивает файл из хранилища.

    Args:
        storage_path: Путь в хранилище (возвращается upload_file)

    Returns:
        bytes содержимое файла
    """
    s3 = _get_s3_client()
    try:
        response = s3.get_object(Bucket=MINIO_BUCKET, Key=storage_path)
        return response["Body"].read()
    except ClientError as e:
        logger.error(f"Download failed for {storage_path}: {e}")
        raise


def delete_file(storage_path: str) -> bool:
    """Удаляет файл из хранилища."""
    s3 = _get_s3_client()
    try:
        s3.delete_object(Bucket=MINIO_BUCKET, Key=storage_path)
        logger.info(f"File deleted: {storage_path}")
        return True
    except ClientError as e:
        logger.error(f"Delete failed for {storage_path}: {e}")
        return False


def generate_presigned_url(storage_path: str, expires_in: int = 3600) -> str:
    s3 = _get_s3_client()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": MINIO_BUCKET, "Key": storage_path},
            ExpiresIn=expires_in,
        )
        # Заменяем внутренний Docker-адрес на публичный
        return url.replace("minio:9000", "localhost:9000")
    except ClientError as e:
        logger.error(f"Presigned URL generation failed: {e}")
        raise


def list_files(folder: str = "", max_keys: int = 100) -> list:
    """Список файлов в папке."""
    s3 = _get_s3_client()
    try:
        response = s3.list_objects_v2(
            Bucket=MINIO_BUCKET,
            Prefix=folder,
            MaxKeys=max_keys,
        )
        files = []
        for obj in response.get("Contents", []):
            files.append(
                {
                    "path": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
            )
        return files
    except ClientError as e:
        logger.error(f"List failed: {e}")
        return []


def get_storage_stats() -> dict:
    """Статистика хранилища."""
    try:
        s3 = _get_s3_client()
        response = s3.list_objects_v2(Bucket=MINIO_BUCKET)
        files = response.get("Contents", [])
        total_size = sum(obj["Size"] for obj in files)
        return {
            "bucket": MINIO_BUCKET,
            "total_files": len(files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return {
            "bucket": MINIO_BUCKET,
            "total_files": 0,
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "error": str(e),
        }


def upload_bytes_with_metadata(
    content: bytes,
    filename: str,
    folder: str = "uploads",
    content_type: str = "application/pdf",
) -> dict:
    """Загружает байты в MinIO и возвращает метаданные."""
    from io import BytesIO

    return upload_file(BytesIO(content), filename, folder, content_type)
