"""Comprehensive tests for salary_notification_dispatcher -> 100%."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.salary_notification_dispatcher import SalaryNotificationDispatcher


@pytest.fixture
def dispatcher():
    return SalaryNotificationDispatcher()


def _mdb(qr):
    db = MagicMock()
    idx = [0]
    def mq(mc):
        c = MagicMock()
        c.filter.return_value = c
        i = idx[0]; idx[0] += 1
        c.first.return_value = qr[i] if i < len(qr) else None
        return c
    db.query.side_effect = mq
    return db


def _rec(**kw):
    d = dict(id=1, employee_contractor_id=10,
             period_start=date(2026, 10, 1), period_end=date(2026, 10, 31),
             net_amount="50000.00", gross_amount="60000.00")
    d.update(kw)
    return SimpleNamespace(**d)


def _emp(**kw):
    d = dict(id=10, contractor_id=10, user_id=5)
    d.update(kw)
    return SimpleNamespace(**d)


def _ctr(**kw):
    d = dict(id=10, name="Ivanov I.I.", contact_email="ivan@test.com")
    d.update(kw)
    return SimpleNamespace(**kw)


def _usr(**kw):
    d = dict(id=5, email="user@test.com", telegram_id="123456")
    d.update(kw)
    return SimpleNamespace(**kw)


MOD = "app.services.salary_notification_dispatcher"


class TestEmployeeNotFound:
    @pytest.mark.asyncio
    async def test_empty(self, dispatcher):
        db = _mdb([None])
        r = await dispatcher.notify_employee(db, _rec())
        assert r == {"email": False, "telegram": False, "internal": False}


class TestAllChannelsSuccess:
    @pytest.mark.asyncio
    async def test_all_sent(self, dispatcher):
        db = _mdb([_emp(), _ctr(), _usr()])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            with patch(MOD + ".create_notification"):
                with patch(MOD + ".email_service") as es:
                    es.send_email = AsyncMock()
                    with patch(MOD + ".telegram_service") as ts:
                        ts.send_document = AsyncMock()
                        r = await dispatcher.notify_employee(db, _rec(), "Admin")
        assert r == {"email": True, "telegram": True, "internal": True}


class TestNoContractor:
    @pytest.mark.asyncio
    async def test_fallback(self, dispatcher):
        db = _mdb([_emp(user_id=None), None])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            r = await dispatcher.notify_employee(db, _rec())
        assert r["internal"] is False
        assert r["email"] is False


class TestPdfFails:
    @pytest.mark.asyncio
    async def test_tg_text_fallback(self, dispatcher):
        db = _mdb([_emp(), _ctr(), _usr()])
        with patch(MOD + ".generate_salary_payslip", side_effect=RuntimeError("fail")):
            with patch(MOD + ".create_notification"):
                with patch(MOD + ".telegram_service") as ts:
                    ts.send_message = AsyncMock()
                    r = await dispatcher.notify_employee(db, _rec())
        assert r["email"] is False
        assert r["telegram"] is True
        assert r["internal"] is True


class TestInternalFails:
    @pytest.mark.asyncio
    async def test_continues(self, dispatcher):
        db = _mdb([_emp(), _ctr(), _usr()])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            with patch(MOD + ".create_notification", side_effect=RuntimeError("fail")):
                with patch(MOD + ".email_service") as es:
                    es.send_email = AsyncMock()
                    with patch(MOD + ".telegram_service") as ts:
                        ts.send_document = AsyncMock()
                        r = await dispatcher.notify_employee(db, _rec())
        assert r["internal"] is False
        assert r["email"] is True
        assert r["telegram"] is True


class TestEmailFails:
    @pytest.mark.asyncio
    async def test_fail(self, dispatcher):
        db = _mdb([_emp(), _ctr(), _usr()])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            with patch(MOD + ".create_notification"):
                with patch(MOD + ".email_service") as es:
                    es.send_email = AsyncMock(side_effect=RuntimeError("SMTP fail"))
                    with patch(MOD + ".telegram_service") as ts:
                        ts.send_document = AsyncMock()
                        r = await dispatcher.notify_employee(db, _rec())
        assert r["email"] is False
        assert r["telegram"] is True


class TestTelegramDocFails:
    @pytest.mark.asyncio
    async def test_fail(self, dispatcher):
        db = _mdb([_emp(), _ctr(), _usr()])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            with patch(MOD + ".create_notification"):
                with patch(MOD + ".email_service") as es:
                    es.send_email = AsyncMock()
                    with patch(MOD + ".telegram_service") as ts:
                        ts.send_document = AsyncMock(side_effect=RuntimeError("TG fail"))
                        r = await dispatcher.notify_employee(db, _rec())
        assert r["telegram"] is False


class TestTelegramTextFallback:
    @pytest.mark.asyncio
    async def test_success(self, dispatcher):
        db = _mdb([_emp(), _ctr(contact_email=None), _usr(email=None)])
        with patch(MOD + ".generate_salary_payslip", side_effect=RuntimeError("no pdf")):
            with patch(MOD + ".create_notification"):
                with patch(MOD + ".telegram_service") as ts:
                    ts.send_message = AsyncMock()
                    r = await dispatcher.notify_employee(db, _rec())
        assert r["telegram"] is True
        assert r["email"] is False

    @pytest.mark.asyncio
    async def test_fail(self, dispatcher):
        db = _mdb([_emp(), _ctr(), _usr()])
        with patch(MOD + ".generate_salary_payslip", side_effect=RuntimeError("no pdf")):
            with patch(MOD + ".create_notification"):
                with patch(MOD + ".telegram_service") as ts:
                    ts.send_message = AsyncMock(side_effect=RuntimeError("TG text fail"))
                    r = await dispatcher.notify_employee(db, _rec())
        assert r["telegram"] is False


class TestNoUser:
    @pytest.mark.asyncio
    async def test_no_user_id(self, dispatcher):
        db = _mdb([_emp(user_id=None), _ctr()])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            with patch(MOD + ".email_service") as es:
                es.send_email = AsyncMock()
                r = await dispatcher.notify_employee(db, _rec())
        assert r["internal"] is False
        assert r["email"] is True
        assert r["telegram"] is False

    @pytest.mark.asyncio
    async def test_user_not_found(self, dispatcher):
        db = _mdb([_emp(user_id=999), _ctr(), None])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            with patch(MOD + ".email_service") as es:
                es.send_email = AsyncMock()
                r = await dispatcher.notify_employee(db, _rec())
        assert r["internal"] is False
        assert r["telegram"] is False


class TestNoEmail:
    @pytest.mark.asyncio
    async def test_no_address(self, dispatcher):
        db = _mdb([_emp(user_id=None), _ctr(contact_email=None)])
        with patch(MOD + ".generate_salary_payslip", return_value=b"pdf"):
            r = await dispatcher.notify_employee(db, _rec())
        assert r["email"] is False
