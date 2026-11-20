"""Прибыльность по технике: часы должны доходить до денег.

Часы брались из getattr(ShiftTask, "planned_end") - "planned_start". У смены нет
полей времени, оба getattr давали None, и часы всегда были нулём. Зарплата и
амортизация обнулялись: себестоимость занижена, маржа завышена. Отчёт выглядел
правдоподобно - нулевая строка затрат читается как «не тратили», а не «не посчитали».
"""

from datetime import date, datetime
from decimal import Decimal

import pytest


@pytest.fixture
def worked_shift(db_session, company, sample_vehicle, sample_contractor):
    from app.models.dispatch import Request
    from app.models.finance import Act
    from app.models.shift import (
        CompanyCostRates,
        ShiftFuelEntry,
        ShiftReport,
        ShiftReportStatus,
        ShiftTask,
    )

    db_session.add(
        CompanyCostRates(
            company_id=company.id,
            fuel_price_per_liter=Decimal("70"),
            hourly_wage=Decimal("600"),
            amortization_per_hour=Decimal("400"),
        )
    )
    req = Request(
        client_id=company.id,
        company_id=company.id,
        status="completed",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=datetime(2026, 11, 10, 8, 0),
        planned_end=datetime(2026, 11, 10, 18, 0),
    )
    db_session.add(req)
    db_session.commit()
    task = ShiftTask(
        request_id=req.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date(2026, 11, 10),
        shift_number=1,
        status="completed",
        company_id=company.id,
        operator_id=sample_contractor.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.add(
        ShiftReport(
            shift_task_id=task.id,
            operator_moto_hours=Decimal("8"),
            final_moto_hours=Decimal("8"),
            status=ShiftReportStatus.submitted,
            company_id=company.id,
        )
    )
    db_session.add(
        ShiftFuelEntry(
            shift_task_id=task.id,
            vehicle_id=sample_vehicle.id,
            quantity_liters=Decimal("100"),
        )
    )
    db_session.add(
        Act(
            document_number="ACT-PNL-0001",
            client_id=sample_contractor.id,
            company_id=company.id,
            vehicle_id=sample_vehicle.id,
            act_date=date(2026, 11, 10),
            total_amount=Decimal("100000"),
            status="draft",
        )
    )
    db_session.commit()
    return task


def test_pnl_counts_wage_and_amortization_from_worked_hours(
    auth_client, sample_vehicle, worked_shift
):
    r = auth_client.get(
        "/api/v1/shifts/stats/pnl",
        params={"date_from": "2026-11-01", "date_to": "2026-11-30"},
    )
    assert r.status_code == 200, r.text
    rows = r.json()["vehicles"]
    row = next(v for v in rows if v["vehicle_id"] == sample_vehicle.id)

    assert row["hours"] == 8.0, "наработка не дошла до отчёта"
    assert row["wage_cost"] == 4800.0, "8 ч x 600"
    assert row["amortization_cost"] == 3200.0, "8 ч x 400"
    assert row["fuel_cost"] == 7000.0, "100 л x 70"
    assert row["total_expenses"] == 15000.0
    assert row["margin"] == 85000.0, "маржа завышена, если затраты обнулены"


def test_utilization_export_reports_real_hours(
    auth_client, sample_vehicle, worked_shift
):
    import io

    import openpyxl

    r = auth_client.get(
        "/api/v1/shifts/stats/utilization/export",
        params={"date_from": "2026-11-01", "date_to": "2026-11-30"},
    )
    assert r.status_code == 200, r.text
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    ws = wb.active
    header = [c.value for c in ws[1]]
    hours_col = header.index("Часов") + 1
    name_col = header.index("Техника") + 1
    values = {
        ws.cell(row=i, column=name_col).value: ws.cell(row=i, column=hours_col).value
        for i in range(2, ws.max_row + 1)
    }
    assert values.get(sample_vehicle.name) == 8.0, f"часы в экспорте: {values}"


def test_cost_forecast_includes_wage_and_amortization(auth_client, worked_shift):
    """Прогноз затрат показывал только топливо: часы были нулём."""
    r = auth_client.get("/api/v1/shifts/stats/cost-forecast")
    assert r.status_code == 200, r.text
    body = r.json()
    actual = body["actual_90d"]
    forecast = body["forecast"]
    assert actual["total_hours"] > 0, f"наработка обнулена: {actual}"
    assert actual["wage_cost"] > 0, f"зарплата обнулена: {actual}"
    assert actual["amortization_cost"] > 0, f"амортизация обнулена: {actual}"
    assert forecast["wage_cost"] > 0, f"прогноз без зарплаты: {forecast}"
    assert forecast["amortization_cost"] > 0, f"прогноз без амортизации: {forecast}"
