"""Coverage tests for dadata_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def svc():
    with patch.dict("os.environ", {"DADATA_API_KEY": "test-key-123"}):
        from app.services.dadata_service import DaDataService

        return DaDataService()


class TestInit:
    """Cover __init__ (lines 20-25)."""

    def test_with_key(self, svc):
        assert svc.api_key == "test-key-123"

    def test_without_key(self):
        with patch.dict("os.environ", {"DADATA_API_KEY": ""}):
            from app.services.dadata_service import DaDataService

            s = DaDataService()
            assert s.api_key == ""


class TestSuggestPartyByInn:
    """Cover suggest_party_by_inn (lines 27-104)."""

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        with patch.dict("os.environ", {"DADATA_API_KEY": ""}):
            from app.services.dadata_service import DaDataService

            s = DaDataService()
            result = await s.suggest_party_by_inn("1234567890")
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_inn_format(self, svc):
        result = await svc.suggest_party_by_inn("abc")
        assert result is None

    @pytest.mark.asyncio
    async def test_inn_wrong_length(self, svc):
        result = await svc.suggest_party_by_inn("12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_success(self, svc):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "suggestions": [
                {
                    "data": {
                        "name": {"full_with_opf": "ООО Тест", "short_with_opf": "Тест"},
                        "inn": "1234567890",
                        "kpp": "123456789",
                        "address": {"value": "Москва"},
                        "finance": {"bank_name": "Сбер", "bank_bik": "044525225"},
                        "management": {"name": "Иванов"},
                        "type": "LEGAL",
                        "state": {"status": "ACTIVE"},
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await svc.suggest_party_by_inn("1234567890")

        assert result is not None
        assert result["inn"] == "1234567890"
        assert result["name"] == "Тест"

    @pytest.mark.asyncio
    async def test_api_error_status(self, svc):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await svc.suggest_party_by_inn("1234567890")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_suggestions(self, svc):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"suggestions": []}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await svc.suggest_party_by_inn("1234567890")

        assert result is None

    @pytest.mark.asyncio
    async def test_timeout(self, svc):
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await svc.suggest_party_by_inn("1234567890")

        assert result is None


class TestParsePartyData:
    """Cover _parse_party_data (lines 106-148)."""

    def test_full_data(self, svc):
        data = {
            "name": {"full_with_opf": "ООО Тест Полное", "short_with_opf": "Тест"},
            "inn": "1234567890",
            "kpp": "123456789",
            "ogrn": "111",
            "okpo": "222",
            "address": {"value": "Москва, ул. Ленина 1"},
            "finance": {
                "bank_name": "Сбер",
                "bank_bik": "044525225",
                "bank_account": "40702810",
                "bank_correspondent_account": "30101810",
            },
            "management": {"name": "Иванов И.И.", "post": "Директор"},
            "type": "LEGAL",
            "state": {"status": "ACTIVE"},
        }
        result = svc._parse_party_data(data)
        assert result["name"] == "Тест"
        assert result["inn"] == "1234567890"
        assert result["bank_name"] == "Сбер"
        assert result["management_name"] == "Иванов И.И."
        assert result["type"] == "LEGAL"

    def test_empty_data(self, svc):
        result = svc._parse_party_data({})
        assert result["name"] == ""
        assert result["inn"] == ""
        assert result["type"] == "LEGAL"


class TestSuggestBankByBik:
    """Cover suggest_bank_by_bik (lines 150-end)."""

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        with patch.dict("os.environ", {"DADATA_API_KEY": ""}):
            from app.services.dadata_service import DaDataService

            s = DaDataService()
            result = await s.suggest_bank_by_bik("044525225")
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_bik_length(self, svc):
        result = await svc.suggest_bank_by_bik("123")
        assert result is None

    @pytest.mark.asyncio
    async def test_success(self, svc):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "suggestions": [
                {
                    "data": {
                        "name": {"short": "ПАО Сбербанк"},
                        "bik": "044525225",
                        "correspondent_account": "30101810400000000225",
                        "address": {"value": "Москва"},
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await svc.suggest_bank_by_bik("044525225")

        assert result is not None
        assert result["bik"] == "044525225"
        assert result["name"] == "ПАО Сбербанк"

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, svc):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await svc.suggest_bank_by_bik("044525225")

        assert result is None
