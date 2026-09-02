"""Тесты для файлового хранилища."""
import pytest
from io import BytesIO

from app.services import storage_service
from app.models.telematics import UploadedFile


@pytest.fixture
def sample_file():
    """Создаёт тестовый файл."""
    content = b"Hello, MinIO! This is a test file."
    return BytesIO(content), "test.txt", len(content)


def test_upload_and_download_file(sample_file):
    """Тест загрузки и скачивания файла."""
    file_obj, filename, size = sample_file
    
    # Загрузка
    result = storage_service.upload_file(
        file_obj=file_obj,
        filename=filename,
        folder="tests",
    )
    
    assert result["size"] == size
    assert result["content_type"] == "text/plain"
    assert "path" in result
    assert "url" in result
    
    # Скачивание
    content = storage_service.get_file(result["path"])
    assert content == b"Hello, MinIO! This is a test file."
    
    # Очистка
    storage_service.delete_file(result["path"])


def test_upload_bytes():
    """Тест загрузки байтов."""
    content = b"Binary content \x00\x01\x02"
    
    result = storage_service.upload_bytes(
        content=content,
        filename="binary.bin",
        folder="tests",
        content_type="application/octet-stream",
    )
    
    assert result["size"] == len(content)
    
    # Проверка
    downloaded = storage_service.get_file(result["path"])
    assert downloaded == content
    
    # Очистка
    storage_service.delete_file(result["path"])


def test_presigned_url(sample_file):
    """Тест генерации подписанного URL."""
    file_obj, filename, _ = sample_file
    
    result = storage_service.upload_file(file_obj, filename, folder="tests")
    
    url = storage_service.generate_presigned_url(result["path"], expires_in=300)
    
    assert url.startswith("http")
    assert "X-Amz-Signature" in url or "Signature" in url
    
    # Очистка
    storage_service.delete_file(result["path"])


def test_list_files(sample_file):
    """Тест списка файлов."""
    file_obj, filename, _ = sample_file
    
    result = storage_service.upload_file(file_obj, filename, folder="test-list")
    
    files = storage_service.list_files(folder="test-list")
    
    assert len(files) >= 1
    assert any(f["path"] == result["path"] for f in files)
    
    # Очистка
    storage_service.delete_file(result["path"])


def test_delete_file(sample_file):
    """Тест удаления файла."""
    file_obj, filename, _ = sample_file
    
    result = storage_service.upload_file(file_obj, filename, folder="tests")
    
    # Удаляем
    deleted = storage_service.delete_file(result["path"])
    assert deleted is True
    
    # Проверяем что файл больше нельзя скачать
    with pytest.raises(Exception):
        storage_service.get_file(result["path"])


def test_storage_stats():
    """Тест статистики хранилища."""
    stats = storage_service.get_storage_stats()
    
    assert "bucket" in stats
    assert stats["bucket"] == "spectech-files"
    assert "total_files" in stats
    assert "total_size_bytes" in stats