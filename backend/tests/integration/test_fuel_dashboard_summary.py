"""RC-5: FuelDashboard при пустых данных возвращает нулевую форму summary.

Дефект: get_fuel_dashboard в пустом случае возвращал summary:{} - карточки
frontend/src/pages/FuelDashboardPage.tsx читали data.summary.total_liters и др.
как undefined/NaN. Отсутствие топлива - ноль литров той же формы, что и в
непустом случае, а не отсутствие поля.
"""

from datetime import date, datetime, timedelta

from app.services.shift_stats_service import shift_stats_service

SUMMARY_KEYS = {
    "total_liters",
    "avg_daily_liters",
    "total_entries",
    "vehicles_count",
    "anomalies_count",
}


def test_empty_fuel_dashboard_summary_is_zero_not_missing(db_session, company):
    today = date.today().isoformat()
    result = shift_stats_service.get_fuel_dashboard(
        db_session, company.id, today, today
    )

    assert (
        set(result["summary"]) == SUMMARY_KEYS
    ), "форма summary должна совпадать с непустым случаем"
    assert result["summary"] == {
        "total_liters": 0,
        "avg_daily_liters": 0,
        "total_entries": 0,
        "vehicles_count": 0,
        "anomalies_count": 0,
    }
    assert result["daily_trend"] == []
    assert result["anomalies"] == []
    assert result["top_consumers"] == []
    assert result["period"] == {"from": today, "to": today}


def test_nonempty_fuel_dashboard_summary_same_shape(
    db_session, company, sample_contractor, sample_vehicle
):
    from app.models.dispatch import Request
    from app.models.shift import ShiftFuelEntry, ShiftTask

    now = datetime.now()
    req = Request(
        client_id=sample_contractor.id,
        status="in_progress",
        request_type="one_time",
        work_type="Earthworks",
        planned_start=now,
        planned_end=now + timedelta(days=1),
        company_id=company.id,
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    task = ShiftTask(
        request_id=req.id,
        vehicle_id=sample_vehicle.id,
        shift_date=date.today(),
        status="completed",
        company_id=company.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    entry = ShiftFuelEntry(
        shift_task_id=task.id,
        vehicle_id=sample_vehicle.id,
        quantity_liters=100.0,
    )
    db_session.add(entry)
    db_session.commit()

    today = date.today().isoformat()
    result = shift_stats_service.get_fuel_dashboard(
        db_session, company.id, today, today
    )

    # форма непустого случая совпадает с пустым (те же ключи)
    assert set(result["summary"]) == SUMMARY_KEYS
    assert result["summary"]["total_liters"] == 100.0
    assert result["summary"]["total_entries"] == 1
    assert result["summary"]["vehicles_count"] == 1
