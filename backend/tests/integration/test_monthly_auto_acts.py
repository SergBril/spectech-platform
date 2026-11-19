"""Акты по завершённым сменам: документ должен создаваться, а не падать.

Прежняя задача считала часы из t.planned_start/planned_end, которых у ShiftTask
нет, и падала AttributeError до создания акта. Существующие тесты планировщика
гоняли её с мок-сессией и пустым списком смен, поэтому ветка не исполнялась.

Период передаётся явно: подмена datetime.date ломает isinstance-проверки
SQLAlchemy, а не только «сегодня» в задаче.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

PERIOD_START = date(2026, 10, 1)
PERIOD_END = date(2026, 10, 31)


@pytest.fixture
def october_shift(db_session, company, sample_vehicle, sample_contractor):
    from app.models.dispatch import Request
    from app.models.shift import ShiftReport, ShiftReportStatus, ShiftTask

    req = Request(
        client_id=sample_contractor.id,
        status="completed",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=datetime(2026, 10, 2, 8, 0),
        planned_end=datetime(2026, 10, 2, 18, 0),
        client_rate=Decimal("2500.00"),
        company_id=company.id,
    )
    db_session.add(req)
    db_session.commit()

    task = ShiftTask(
        request_id=req.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date(2026, 10, 2),
        shift_number=1,
        status="completed",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()

    db_session.add(
        ShiftReport(
            shift_task_id=task.id,
            operator_moto_hours=Decimal("8.00"),
            final_moto_hours=Decimal("8.00"),
            status=ShiftReportStatus.submitted,
            company_id=company.id,
        )
    )
    db_session.commit()
    db_session.refresh(task)
    return task


def _generate(db_session, company):
    from app.services.act_service import generate_acts_for_shifts

    return generate_acts_for_shifts(db_session, company.id, PERIOD_START, PERIOD_END)


def test_act_is_created_from_the_shift_report(
    db_session, company, october_shift, sample_contractor
):
    from app.models.finance import Act

    result = _generate(db_session, company)
    db_session.commit()
    assert result["created"] == 1, f"акт не создан: {result['skipped']}"

    act = db_session.query(Act).filter(Act.shift_task_id == october_shift.id).one()
    assert act.hours_worked == 8.0, "часы взяты не из отчёта по смене"
    assert act.client_id == sample_contractor.id, "акт без заказчика"
    assert act.hourly_rate == 2500.0, "ставка взята не из заявки"
    assert act.total_amount == Decimal("20000.00")
    assert act.document_number.startswith("ACT-")
    assert act.act_date == date(2026, 10, 2), "дата акта должна быть датой работ"


def test_vat_follows_the_document_date(db_session, company, october_shift):
    from app.models.finance import Act

    _generate(db_session, company)
    db_session.commit()
    act = db_session.query(Act).filter(Act.shift_task_id == october_shift.id).one()
    assert act.vat_rate == Decimal(
        "22.00"
    ), "НДС зашит константой вместо ставки на дату"
    assert act.vat_amount == Decimal("3606.56"), "НДС должен быть выделен из суммы"


def test_second_run_does_not_duplicate(db_session, company, october_shift):
    from app.models.finance import Act

    _generate(db_session, company)
    db_session.commit()
    result = _generate(db_session, company)
    db_session.commit()
    assert result["created"] == 0
    assert (
        db_session.query(Act).filter(Act.shift_task_id == october_shift.id).count() == 1
    )


def test_shift_without_a_rate_is_skipped_with_a_reason(
    db_session, company, october_shift
):
    """Акт с нулевой суммой выглядит документом, но им не является."""
    from app.models.catalog import Vehicle
    from app.models.dispatch import Request
    from app.models.finance import Act

    req = db_session.get(Request, october_shift.request_id)
    req.client_rate = None
    vehicle = db_session.get(Vehicle, october_shift.vehicle_id)
    vehicle.hourly_rate = None
    db_session.commit()

    result = _generate(db_session, company)
    db_session.commit()
    assert result["created"] == 0
    assert any("ставка" in s["reason"] for s in result["skipped"])
    assert (
        db_session.query(Act).filter(Act.shift_task_id == october_shift.id).count() == 0
    )


def test_shift_without_a_report_is_skipped(db_session, company, october_shift):
    from app.models.shift import ShiftReport

    db_session.query(ShiftReport).filter(
        ShiftReport.shift_task_id == october_shift.id
    ).delete()
    db_session.commit()

    result = _generate(db_session, company)
    db_session.commit()
    assert result["created"] == 0
    assert any("выработк" in s["reason"] for s in result["skipped"])


def test_endpoint_creates_the_act(auth_client, db_session, company, october_shift):
    """Тот же путь, но через API: раньше падал на Act(driver_name=, distance_km=)."""
    from app.models.finance import Act

    r = auth_client.post(
        "/api/v1/shifts/acts/auto-generate",
        json={"date_from": "2026-10-01", "date_to": "2026-10-31"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1, r.text

    act = db_session.query(Act).filter(Act.shift_task_id == october_shift.id).one()
    assert act.hours_worked == 8.0
    assert act.total_amount == Decimal("20000.00")
    assert act.created_by is not None, "автор документа не записан"


def test_endpoint_reports_why_a_shift_was_skipped(
    auth_client, db_session, company, october_shift
):
    from app.models.shift import ShiftReport

    db_session.query(ShiftReport).filter(
        ShiftReport.shift_task_id == october_shift.id
    ).delete()
    db_session.commit()

    r = auth_client.post(
        "/api/v1/shifts/acts/auto-generate",
        json={"date_from": "2026-10-01", "date_to": "2026-10-31"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 0
    assert body["skipped"] == 1
    assert "выработк" in body["skipped_reasons"][0]["reason"]
