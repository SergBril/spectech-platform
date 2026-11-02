"""Модуль stats для shifts router — тонкие wrapper'ы над ShiftStatsService."""

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user
from app.services.shift_stats_service import shift_stats_service

router = APIRouter()

@router.get("/stats/utilization")
def get_utilization_stats(
    date_from: str = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: str = Query(..., description="Конец периода YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика использования техники: % дней со сменами, часы работы, простои."""
    return shift_stats_service.get_utilization_stats(db=db, company_id=company_id, date_from=date_from, date_to=date_to)


@router.get("/stats/utilization/export")
def export_utilization_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт статистики утилизации техники в Excel."""
    return shift_stats_service.export_utilization_excel(db=db, company_id=company_id, date_from=date_from, date_to=date_to)


@router.get("/stats/driver-kpi")
def get_driver_kpi(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """KPI водителей: часы работы, количество смен, утилизация, рейтинг."""
    return shift_stats_service.get_driver_kpi(db=db, company_id=company_id, date_from=date_from, date_to=date_to)


@router.get("/stats/driver-kpi/export")
def export_driver_kpi_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт KPI водителей в Excel с рейтингом."""
    return shift_stats_service.export_driver_kpi_excel(db=db, company_id=company_id, date_from=date_from, date_to=date_to)


@router.get("/stats/fuel")
def get_fuel_consumption_stats(
    date_from: str = Query(...),
    date_to: str = Query(...),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика расхода топлива по технике за период."""
    return shift_stats_service.get_fuel_consumption_stats(db=db, company_id=company_id, date_from=date_from, date_to=date_to, vehicle_id=vehicle_id)


@router.get("/stats/fuel/export")
def export_fuel_consumption_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт записей расхода топлива в Excel."""
    return shift_stats_service.export_fuel_consumption_excel(db=db, company_id=company_id, date_from=date_from, date_to=date_to, vehicle_id=vehicle_id)


@router.get("/stats/fuel-dashboard")
def get_fuel_dashboard(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Дашборд расхода топлива: тренды, аномалии, топ потребителей."""
    return shift_stats_service.get_fuel_dashboard(db=db, company_id=company_id, date_from=date_from, date_to=date_to)


@router.get("/stats/cost-per-hour")
def get_cost_per_hour_report(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отчёт себестоимости моточаса: топливо + зарплата водителя + амортизация."""
    return shift_stats_service.get_cost_per_hour_report(db=db, company_id=company_id, current_user=current_user, date_from=date_from, date_to=date_to)


@router.get("/stats/cost-per-hour/export")
def export_cost_per_hour_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт отчёта себестоимости моточаса в Excel."""
    return shift_stats_service.export_cost_per_hour_excel(db=db, company_id=company_id, current_user=current_user, date_from=date_from, date_to=date_to)


@router.get("/stats/cost-rates")
def get_cost_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить текущие ставки для расчёта себестоимости."""
    return shift_stats_service.get_cost_rates(db=db, company_id=company_id)


@router.patch("/stats/cost-rates")
def update_cost_rates(
    fuel_price_per_liter: float = Body(...),
    hourly_wage: float = Body(...),
    amortization_per_hour: float = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить ставки для расчёта себестоимости моточаса."""
    return shift_stats_service.update_cost_rates(db=db, company_id=company_id, current_user=current_user, fuel_price_per_liter=fuel_price_per_liter, hourly_wage=hourly_wage, amortization_per_hour=amortization_per_hour)


@router.get("/stats/cost-forecast")
def get_cost_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Прогноз расходов на следующий месяц на основе трендов за последние 90 дней."""
    return shift_stats_service.get_cost_forecast(db=db, company_id=company_id)


@router.get("/stats/pnl")
def get_pnl_per_vehicle(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отчёт прибыльности по каждой единице техники: выручка - расходы = маржа."""
    return shift_stats_service.get_pnl_per_vehicle(db=db, company_id=company_id, current_user=current_user, date_from=date_from, date_to=date_to)


@router.get("/stats/pnl/export")
def export_pnl_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт отчёта прибыльности по технике в Excel."""
    return shift_stats_service.export_pnl_excel(db=db, company_id=company_id, current_user=current_user, date_from=date_from, date_to=date_to)


@router.get("/stats/platform-overview")
def get_platform_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обзор платформы: пользователи, техника, акты, финансы, активность."""
    return shift_stats_service.get_platform_overview(db=db, company_id=company_id)


@router.get("/stats/recent-actions")
def get_recent_actions(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Последние действия из audit log для dashboard виджета."""
    return shift_stats_service.get_recent_actions(db=db, company_id=company_id, limit=limit)
