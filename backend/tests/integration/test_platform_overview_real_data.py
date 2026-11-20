"""Обзор платформы: тренд выручки и здоровье GPS из базы, а не из вымысла.

Страница подставляла [65,45,80,55,90,70,85] как тренд выручки: выдуманные числа
под видом факта опаснее пустого графика, потому что их принимают за данные.
Подписи дней были захардкожены Пн-Вс по индексу, что неверно для скользящей недели.
Здоровье GPS не возвращалось вовсе.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal


def _add_act(db_session, company, contractor, number, day, amount):
    from app.models.finance import Act

    db_session.add(
        Act(
            document_number=number,
            client_id=contractor.id,
            company_id=company.id,
            act_date=day,
            total_amount=Decimal(amount),
            status="draft",
        )
    )
    db_session.commit()


def test_revenue_trend_comes_from_acts(
    auth_client, db_session, company, sample_contractor
):
    today = date.today()
    _add_act(db_session, company, sample_contractor, "ACT-TR-1", today, "12000")
    _add_act(
        db_session,
        company,
        sample_contractor,
        "ACT-TR-2",
        today - timedelta(days=2),
        "5000",
    )

    r = auth_client.get("/api/v1/shifts/stats/platform-overview")
    assert r.status_code == 200, r.text
    trend = r.json()["revenue_trend"]

    assert len(trend) == 7, "ожидается скользящая неделя"
    assert [d["date"] for d in trend] == [
        str(today - timedelta(days=6 - i)) for i in range(7)
    ], "даты должны идти по порядку, а не Пн-Вс по индексу"
    by_date = {d["date"]: d["revenue"] for d in trend}
    assert by_date[str(today)] == 12000.0
    assert by_date[str(today - timedelta(days=2))] == 5000.0
    assert by_date[str(today - timedelta(days=1))] == 0.0


def test_gps_health_distinguishes_no_data_from_zero_errors(auth_client):
    r = auth_client.get("/api/v1/shifts/stats/platform-overview")
    assert r.status_code == 200, r.text
    health = r.json()["gps_health"]
    assert health["samples"] == 0
    assert health["success_rate"] is None, "нет данных - не ноль процентов успеха"
    assert health["avg_ms"] is None
    assert health["errors_24h"] == 0


def test_gps_health_computes_from_the_sync_log(
    auth_client, db_session, company, sample_vehicle
):
    from app.models.telematics import GpsSyncLog

    now = datetime.now(UTC)
    for status, ms in (("success", 200), ("error", None)):
        db_session.add(
            GpsSyncLog(
                company_id=company.id,
                vehicle_id=sample_vehicle.id,
                provider_name="wialon",
                sync_type="manual",
                status=status,
                duration_ms=ms,
                created_at=now - timedelta(minutes=5),
            )
        )
    db_session.commit()

    r = auth_client.get("/api/v1/shifts/stats/platform-overview")
    assert r.status_code == 200, r.text
    health = r.json()["gps_health"]
    assert health["samples"] == 2
    assert health["success_rate"] == 50.0
    assert health["avg_ms"] == 200
    assert health["errors_24h"] == 1
