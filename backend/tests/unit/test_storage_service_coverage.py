"""Coverage tests for storage_service."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest


class TestEnsureBucketExists:
    """Cover ensure_bucket_exists (lines 37-51)."""

    def test_bucket_exists(self):
        from app.services.storage_service import ensure_bucket_exists

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.head_bucket.return_value = {}
            ensure_bucket_exists()
            mock_s3.head_bucket.assert_called_once()
            mock_s3.create_bucket.assert_not_called()

    def test_bucket_created(self):
        from botocore.exceptions import ClientError

        from app.services.storage_service import ensure_bucket_exists

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.head_bucket.side_effect = ClientError(
                {"Error": {"Code": "404"}}, "head_bucket"
            )
            ensure_bucket_exists()
            mock_s3.create_bucket.assert_called_once()

    def test_other_error_raises(self):
        from botocore.exceptions import ClientError

        from app.services.storage_service import ensure_bucket_exists

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.head_bucket.side_effect = ClientError(
                {"Error": {"Code": "500"}}, "head_bucket"
            )
            with pytest.raises(ClientError):
                ensure_bucket_exists()


class TestUploadFile:
    """Cover upload_file (lines 53-122)."""

    def test_success(self):
        from app.services.storage_service import upload_file

        with (
            patch("app.services.storage_service.ensure_bucket_exists"),
            patch("app.services.storage_service._get_s3_client") as mock_client,
        ):
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            file_obj = BytesIO(b"test content")
            result = upload_file(file_obj, "test.pdf", folder="docs")
            assert result["size"] == 12
            assert result["content_type"] == "application/pdf"
            assert "path" in result
            assert "url" in result
            mock_s3.put_object.assert_called_once()

    def test_auto_content_type(self):
        from app.services.storage_service import upload_file

        with (
            patch("app.services.storage_service.ensure_bucket_exists"),
            patch("app.services.storage_service._get_s3_client") as mock_client,
        ):
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            file_obj = BytesIO(b"data")
            result = upload_file(file_obj, "image.png")
            assert result["content_type"] == "image/png"

    def test_upload_failure_raises(self):
        from botocore.exceptions import ClientError

        from app.services.storage_service import upload_file

        with (
            patch("app.services.storage_service.ensure_bucket_exists"),
            patch("app.services.storage_service._get_s3_client") as mock_client,
        ):
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.put_object.side_effect = ClientError(
                {"Error": {"Code": "500"}}, "put"
            )
            with pytest.raises(ClientError):
                upload_file(BytesIO(b"data"), "test.pdf")


class TestUploadBytes:
    """Cover upload_bytes (lines 124-134)."""

    def test_delegates_to_upload_file(self):
        from app.services.storage_service import upload_bytes

        with patch(
            "app.services.storage_service.upload_file", return_value={"path": "x"}
        ) as mock_up:
            result = upload_bytes(b"data", "test.pdf")
            assert result["path"] == "x"
            mock_up.assert_called_once()


class TestGetFile:
    """Cover get_file (lines 136-153)."""

    def test_success(self):
        from app.services.storage_service import get_file

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            body = MagicMock()
            body.read.return_value = b"file content"
            mock_s3.get_object.return_value = {"Body": body}
            result = get_file("uploads/test.pdf")
            assert result == b"file content"

    def test_failure_raises(self):
        from botocore.exceptions import ClientError

        from app.services.storage_service import get_file

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.get_object.side_effect = ClientError(
                {"Error": {"Code": "404"}}, "get"
            )
            with pytest.raises(ClientError):
                get_file("nonexistent.pdf")


class TestDeleteFile:
    """Cover delete_file (lines 155-165)."""

    def test_success(self):
        from app.services.storage_service import delete_file

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            assert delete_file("uploads/test.pdf") is True

    def test_failure_returns_false(self):
        from botocore.exceptions import ClientError

        from app.services.storage_service import delete_file

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.delete_object.side_effect = ClientError(
                {"Error": {"Code": "500"}}, "del"
            )
            assert delete_file("uploads/test.pdf") is False


class TestGeneratePresignedUrl:
    """Cover generate_presigned_url (lines 167-180)."""

    def test_success(self):
        from app.services.storage_service import generate_presigned_url

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.generate_presigned_url.return_value = "http://minio:9000/bucket/key"
            result = generate_presigned_url("uploads/test.pdf")
            assert "localhost:9000" in result

    def test_failure_raises(self):
        from botocore.exceptions import ClientError

        from app.services.storage_service import generate_presigned_url

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.generate_presigned_url.side_effect = ClientError(
                {"Error": {"Code": "500"}}, "url"
            )
            with pytest.raises(ClientError):
                generate_presigned_url("uploads/test.pdf")


class TestListFiles:
    """Cover list_files (lines 182-204)."""

    def test_success(self):
        from datetime import UTC, datetime

        from app.services.storage_service import list_files

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.list_objects_v2.return_value = {
                "Contents": [
                    {"Key": "a.pdf", "Size": 100, "LastModified": datetime.now(UTC)},
                ]
            }
            result = list_files("uploads")
            assert len(result) == 1
            assert result[0]["path"] == "a.pdf"

    def test_empty(self):
        from app.services.storage_service import list_files

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.list_objects_v2.return_value = {}
            result = list_files()
            assert result == []

    def test_error_returns_empty(self):
        from botocore.exceptions import ClientError

        from app.services.storage_service import list_files

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.list_objects_v2.side_effect = ClientError(
                {"Error": {"Code": "500"}}, "list"
            )
            result = list_files()
            assert result == []


class TestGetStorageStats:
    """Cover get_storage_stats (lines 206-228)."""

    def test_success(self):
        from app.services.storage_service import get_storage_stats

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            mock_s3.list_objects_v2.return_value = {
                "Contents": [{"Size": 1024}, {"Size": 2048}]
            }
            result = get_storage_stats()
            assert result["total_files"] == 2
            assert result["total_size_bytes"] == 3072

    def test_error_returns_zeros(self):
        from app.services.storage_service import get_storage_stats

        with patch("app.services.storage_service._get_s3_client") as mock_client:
            mock_client.side_effect = Exception("Connection refused")
            result = get_storage_stats()
            assert result["total_files"] == 0
            assert "error" in result


class TestUploadBytesWithMetadata:
    """Cover upload_bytes_with_metadata (lines 230-end)."""

    def test_delegates(self):
        from app.services.storage_service import upload_bytes_with_metadata

        with patch(
            "app.services.storage_service.upload_file", return_value={"path": "x"}
        ):
            result = upload_bytes_with_metadata(b"data", "doc.pdf")
            assert result["path"] == "x"
