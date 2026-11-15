"""AQ: per-company credentials в diadoc_service.

Дискриминирующие тесты: две компании с РАЗНЫМИ ключами — каждый вызов
уходит со своим api_key/box_id; компания без ключа — глобальный fallback;
ключ в БД лежит НЕ открытым текстом (DB-факт).

ЗАПУСКАТЬ ТОЛЬКО после сигнала пользователя: колонки Company.diadoc_*
и app.core.crypto.decrypt_secret добавляются в параллельной задаче.
Мок только внешнего Diadoc (httpx); decrypt_secret подменяется фейковым
шифром "enc:<plaintext>", чтобы не зависеть от реализации Fernet.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.company import Company

pytestmark = [pytest.mark.unit]


def _svc(global_key: str = "", global_box: str = ""):
    """DiadocService с заданными глобальными settings (паттерн test_diadoc_service_final)."""
    with patch("app.core.config.settings") as s:
        s.DIADOC_API_KEY = global_key
        s.DIADOC_BOX_ID = global_box
        s.DIADOC_BASE_URL = "https://api.test.com"
        from app.services.diadoc_service import DiadocService

        return DiadocService()


def _http_client():
    mock_resp = MagicMock()
    mock_resp.headers = {"AuthToken": "tok"}
    mock_resp.json.return_value = {
        "MessageId": "msg-1",
        "Documents": [],
        "Counteragents": [],
    }
    mock_resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post = AsyncMock(return_value=mock_resp)
    client.get = AsyncMock(return_value=mock_resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.fixture
def companies(db_session):
    a = Company(
        name="AQ Company A",
        legal_name="ООО А",
        inn="7700000001",
        diadoc_api_key="enc:KEY-A",
        diadoc_box_id="BOX-A",
    )
    b = Company(
        name="AQ Company B",
        legal_name="ООО Б",
        inn="7700000002",
        diadoc_api_key="enc:KEY-B",
        diadoc_box_id="BOX-B",
    )
    c = Company(name="AQ Company C", legal_name="ООО В", inn="7700000003")
    db_session.add_all([a, b, c])
    db_session.commit()
    for x in (a, b, c):
        db_session.refresh(x)
    return a, b, c


@pytest.fixture
def fake_decrypt(monkeypatch):
    calls = []

    def _decrypt(value):
        calls.append(value)
        return value.removeprefix("enc:")

    monkeypatch.setattr("app.core.crypto.decrypt_secret", _decrypt)
    return calls


class TestCompanyCredentials:
    @pytest.mark.asyncio
    async def test_authenticate_uses_own_key_per_company(self, companies, fake_decrypt):
        a, b, _ = companies
        svc = _svc()
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.authenticate(company=a)
            headers_a = client.post.call_args.kwargs["headers"]
            await svc.authenticate(company=b)
            headers_b = client.post.call_args.kwargs["headers"]
        assert headers_a["ddauth_api_client_id"] == "KEY-A"
        assert headers_b["ddauth_api_client_id"] == "KEY-B"
        assert fake_decrypt == ["enc:KEY-A", "enc:KEY-B"]

    @pytest.mark.asyncio
    async def test_send_act_uses_own_box_and_key(self, companies, fake_decrypt):
        a, b, _ = companies
        svc = _svc()
        client = _http_client()
        with (
            patch("httpx.AsyncClient", return_value=client),
            patch.object(svc, "_sign_for_diadoc", new=AsyncMock(return_value="sig")),
        ):
            await svc.send_act(b"<xml/>", "cp-box", "tok", company=a)
            payload_a = client.post.call_args.kwargs["json"]
            headers_a = client.post.call_args.kwargs["headers"]
            await svc.send_act(b"<xml/>", "cp-box", "tok", company=b)
            payload_b = client.post.call_args.kwargs["json"]
            headers_b = client.post.call_args.kwargs["headers"]
        assert payload_a["BoxId"] == "BOX-A"
        assert headers_a["ddauth_api_client_id"] == "KEY-A"
        assert payload_b["BoxId"] == "BOX-B"
        assert headers_b["ddauth_api_client_id"] == "KEY-B"

    @pytest.mark.asyncio
    async def test_get_counterparties_uses_company_box(self, companies, fake_decrypt):
        a, _, _ = companies
        svc = _svc()
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.get_counterparties("tok", company=a)
        assert client.get.call_args.kwargs["params"]["boxId"] == "BOX-A"
        assert client.get.call_args.kwargs["headers"]["ddauth_api_client_id"] == "KEY-A"

    @pytest.mark.asyncio
    async def test_get_document_status_uses_company_box(self, companies, fake_decrypt):
        a, _, _ = companies
        svc = _svc()
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.get_document_status("msg-1", "tok", company=a)
        params = client.get.call_args.kwargs["params"]
        assert params["boxId"] == "BOX-A"
        assert params["messageId"] == "msg-1"
        assert client.get.call_args.kwargs["headers"]["ddauth_api_client_id"] == "KEY-A"

    @pytest.mark.asyncio
    async def test_company_without_key_falls_back_to_globals(
        self, companies, fake_decrypt
    ):
        _, _, c = companies
        svc = _svc("GLOBAL-KEY", "GLOBAL-BOX")
        client = _http_client()
        with (
            patch("httpx.AsyncClient", return_value=client),
            patch.object(svc, "_sign_for_diadoc", new=AsyncMock(return_value="sig")),
        ):
            await svc.authenticate(company=c)
            assert (
                client.post.call_args.kwargs["headers"]["ddauth_api_client_id"]
                == "GLOBAL-KEY"
            )
            await svc.send_act(b"<xml/>", "cp-box", "tok", company=c)
            assert client.post.call_args.kwargs["json"]["BoxId"] == "GLOBAL-BOX"
        assert fake_decrypt == []

    @pytest.mark.asyncio
    async def test_company_key_without_box_falls_back_per_field(
        self, db_session, fake_decrypt
    ):
        partial = Company(
            name="AQ Partial",
            legal_name="ООО Частичная",
            inn="7700000004",
            diadoc_api_key="enc:KEY-P",
        )
        db_session.add(partial)
        db_session.commit()
        db_session.refresh(partial)

        svc = _svc("GLOBAL-KEY", "GLOBAL-BOX")
        client = _http_client()
        with (
            patch("httpx.AsyncClient", return_value=client),
            patch.object(svc, "_sign_for_diadoc", new=AsyncMock(return_value="sig")),
        ):
            await svc.send_act(b"<xml/>", "cp-box", "tok", company=partial)
        assert (
            client.post.call_args.kwargs["headers"]["ddauth_api_client_id"] == "KEY-P"
        )
        assert client.post.call_args.kwargs["json"]["BoxId"] == "GLOBAL-BOX"

    @pytest.mark.asyncio
    async def test_stub_when_no_key_anywhere(self, companies, fake_decrypt):
        _, _, c = companies
        svc = _svc()
        with patch("httpx.AsyncClient") as cls:
            assert await svc.authenticate(company=c) == "stub-token"
            r = await svc.send_act(b"<xml/>", "cp-box", "tok", company=c)
            assert r["status"] == "sent_stub"
            cp = await svc.get_counterparties("tok", company=c)
            assert cp[0]["box_id"] == "stub-box"
            st = await svc.get_document_status("msg-1", "tok", company=c)
            assert st["status"] == "stub"
            cls.assert_not_called()
        assert fake_decrypt == []

    def test_db_stores_ciphertext_not_plaintext(self, companies, db_session):
        a, _, _ = companies
        raw = db_session.get(Company, a.id).diadoc_api_key
        assert raw == "enc:KEY-A"
        assert raw != "KEY-A"
