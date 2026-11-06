"""Coverage tests for digital_signature_service."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def stub_service():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SIGNATURE_PROVIDER = "stub"
        from app.services.digital_signature_service import DigitalSignatureService
        return DigitalSignatureService()


@pytest.fixture
def cryptopro_service():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SIGNATURE_PROVIDER = "cryptopro"
        mock_settings.CRYPTOPRO_URL = "http://localhost:8080"
        mock_settings.GOSUSLUGI_CLIENT_ID = ""
        mock_settings.GOSUSLUGI_SECRET = ""
        from app.services.digital_signature_service import DigitalSignatureService
        return DigitalSignatureService()


@pytest.fixture
def gosuslugi_service():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.SIGNATURE_PROVIDER = "gosuslugi"
        mock_settings.CRYPTOPRO_URL = "http://localhost:8080"
        mock_settings.GOSUSLUGI_CLIENT_ID = "client_id"
        mock_settings.GOSUSLUGI_SECRET = "secret"
        from app.services.digital_signature_service import DigitalSignatureService
        return DigitalSignatureService()


class TestInit:
    """Cover __init__ (lines 17-26)."""

    def test_stub_provider(self, stub_service):
        assert stub_service.provider == "stub"
        assert stub_service.enabled is False

    def test_cryptopro_provider(self, cryptopro_service):
        assert cryptopro_service.provider == "cryptopro"
        assert cryptopro_service.enabled is True

    def test_gosuslugi_provider(self, gosuslugi_service):
        assert gosuslugi_service.provider == "gosuslugi"
        assert gosuslugi_service.enabled is True


class TestSignDocument:
    """Cover sign_document (lines 28-48)."""

    @pytest.mark.asyncio
    async def test_stub_signs(self, stub_service):
        result = await stub_service.sign_document(b"test document")
        assert result["status"] == "signed_stub"
        assert result["provider"] == "stub"
        assert len(result["signature"]) > 0

    @pytest.mark.asyncio
    async def test_cryptopro_delegates(self, cryptopro_service):
        with patch.object(cryptopro_service, "_sign_cryptopro", new_callable=AsyncMock) as mock:
            mock.return_value = {"signature": "sig", "status": "signed"}
            result = await cryptopro_service.sign_document(b"data", "thumbprint")
        mock.assert_called_once_with(b"data", "thumbprint")

    @pytest.mark.asyncio
    async def test_gosuslugi_delegates(self, gosuslugi_service):
        with patch.object(gosuslugi_service, "_sign_gosuslugi", new_callable=AsyncMock) as mock:
            mock.return_value = {"signature": "sig", "status": "signed"}
            result = await gosuslugi_service.sign_document(b"data")
        mock.assert_called_once_with(b"data")


class TestSignCryptopro:
    """Cover _sign_cryptopro (lines 50-73)."""

    @pytest.mark.asyncio
    async def test_success(self, cryptopro_service):
        mock_response = MagicMock()
        mock_response.json.return_value = {"signature": "base64sig"}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cryptopro_service._sign_cryptopro(b"data", "thumb")
        assert result["status"] == "signed"
        assert result["provider"] == "cryptopro"

    @pytest.mark.asyncio
    async def test_error_returns_error(self, cryptopro_service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cryptopro_service._sign_cryptopro(b"data", "thumb")
        assert result["status"] == "error"
        assert "Connection refused" in result["error"]


class TestSignGosuslugi:
    """Cover _sign_gosuslugi (lines 75-110)."""

    @pytest.mark.asyncio
    async def test_success(self, gosuslugi_service):
        token_response = MagicMock()
        token_response.json.return_value = {"access_token": "token123"}
        token_response.raise_for_status = MagicMock()
        sign_response = MagicMock()
        sign_response.json.return_value = {"signature": "gos_sig"}
        sign_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.side_effect = [token_response, sign_response]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await gosuslugi_service._sign_gosuslugi(b"data")
        assert result["status"] == "signed"
        assert result["provider"] == "gosuslugi"

    @pytest.mark.asyncio
    async def test_error_returns_error(self, gosuslugi_service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("ESIA fail")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await gosuslugi_service._sign_gosuslugi(b"data")
        assert result["status"] == "error"


class TestVerifySignature:
    """Cover verify_signature (lines 112-121)."""

    @pytest.mark.asyncio
    async def test_stub_verify(self, stub_service):
        result = await stub_service.verify_signature(b"data", "sig")
        assert result["valid"] is True
        assert result["provider"] == "stub"

    @pytest.mark.asyncio
    async def test_non_stub_verify(self, cryptopro_service):
        result = await cryptopro_service.verify_signature(b"data", "sig")
        assert result["valid"] is True
        assert result["provider"] == "cryptopro"


class TestGlobalSingleton:
    def test_exists(self):
        from app.services.digital_signature_service import digital_signature_service
        assert digital_signature_service is not None
