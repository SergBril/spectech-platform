"""Unit-тесты адаптера Mapix GPS (ObjectId-based API)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.gps_providers.mapix import MapixAdapter


class TestMapixAdapterInit:
    """Тесты инициализации адаптера."""

    def test_init_with_object_ids_string(self):
        config = {
            "login": "test",
            "password": "pass",
            "object_ids": "18625,18539,6097",
        }
        adapter = MapixAdapter(config)
        assert adapter.object_ids == ["18625", "18539", "6097"]
        assert adapter.login == "test"

    def test_init_with_object_ids_list(self):
        config = {
            "login": "test",
            "password": "pass",
            "object_ids": ["18625", "18539"],
        }
        adapter = MapixAdapter(config)
        assert adapter.object_ids == ["18625", "18539"]

    def test_init_without_object_ids(self):
        config = {"login": "test", "password": "pass"}
        adapter = MapixAdapter(config)
        assert adapter.object_ids == []


class TestMapixInfodataParsing:
    """Тесты парсинга ответа /index/infodata/ObjectId/{id}."""

    @pytest.mark.asyncio
    async def test_fetch_object_data_success(self):
        """✅ Корректный JSON-ответ парсится в GpsPointData."""
        adapter = MapixAdapter(
            {
                "login": "test",
                "password": "pass",
                "object_ids": "18625",
            }
        )
        adapter._session_valid = True
        adapter._cookies = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success":true,"lat":"55.7769928","long":"37.2542114"}'

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await adapter._fetch_object_data(mock_client, "18625")

        assert result is not None
        assert abs(result.latitude - 55.7769928) < 0.0001
        assert abs(result.longitude - 37.2542114) < 0.0001
        assert result.raw_data["object_id"] == "18625"

    @pytest.mark.asyncio
    async def test_fetch_object_data_zero_coords_skipped(self):
        """❌ Точки с нулевыми координатами пропускаются."""
        adapter = MapixAdapter(
            {
                "login": "test",
                "password": "pass",
                "object_ids": "18625",
            }
        )
        adapter._session_valid = True
        adapter._cookies = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success":true,"lat":"0","long":"0"}'

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await adapter._fetch_object_data(mock_client, "18625")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_object_data_empty_response(self):
        """❌ Пустой ответ возвращает None."""
        adapter = MapixAdapter(
            {
                "login": "test",
                "password": "pass",
                "object_ids": "18625",
            }
        )
        adapter._session_valid = True
        adapter._cookies = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await adapter._fetch_object_data(mock_client, "18625")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_object_data_http_error(self):
        """❌ HTTP ошибка возвращает None."""
        adapter = MapixAdapter(
            {
                "login": "test",
                "password": "pass",
                "object_ids": "18625",
            }
        )
        adapter._session_valid = True
        adapter._cookies = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await adapter._fetch_object_data(mock_client, "18625")
        assert result is None
