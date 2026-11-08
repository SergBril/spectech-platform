"""Tests for DaDataService - async-correct."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def service():
    from app.services.dadata_service import DaDataService

    with patch.dict(
        os.environ, {"DADATA_API_KEY": "test-key-123", "DADATA_TOKEN": "test-token"}
    ):
        return DaDataService()


class TestInit:
    def test_with_key(self, service):
        assert service.api_key == "test-key-123"

    def test_without_key(self):
        from app.services.dadata_service import DaDataService

        with patch.dict(
            os.environ, {"DADATA_API_KEY": "", "DADATA_TOKEN": ""}, clear=False
        ):
            svc = DaDataService()
        assert svc.api_key == ""


class TestSuggestPartyByInn:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        from app.services.dadata_service import DaDataService

        with patch.dict(
            os.environ, {"DADATA_API_KEY": "", "DADATA_TOKEN": ""}, clear=False
        ):
            svc = DaDataService()
        result = await svc.suggest_party_by_inn("1234567890")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_inn_format(self, service):
        result = await service.suggest_party_by_inn("abc")
        assert result is None

    @pytest.mark.asyncio
    async def test_inn_wrong_length(self, service):
        result = await service.suggest_party_by_inn("12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_success(self, service):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "suggestions": [
                {
                    "data": {
                        "name": {"full_with_opf": "OOO Test", "short_with_opf": "Test"},
                        "inn": "1234567890",
                        "kpp": "123456789",
                        "address": {"value": "Moscow"},
                        "finance": {"bank_name": "Sber", "bank_bik": "044525225"},
                        "management": {"name": "Ivanov"},
                    }
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_party_by_inn("1234567890")
        assert result is not None
        assert result["inn"] == "1234567890"

    @pytest.mark.asyncio
    async def test_http_error(self, service):
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Server Error"
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_party_by_inn("1234567890")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_suggestions(self, service):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"suggestions": []}
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_party_by_inn("1234567890")
        assert result is None

    @pytest.mark.asyncio
    async def test_timeout(self, service):
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_party_by_inn("1234567890")
        assert result is None

    @pytest.mark.asyncio
    async def test_generic_exception(self, service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_party_by_inn("1234567890")
        assert result is None


class TestParsePartyData:
    def test_full_data(self, service):
        data = {
            "name": {"full_with_opf": "OOO Full", "short_with_opf": "Short"},
            "inn": "123",
            "kpp": "456",
            "ogrn": "789",
            "okpo": "012",
            "address": {"value": "Addr"},
            "finance": {
                "bank_name": "Bank",
                "bank_bik": "BIK",
                "bank_account": "ACC",
                "bank_correspondent_account": "CORR",
            },
            "management": {"name": "Boss", "post": "CEO"},
            "type": "LEGAL",
            "state": {"status": "ACTIVE"},
        }
        result = service._parse_party_data(data)
        assert result["name"] == "Short"
        assert result["bank_name"] == "Bank"
        assert result["management_name"] == "Boss"

    def test_empty_data(self, service):
        result = service._parse_party_data({})
        assert result["name"] == ""
        assert result["inn"] == ""

    def test_fallback_to_full_name(self, service):
        data = {"name": {"full_with_opf": "Full Name"}}
        result = service._parse_party_data(data)
        assert result["name"] == "Full Name"


class TestSuggestBankByBik:
    @pytest.mark.asyncio
    async def test_no_api_key(self):
        from app.services.dadata_service import DaDataService

        with patch.dict(
            os.environ, {"DADATA_API_KEY": "", "DADATA_TOKEN": ""}, clear=False
        ):
            svc = DaDataService()
        result = await svc.suggest_bank_by_bik("044525225")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_bik(self, service):
        result = await service.suggest_bank_by_bik("123")
        assert result is None

    @pytest.mark.asyncio
    async def test_success(self, service):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "suggestions": [
                {
                    "data": {
                        "name": {"short": "Sberbank"},
                        "bik": "044525225",
                        "correspondent_account": "30101810400000000225",
                        "address": {"value": "Moscow"},
                    }
                }
            ]
        }
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_bank_by_bik("044525225")
        assert result is not None
        assert result["bik"] == "044525225"

    @pytest.mark.asyncio
    async def test_http_error(self, service):
        resp = MagicMock()
        resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_bank_by_bik("044525225")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_suggestions(self, service):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"suggestions": []}
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_bank_by_bik("044525225")
        assert result is None

    @pytest.mark.asyncio
    async def test_exception(self, service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("fail")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.dadata_service.httpx.AsyncClient", return_value=mock_client
        ):
            result = await service.suggest_bank_by_bik("044525225")
        assert result is None
