"""Comprehensive tests for diadoc_service -> 100%."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


MOD = "app.services.diadoc_service"


def _svc(enabled=True):
    with patch("app.core.config.settings") as s:
        s.DIADOC_API_KEY = "test-key" if enabled else ""
        s.DIADOC_BOX_ID = "test-box" if enabled else ""
        s.DIADOC_BASE_URL = "https://api.test.com"
        from app.services.diadoc_service import DiadocService
        return DiadocService()


class TestInit:
    def test_enabled(self):
        svc = _svc(enabled=True)
        assert svc.enabled is True

    def test_disabled(self):
        svc = _svc(enabled=False)
        assert svc.enabled is False


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_stub_when_disabled(self):
        svc = _svc(enabled=False)
        token = await svc.authenticate()
        assert token == "stub-token"

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _svc(enabled=True)
        mock_resp = MagicMock()
        mock_resp.headers = {"AuthToken": "real-token"}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            token = await svc.authenticate()
        assert token == "real-token"

    @pytest.mark.asyncio
    async def test_auth_error(self):
        svc = _svc(enabled=True)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("auth fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            token = await svc.authenticate()
        assert token is None


class TestSendAct:
    @pytest.mark.asyncio
    async def test_stub_when_disabled(self):
        svc = _svc(enabled=False)
        r = await svc.send_act(b"<xml/>", "counter-box", "token")
        assert r["status"] == "sent_stub"

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _svc(enabled=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"MessageId": "msg-123"}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.object(svc, "_sign_for_diadoc", new=AsyncMock(return_value="sig")):
                r = await svc.send_act(b"<xml/>", "counter-box", "token")
        assert r["message_id"] == "msg-123"
        assert r["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_error(self):
        svc = _svc(enabled=True)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("send fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.object(svc, "_sign_for_diadoc", new=AsyncMock(return_value="sig")):
                r = await svc.send_act(b"<xml/>", "counter-box", "token")
        assert r["status"] == "error"
        assert r["message_id"] is None


class TestSignForDiadoc:
    @pytest.mark.asyncio
    async def test_success(self):
        svc = _svc(enabled=True)
        mock_result = {"signature": "base64sig", "status": "ok", "provider": "cryptopro"}
        with patch(f"{MOD}.digital_signature_service") as dss:
            dss.sign_document = AsyncMock(return_value=mock_result)
            sig = await svc._sign_for_diadoc(b"doc-bytes")
        assert sig == "base64sig"

    @pytest.mark.asyncio
    async def test_signing_error(self):
        svc = _svc(enabled=True)
        mock_result = {"status": "error", "error": "KEP expired"}
        with patch(f"{MOD}.digital_signature_service") as dss:
            dss.sign_document = AsyncMock(return_value=mock_result)
            sig = await svc._sign_for_diadoc(b"doc-bytes")
        assert sig == ""

    @pytest.mark.asyncio
    async def test_exception(self):
        svc = _svc(enabled=True)
        with patch(f"{MOD}.digital_signature_service") as dss:
            dss.sign_document = AsyncMock(side_effect=RuntimeError("KEP down"))
            sig = await svc._sign_for_diadoc(b"doc-bytes")
        assert sig == ""


class TestGetCounterparties:
    @pytest.mark.asyncio
    async def test_stub_when_disabled(self):
        svc = _svc(enabled=False)
        r = await svc.get_counterparties("token")
        assert len(r) == 1
        assert r[0]["box_id"] == "stub-box"

    @pytest.mark.asyncio
    async def test_success(self):
        svc = _svc(enabled=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "Counteragents": [
                {"CounteragentBoxId": "box1",
                 "Organization": {"Name": "OOO Test", "Inn": "7700000001"}}
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            r = await svc.get_counterparties("token")
        assert len(r) == 1
        assert r[0]["name"] == "OOO Test"
        assert r[0]["inn"] == "7700000001"

    @pytest.mark.asyncio
    async def test_error(self):
        svc = _svc(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("API down"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            r = await svc.get_counterparties("token")
        assert r == []


class TestGetDocumentStatus:
    @pytest.mark.asyncio
    async def test_stub_when_disabled(self):
        svc = _svc(enabled=False)
        r = await svc.get_document_status("msg-1", "token")
        assert r["status"] == "stub"

    @pytest.mark.asyncio
    async def test_known_status(self):
        svc = _svc(enabled=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "Documents": [{
                "DocflowStatus": {"PrimaryStatus": "WithRecipientSignature"},
                "Timestamp": "2026-01-15T10:00:00"
            }]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            r = await svc.get_document_status("msg-1", "token")
        assert r["status"] == "signed"
        assert r["raw_status"] == "WithRecipientSignature"

    @pytest.mark.asyncio
    async def test_unknown_status(self):
        svc = _svc(enabled=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "Documents": [{
                "DocflowStatus": {"PrimaryStatus": "SomeNewStatus"},
                "Timestamp": "2026-01-15"
            }]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            r = await svc.get_document_status("msg-1", "token")
        assert r["status"] == "SomeNewStatus"

    @pytest.mark.asyncio
    async def test_no_documents(self):
        svc = _svc(enabled=True)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Documents": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            r = await svc.get_document_status("msg-1", "token")
        assert r["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_error(self):
        svc = _svc(enabled=True)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=mock_client):
            r = await svc.get_document_status("msg-1", "token")
        assert r["status"] == "error"
        assert "timeout" in r["error"]
