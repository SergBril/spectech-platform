"""AR: выбор base_url по company.diadoc_use_sandbox.

Дефолт True = безопасно (тестовый контур не создаёт настоящих документов).
Проверенные адреса: продуктивный https://diadoc-api.kontur.ru,
тестовый https://diadoc-api-test.kontur.ru. Мок только внешнего HTTP (httpx).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.company import Company
from app.services.diadoc_service import (
    DIADOC_PROD_URL,
    DIADOC_SANDBOX_URL,
    DiadocService,
)

pytestmark = [pytest.mark.unit]


def _svc(global_sandbox: bool = True):
    with patch("app.core.config.settings") as s:
        s.DIADOC_API_KEY = "test-key"
        s.DIADOC_BOX_ID = "test-box"
        s.DIADOC_USE_SANDBOX = global_sandbox
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
    sandbox_co = Company(
        name="AR Sandbox Co",
        legal_name="ООО Песочница",
        inn="7700000031",
        diadoc_api_key="enc:KEY-S",
        diadoc_box_id="BOX-S",
        diadoc_use_sandbox=True,
    )
    prod_co = Company(
        name="AR Prod Co",
        legal_name="ООО Продуктив",
        inn="7700000032",
        diadoc_api_key="enc:KEY-P",
        diadoc_box_id="BOX-P",
        diadoc_use_sandbox=False,
    )
    db_session.add_all([sandbox_co, prod_co])
    db_session.commit()
    db_session.refresh(sandbox_co)
    db_session.refresh(prod_co)
    return sandbox_co, prod_co


@pytest.fixture(autouse=True)
def fake_decrypt(monkeypatch):
    monkeypatch.setattr(
        "app.core.crypto.decrypt_secret", lambda value: value.removeprefix("enc:")
    )


class TestSandboxUrl:
    @pytest.mark.asyncio
    async def test_sandbox_true_hits_test_url(self, companies):
        sandbox_co, _ = companies
        svc = _svc(global_sandbox=False)
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.authenticate(company=sandbox_co)
        url = client.post.call_args.args[0]
        assert url == f"{DIADOC_SANDBOX_URL}/V3/Authenticate"
        assert url.startswith("https://diadoc-api-test.kontur.ru")

    @pytest.mark.asyncio
    async def test_sandbox_false_hits_prod_url(self, companies):
        _, prod_co = companies
        svc = _svc(global_sandbox=True)
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.authenticate(company=prod_co)
        url = client.post.call_args.args[0]
        assert url == f"{DIADOC_PROD_URL}/V3/Authenticate"
        assert url.startswith("https://diadoc-api.kontur.ru")

    @pytest.mark.asyncio
    async def test_two_companies_different_flags_different_urls(self, companies):
        sandbox_co, prod_co = companies
        svc = _svc()
        client = _http_client()
        with (
            patch("httpx.AsyncClient", return_value=client),
            patch.object(svc, "_sign_for_diadoc", new=AsyncMock(return_value="sig")),
        ):
            await svc.authenticate(company=sandbox_co)
            auth_url_sandbox = client.post.call_args.args[0]
            await svc.authenticate(company=prod_co)
            auth_url_prod = client.post.call_args.args[0]
            await svc.send_act(b"<xml/>", "cp", "tok", company=sandbox_co)
            send_url_sandbox = client.post.call_args.args[0]
            await svc.send_act(b"<xml/>", "cp", "tok", company=prod_co)
            send_url_prod = client.post.call_args.args[0]
        assert auth_url_sandbox != auth_url_prod
        assert auth_url_sandbox.startswith(DIADOC_SANDBOX_URL)
        assert auth_url_prod.startswith(DIADOC_PROD_URL)
        assert send_url_sandbox == f"{DIADOC_SANDBOX_URL}/V3/PostMessage"
        assert send_url_prod == f"{DIADOC_PROD_URL}/V3/PostMessage"

    @pytest.mark.asyncio
    async def test_all_methods_use_company_sandbox_url(self, companies):
        sandbox_co, _ = companies
        svc = _svc(global_sandbox=False)
        client = _http_client()
        with (
            patch("httpx.AsyncClient", return_value=client),
            patch.object(svc, "_sign_for_diadoc", new=AsyncMock(return_value="sig")),
        ):
            await svc.send_act(b"<xml/>", "cp", "tok", company=sandbox_co)
            assert (
                client.post.call_args.args[0] == f"{DIADOC_SANDBOX_URL}/V3/PostMessage"
            )
            await svc.get_counterparties("tok", company=sandbox_co)
            assert (
                client.get.call_args.args[0]
                == f"{DIADOC_SANDBOX_URL}/V2/GetCounteragents"
            )
            await svc.get_document_status("msg-1", "tok", company=sandbox_co)
            assert client.get.call_args.args[0] == f"{DIADOC_SANDBOX_URL}/V3/GetMessage"

    @pytest.mark.asyncio
    async def test_company_flag_overrides_global_false(self, companies):
        sandbox_co, _ = companies
        svc = _svc(global_sandbox=False)
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.authenticate(company=sandbox_co)
        assert client.post.call_args.args[0].startswith(DIADOC_SANDBOX_URL)

    @pytest.mark.asyncio
    async def test_company_flag_overrides_global_true(self, companies):
        _, prod_co = companies
        svc = _svc(global_sandbox=True)
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.authenticate(company=prod_co)
        assert client.post.call_args.args[0].startswith(DIADOC_PROD_URL)

    @pytest.mark.asyncio
    async def test_company_flag_none_falls_back_to_global(self, db_session):
        no_flag = Company(
            name="AR NoFlag Co",
            legal_name="ООО Без флага",
            inn="7700000033",
            diadoc_api_key="enc:KEY-N",
            diadoc_box_id="BOX-N",
        )
        db_session.add(no_flag)
        db_session.commit()
        # INSERT подставляет default=True; NULL достижим только UPDATE-ом
        no_flag.diadoc_use_sandbox = None
        db_session.commit()
        db_session.refresh(no_flag)
        assert no_flag.diadoc_use_sandbox is None

        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await _svc(global_sandbox=False).authenticate(company=no_flag)
            assert client.post.call_args.args[0].startswith(DIADOC_PROD_URL)
            await _svc(global_sandbox=True).authenticate(company=no_flag)
            assert client.post.call_args.args[0].startswith(DIADOC_SANDBOX_URL)

    @pytest.mark.asyncio
    async def test_global_default_is_sandbox_when_setting_absent(self):
        with patch("app.core.config.settings") as s:
            s.DIADOC_API_KEY = "test-key"
            s.DIADOC_BOX_ID = "test-box"
            del s.DIADOC_USE_SANDBOX
            svc = DiadocService()
        assert svc.use_sandbox is True
        client = _http_client()
        with patch("httpx.AsyncClient", return_value=client):
            await svc.authenticate()
        assert client.post.call_args.args[0].startswith(DIADOC_SANDBOX_URL)
