"""Comprehensive tests for salary_notification_dispatcher -> 100%."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.salary_notification_dispatcher import SalaryNotificationDispatcher


@pytest.fixture
def dispatcher():
    return SalaryNotificationDispatcher()


def _make_mock_db(return_values: list):
    """Create mock db where query().filter().first() returns values in order."""
    db = MagicMock()
    call_count = {"n": 0}

    def mock_query(model):
        chain = MagicMock()
        chain.filter.return_value = chain

        def mock_first():
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(return_values):
                return return_values[idx]
            return None

        chain.first = mock_first
        return chain

    db.query.side_effect = mock_query
    return db


def _record(**kw):
    d = dict(
        id=1, employee_contractor_id=10,
        period_start=date(2026, 10, 1), period_end=date(2026, 10, 31),
        net_amount="50000.00", gross_amount="60000.00",
    )
    d.update(kw)
    return SimpleNamespace(**d)


def _employee(**kw):
    d = dict(contractor_id=10, user_id=5)
    d.update(kw)
    return SimpleNamespace(**d)


def _contractor(**kw):
    d = dict(id=10, name="Ivanov I.I.", contact_email="ivan@test.com")
    d.update(kw)
    return SimpleNamespace(**kw)


def _user(**kw):
    d = dict(id=5, email="user@test.com", telegram_id="123456")
    d.update(kw)
    return SimpleNamespace(**kw)


class TestNotifyEmployeeNotFound:
    @pytest.mark.asyncio
    async def test_returns_empty(self, dispatcher):
        db = _make_mock_db([None])
        result = await dispatcher.notify_employee(db, _record())
        assert result == {"email": False, "telegram": False, "internal": False}


class TestNotifyAllChannelsSuccess:
    @pytest.mark.asyncio
    async def test_all_sent(self, dispatcher):
        db = _make_mock_db([_employee(), _contractor(), _user()])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            with patch("app.services.salary_notification_dispatcher.create_notification"):
                with patch("app.services.salary_notification_dispatcher.email_service") as es:
                    es.send_email = AsyncMock()
                    with patch("app.services.salary_notification_dispatcher.telegram_service") as ts:
                        ts.send_document = AsyncMock()
                        result = await dispatcher.notify_employee(db, _record(), "Admin")
        assert result == {"email": True, "telegram": True, "internal": True}


class TestNotifyNoContractor:
    @pytest.mark.asyncio
    async def test_fallback_name(self, dispatcher):
        db = _make_mock_db([_employee(user_id=None), None])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            result = await dispatcher.notify_employee(db, _record())
        assert result["internal"] is False
        assert result["email"] is False
        assert result["telegram"] is False


class TestNotifyPdfFails:
    @pytest.mark.asyncio
    async def test_pdf_fail_tg_text_fallback(self, dispatcher):
        db = _make_mock_db([_employee(), _contractor(), _user()])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip",
                   side_effect=RuntimeError("PDF fail")):
            with patch("app.services.salary_notification_dispatcher.create_notification"):
                with patch("app.services.salary_notification_dispatcher.telegram_service") as ts:
                    ts.send_message = AsyncMock()
                    result = await dispatcher.notify_employee(db, _record())
        assert result["email"] is False
        assert result["telegram"] is True
        assert result["internal"] is True


class TestNotifyInternalFails:
    @pytest.mark.asyncio
    async def test_internal_fail_continues(self, dispatcher):
        db = _make_mock_db([_employee(), _contractor(), _user()])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            with patch("app.services.salary_notification_dispatcher.create_notification",
                       side_effect=RuntimeError("fail")):
                with patch("app.services.salary_notification_dispatcher.email_service") as es:
                    es.send_email = AsyncMock()
                    with patch("app.services.salary_notification_dispatcher.telegram_service") as ts:
                        ts.send_document = AsyncMock()
                        result = await dispatcher.notify_employee(db, _record())
        assert result["internal"] is False
        assert result["email"] is True
        assert result["telegram"] is True


class TestNotifyEmailFails:
    @pytest.mark.asyncio
    async def test_email_fail(self, dispatcher):
        db = _make_mock_db([_employee(), _contractor(), _user()])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            with patch("app.services.salary_notification_dispatcher.create_notification"):
                with patch("app.services.salary_notification_dispatcher.email_service") as es:
                    es.send_email = AsyncMock(side_effect=RuntimeError("SMTP fail"))
                    with patch("app.services.salary_notification_dispatcher.telegram_service") as ts:
                        ts.send_document = AsyncMock()
                        result = await dispatcher.notify_employee(db, _record())
        assert result["email"] is False
        assert result["telegram"] is True


class TestNotifyTelegramDocFails:
    @pytest.mark.asyncio
    async def test_tg_doc_fail(self, dispatcher):
        db = _make_mock_db([_employee(), _contractor(), _user()])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            with patch("app.services.salary_notification_dispatcher.create_notification"):
                with patch("app.services.salary_notification_dispatcher.email_service") as es:
                    es.send_email = AsyncMock()
                    with patch("app.services.salary_notification_dispatcher.telegram_service") as ts:
                        ts.send_document = AsyncMock(side_effect=RuntimeError("TG fail"))
                        result = await dispatcher.notify_employee(db, _record())
        assert result["telegram"] is False


class TestNotifyTelegramTextFallback:
    @pytest.mark.asyncio
    async def test_text_success(self, dispatcher):
        db = _make_mock_db([_employee(), _contractor(contact_email=None), _user(email=None)])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip",
                   side_effect=RuntimeError("no pdf")):
            with patch("app.services.salary_notification_dispatcher.create_notification"):
                with patch("app.services.salary_notification_dispatcher.telegram_service") as ts:
                    ts.send_message = AsyncMock()
                    result = await dispatcher.notify_employee(db, _record())
        assert result["telegram"] is True
        assert result["email"] is False

    @pytest.mark.asyncio
    async def test_text_fail(self, dispatcher):
        db = _make_mock_db([_employee(), _contractor(), _user()])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip",
                   side_effect=RuntimeError("no pdf")):
            with patch("app.services.salary_notification_dispatcher.create_notification"):
                with patch("app.services.salary_notification_dispatcher.telegram_service") as ts:
                    ts.send_message = AsyncMock(side_effect=RuntimeError("TG text fail"))
                    result = await dispatcher.notify_employee(db, _record())
        assert result["telegram"] is False


class TestNotifyNoUser:
    @pytest.mark.asyncio
    async def test_no_user_id(self, dispatcher):
        db = _make_mock_db([_employee(user_id=None), _contractor()])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            with patch("app.services.salary_notification_dispatcher.email_service") as es:
                es.send_email = AsyncMock()
                result = await dispatcher.notify_employee(db, _record())
        assert result["internal"] is False
        assert result["email"] is True
        assert result["telegram"] is False

    @pytest.mark.asyncio
    async def test_user_not_found(self, dispatcher):
        db = _make_mock_db([_employee(user_id=999), _contractor(), None])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            with patch("app.services.salary_notification_dispatcher.email_service") as es:
                es.send_email = AsyncMock()
                result = await dispatcher.notify_employee(db, _record())
        assert result["internal"] is False
        assert result["telegram"] is False


class TestNotifyNoEmail:
    @pytest.mark.asyncio
    async def test_no_email_address(self, dispatcher):
        db = _make_mock_db([_employee(user_id=None), _contractor(contact_email=None)])
        with patch("app.services.salary_notification_dispatcher.generate_salary_payslip", return_value=b"pdf"):
            result = await dispatcher.notify_employee(db, _record())
        assert result["email"] is False
