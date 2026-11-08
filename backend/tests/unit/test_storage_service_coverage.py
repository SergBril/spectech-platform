"""Coverage tests for storage_service."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def _make_s3():
    return MagicMock()


class TestEnsureBucketExists:
    """Cover ensure_bucket_exists (lines 37-51)."""

    def test_bucket_exists(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.head_bucket.return_value = {}
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            storage_service.ensure_bucket_exists()
        s3.create_bucket.assert_not_called()

    def test_bucket_404_creates(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            storage_service.ensure_bucket_exists()
        s3.create_bucket.assert_called_once()

    def test_other_error_raises(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "HeadBucket"
        )
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            with pytest.raises(ClientError):
                storage_service.ensure_bucket_exists()


class TestUploadFile:
    """Cover upload_file (lines 53-122)."""

    def _run(self, s3, *args, **kwargs):
        from app.services import storage_service

        with (
            patch.object(storage_service, "_get_s3_client", return_value=s3),
            patch.object(storage_service, "ensure_bucket_exists"),
        ):
            return storage_service.upload_file(*args, **kwargs)

    def test_success(self):
        s3 = _make_s3()
        result = self._run(s3, BytesIO(b"test content"), "test.pdf", folder="docs")
        assert result["size"] == 12
        assert result["content_type"] == "application/pdf"
        s3.put_object.assert_called_once()

    def test_auto_content_type(self):
        s3 = _make_s3()
        result = self._run(s3, BytesIO(b"data"), "image.png")
        assert result["content_type"] == "image/png"

    def test_unknown_extension(self):
        s3 = _make_s3()
        result = self._run(s3, BytesIO(b"data"), "noext")
        assert ".bin" in result["path"]

    def test_upload_error_raises(self):
        s3 = _make_s3()
        s3.put_object.side_effect = ClientError({"Error": {"Code": "500"}}, "PutObject")
        with pytest.raises(ClientError):
            self._run(s3, BytesIO(b"data"), "test.pdf")


class TestUploadBytes:
    """Cover upload_bytes (lines 124-134)."""

    def test_delegates(self):
        from app.services import storage_service

        s3 = _make_s3()
        with (
            patch.object(storage_service, "_get_s3_client", return_value=s3),
            patch.object(storage_service, "ensure_bucket_exists"),
        ):
            result = storage_service.upload_bytes(
                b"hello", "test.txt", content_type="text/plain"
            )
        assert result["size"] == 5


class TestGetFile:
    """Cover get_file (lines 136-153)."""

    def test_success(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.get_object.return_value = {"Body": BytesIO(b"file content")}
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            result = storage_service.get_file("uploads/test.pdf")
        assert result == b"file content"

    def test_error_raises(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.get_object.side_effect = ClientError({"Error": {"Code": "404"}}, "GetObject")
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            with pytest.raises(ClientError):
                storage_service.get_file("nonexistent.pdf")


class TestDeleteFile:
    """Cover delete_file (lines 155-165)."""

    def test_success(self):
        from app.services import storage_service

        s3 = _make_s3()
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            assert storage_service.delete_file("uploads/test.pdf") is True

    def test_error_returns_false(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.delete_object.side_effect = ClientError({"Error": {"Code": "500"}}, "Delete")
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            assert storage_service.delete_file("uploads/test.pdf") is False


class TestGeneratePresignedUrl:
    """Cover generate_presigned_url (lines 167-180)."""

    def test_success_replaces_minio(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.generate_presigned_url.return_value = "http://minio:9000/bucket/key"
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            url = storage_service.generate_presigned_url("uploads/test.pdf")
        assert "localhost:9000" in url

    def test_error_raises(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "Sign"
        )
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            with pytest.raises(ClientError):
                storage_service.generate_presigned_url("test.pdf")


class TestListFiles:
    """Cover list_files (lines 182-204)."""

    def test_with_files(self):
        from datetime import UTC, datetime

        from app.services import storage_service

        s3 = _make_s3()
        s3.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "a.pdf",
                    "Size": 100,
                    "LastModified": datetime(2026, 1, 1, tzinfo=UTC),
                },
            ]
        }
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            result = storage_service.list_files("uploads")
        assert len(result) == 1

    def test_empty(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.list_objects_v2.return_value = {}
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            result = storage_service.list_files()
        assert result == []

    def test_error_returns_empty(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.list_objects_v2.side_effect = ClientError({"Error": {"Code": "500"}}, "List")
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            result = storage_service.list_files()
        assert result == []


class TestGetStorageStats:
    """Cover get_storage_stats (lines 206-228)."""

    def test_success(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.list_objects_v2.return_value = {"Contents": [{"Size": 1048576}]}
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            stats = storage_service.get_storage_stats()
        assert stats["total_files"] == 1
        assert stats["total_size_mb"] == 1.0

    def test_error_returns_zero(self):
        from app.services import storage_service

        s3 = _make_s3()
        s3.list_objects_v2.side_effect = Exception("fail")
        with patch.object(storage_service, "_get_s3_client", return_value=s3):
            stats = storage_service.get_storage_stats()
        assert stats["total_files"] == 0
        assert "error" in stats


class TestUploadBytesWithMetadata:
    """Cover upload_bytes_with_metadata (lines 230-end)."""

    def test_delegates(self):
        from app.services import storage_service

        s3 = _make_s3()
        with (
            patch.object(storage_service, "_get_s3_client", return_value=s3),
            patch.object(storage_service, "ensure_bucket_exists"),
        ):
            result = storage_service.upload_bytes_with_metadata(b"pdf", "doc.pdf")
        assert result["size"] == 3


class TestGetS3Client:
    """Cover _get_s3_client (line 28)."""

    def test_returns_boto3_client(self):
        from app.services.storage_service import _get_s3_client

        with patch("app.services.storage_service.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            result = _get_s3_client()
        assert result == mock_client
        mock_boto3.client.assert_called_once_with(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            region_name="ru-central1",
        )
