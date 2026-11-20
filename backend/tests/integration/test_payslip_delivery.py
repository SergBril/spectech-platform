"""Расчётный листок: уведомление и письмо должны действительно уходить.

В одном вызове было четыре дефекта: create_notification без await (корутина не
исполнялась, в логе успех), await у синхронного send_email (TypeError), параметр
to= вместо to_email= (TypeError) и вложение кортежем вместо словаря. Исключения
глотались, поэтому рассылка выглядела успешной при полностью отсутствующем письме.

Отправка подменена перехватом: реальных писем тест не отправляет.
"""

from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def salary_record(db_session, company, sample_contractor, admin_user):
    from app.models.contractor import Employee
    from app.models.salary import SalaryRecord

    db_session.add(
        Employee(
            contractor_id=sample_contractor.id,
            user_id=admin_user.id,
            role_in_system="driver",
        )
    )
    rec = SalaryRecord(
        company_id=company.id,
        employee_contractor_id=sample_contractor.id,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 15),
        salary_type="hourly",
        net_amount=Decimal("50000"),
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)
    return rec


async def test_payslip_creates_notification_and_calls_email_correctly(
    db_session, salary_record, admin_user, monkeypatch
):
    from app.models.telematics import Notification
    from app.services import salary_notification_dispatcher as mod

    sent = {}

    def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(mod.email_service, "send_email", fake_send_email)
    monkeypatch.setattr(
        mod, "generate_salary_payslip", lambda *a, **k: b"%PDF-1.4 " + b"x" * 200
    )

    results = await mod.salary_notification_dispatcher.notify_employee(
        db_session, salary_record, "Начальник участка"
    )

    assert results["internal"] is True, f"внутреннее уведомление не создано: {results}"
    rows = (
        db_session.query(Notification)
        .filter(Notification.user_id == admin_user.id)
        .all()
    )
    assert any(
        "Расчётный листок" in (n.title or "") for n in rows
    ), "уведомления нет в базе"

    assert results["email"] is True, f"письмо не отправлено: {results}"
    assert sent.get("to_email"), f"неверный параметр получателя: {list(sent)}"
    assert isinstance(sent["attachments"][0], dict), "вложение должно быть словарём"
    assert sent["attachments"][0]["filename"] == "payslip.pdf"
