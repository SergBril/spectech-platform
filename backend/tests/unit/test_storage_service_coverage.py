"""Coverage tests for storage_service."""
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def mock_s3():
    return MagicMock()


@pytest.fixture(autouse=True)
def patch_s3_client(mock_s3):
    with patch("app.services.storage_service._get_s3_client", return_value=mock_s3), \
         patch("app.services.storage_service.ensure_bucket_exists"):
        yield mock_s3


class TestEnsureBucketExists:
    """Cover ensure_bucket_exists (lines 37-51)."""

    def test_bucket_exists(self):
        from app.services.storage_service import ensure_bucket_exists
        with patch("app.services.storage_service._get_s3_client") as mock_get:
            s3 = MagicMock()
            mock_get.return_value = s3
            s3.head_bucket.return_value = {}
            ensure_bucket_exists()
            s3.create_bucket.assert_not_called()

    def test_bucket_404_creates(self):
        from app.services.storage_service import ensure_bucket_exists
        with patch("app.services.storage_service._get_s3_client") as mock_get:
            s3 = MagicMock()
            mock_get.return_value = s3
            error_response = {"Error": {"Code": "404"}}
            s3.head_bucket.side_effect = ClientError(error_response, "HeadBucket")
            ensure_bucket_exists()
            s3.create_bucket.assert_called_once()

    def test_other_error_raises(self):
        from app.services.storage_service import ensure_bucket_exists
        with patch("app.services.storage_service._get_s3_client") as mock_get:
            s3 = MagicMock()
            mock_get.return_value = s3
            error_response = {"Error": {"Code": "500"}}
            s3.head_bucket.side_effect = ClientError(error_response, "HeadBucket")
            with pytest.raises(ClientError):
                ensure_bucket_exists()


class TestUploadFile:
    """Cover upload_file (lines 53-122)."""

    def test_success(self, mock_s3):
        from app.services.storage_service import upload_file
        file_obj = BytesIO(b"test content")
        result = upload_file(file_obj, "test.pdf", folder="docs")
        assert result["size"] == 12
        assert result["content_type"] == "application/pdf"
        assert result["original_filename"] == "test.pdf"
        assert "path" in result
        assert "url" in result
        mock_s3.put_object.assert_called_once()

    def test_auto_content_type(self, mock_s3):
        from app.services.storage_service import upload_file
        file_obj = BytesIO(b"data")
        result = upload_file(file_obj, "image.png")
        assert result["content_type"] == "image/png"

    def test_unknown_extension(self, mock_s3):
        from app.services.storage_service import upload_file
        file_obj = BytesIO(b"data")
        result = upload_file(file_obj, "noext")
        assert ".bin" in result["path"]

    def test_upload_error_raises(self, mock_s3):
        from app.services.storage_service import upload_file
        mock_s3.put_object.side_effect = ClientError({"Error": {"Code": "500"}}, "PutObject")
        file_obj = BytesIO(b"data")
        with pytest.raises(ClientError):
            upload_file(file_obj, "test.pdf")


class TestUploadBytes:
    """Cover upload_bytes (lines 124-134)."""

    def test_delegates_to_upload_file(self, mock_s3):
        from app.services.storage_service import upload_bytes
        result = upload_bytes(b"hello", "test.txt", content_type="text/plain")
        assert result["size"] == 5
        mock_s3.put_object.assert_called_once()


class TestGetFile:
    """Cover get_file (lines 136-153)."""

    def test_success(self, mock_s3):
        from app.services.storage_service import get_file
        mock_s3.get_object.return_value = {"Body": BytesIO(b"file content")}
        result = get_file("uploads/test.pdf")
        assert result == b"file content"

    def test_error_raises(self, mock_s3):
        from app.services.storage_service import get_file
        mock_s3.get_object.side_effect = ClientError({"Error": {"Code": "404"}}, "GetObject")
        with pytest.raises(ClientError):
            get_file("nonexistent.pdf")


class TestDeleteFile:
    """Cover delete_file (lines 155-165)."""

    def test_success(self, mock_s3):
        from app.services.storage_service import delete_file
        assert delete_file("uploads/test.pdf") is True
        mock_s3.delete_object.assert_called_once()

    def test_error_returns_false(self, mock_s3):
        from app.services.storage_service import delete_file
        mock_s3.delete_object.side_effect = ClientError({"Error": {"Code": "500"}}, "DeleteObject")
        assert delete_file("uploads/test.pdf") is False


class TestGeneratePresignedUrl:
    """Cover generate_presigned_url (lines 167-180)."""

    def test_success_replaces_minio(self, mock_s3):
        from app.services.storage_service import generate_presigned_url
        mock_s3.generate_presigned_url.return_value = "http://minio:9000/bucket/key"
        url = generate_presigned_url("uploads/test.pdf")
        assert "localhost:9000" in url
        assert "minio:9000" not in url

    def test_error_raises(self, mock_s3):
        from app.services.storage_service import generate_presigned_url
        mock_s3.generate_presigned_url.side_effect = ClientError({"Error": {"Code": "500"}}, "Sign")
        with pytest.raises(ClientError):
            generate_presigned_url("test.pdf")


class TestListFiles:
    """Cover list_files (lines 182-204)."""

    def test_with_files(self, mock_s3):
        from datetime import UTC, datetime
        from app.services.storage_service import list_files
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "a.pdf", "Size": 100, "LastModified": datetime(2026, 1, 1, tzinfo=UTC)},
                {"Key": "b.pdf", "Size": 200, "LastModified": datetime(2026, 1, 2, tzinfo=UTC)},
            ]
        }
        result = list_files("uploads")
        assert len(result) == 2
        assert result[0]["path"] == "a.pdf"

    def test_empty(self, mock_s3):
        from app.services.storage_service import list_files
        mock_s3.list_objects_v2.return_value = {}
        result = list_files()
        assert result == []

    def test_error_returns_empty(self, mock_s3):
        from app.services.storage_service import list_files
        mock_s3.list_objects_v2.side_effect = ClientError({"Error": {"Code": "500"}}, "List")
        result = list_files()
        assert result == []


class TestGetStorageStats:
    """Cover get_storage_stats (lines 206-228)."""

    def test_success(self, mock_s3):
        from app.services.storage_service import get_storage_stats
        mock_s3.list_objects_v2.return_value = {
            "Contents": [{"Size": 1048576}, {"Size": 2097152}]
        }
        stats = get_storage_stats()
        assert stats["total_files"] == 2
        assert stats["total_size_mb"] == 3.0

    def test_error_returns_zero(self, mock_s3):
        from app.services.storage_service import get_storage_stats
        mock_s3.list_objects_v2.side_effect = Exception("Connection failed")
        stats = get_storage_stats()
        assert stats["total_files"] == 0
        assert "error" in stats


class TestUploadBytesWithMetadata:
    """Cover upload_bytes_with_metadata (lines 230-end)."""

    def test_delegates(self, mock_s3):
        from app.services.storage_service import upload_bytes_with_metadata
        result = upload_bytes_with_metadata(b"pdf data", "doc.pdf")
        assert result["size"] == 8
        assert result["content_type"] == "application/pdf"
