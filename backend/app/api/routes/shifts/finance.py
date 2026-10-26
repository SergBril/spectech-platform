"""Модуль finance для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.finance import Act
from app.models.shift import ShiftTask, ShiftFuelEntry, CompanyCostRates
from app.models.catalog import Vehicle
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user, get_user_company_ids

from app.models.finance import Act
from app.models.shift import ShiftTask, ShiftFuelEntry, CompanyCostRates
from app.models.catalog import Vehicle

router = APIRouter()

def get_finance_dashboard(
    year: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Финансовый дашборд: выручка (акты), расходы (топливо+зарплата), маржа по месяцам."""
    from datetime import date as date_type
    from sqlalchemy import func, extract
    from app.models.shift import ShiftFuelEntry, CompanyCostRates

    target_year = year or date_type.today().year

    # Revenue: sum of acts by month
    revenue_by_month = db.execute(
        select(
            extract('month', Act.act_date).label('month'),
            func.coalesce(func.sum(Act.total_amount), 0).label('revenue'),
        )
        .where(Act.company_id == company_id)
        .where(extract('year', Act.act_date) == target_year)
        .group_by('month')
        .order_by('month')
    ).all()

    revenue_map = {int(r.month): float(r.revenue) for r in revenue_by_month}

    # Expenses: fuel + wage + amortization by month
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(extract('year', ShiftTask.shift_date) == target_year)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(extract('year', ShiftTask.shift_date) == target_year)
    ).scalars().all()

    # Load rates
    company_rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()
    fuel_price = company_rates.fuel_price_per_liter if company_rates else 65.0
    hourly_wage = company_rates.hourly_wage if company_rates else 500.0
    amort_rate = company_rates.amortization_per_hour if company_rates else 300.0

    monthly_expenses = {}
    for t in tasks:
        m = t.shift_date.month
        if m not in monthly_expenses:
            monthly_expenses[m] = {"fuel": 0, "wage": 0, "amort": 0}
        hours = max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None) else 0
        monthly_expenses[m]["wage"] += hours * hourly_wage
        monthly_expenses[m]["amort"] += hours * amort_rate

    for f_entry in fuel_entries:
        task = db.get(ShiftTask, f_entry.shift_task_id)
        if task:
            m = task.shift_date.month
            if m not in monthly_expenses:
                monthly_expenses[m] = {"fuel": 0, "wage": 0, "amort": 0}
            monthly_expenses[m]["fuel"] += f_entry.quantity_liters * fuel_price

    month_names = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    months_data = []
    total_revenue = 0
    total_expenses = 0

    for m in range(1, 13):
        rev = revenue_map.get(m, 0)
        exp_data = monthly_expenses.get(m, {"fuel": 0, "wage": 0, "amort": 0})
        total_exp = round(exp_data["fuel"] + exp_data["wage"] + exp_data["amort"], 2)
        margin = round(rev - total_exp, 2)
        margin_pct = round((margin / rev) * 100, 1) if rev > 0 else 0

        months_data.append({
            "month": m, "month_name": month_names[m - 1],
            "revenue": round(rev, 2),
            "fuel_cost": round(exp_data["fuel"], 2),
            "wage_cost": round(exp_data["wage"], 2),
            "amortization_cost": round(exp_data["amort"], 2),
            "total_expenses": total_exp,
            "margin": margin,
            "margin_pct": margin_pct,
        })
        total_revenue += rev
        total_expenses += total_exp

    total_margin = round(total_revenue - total_expenses, 2)
    total_margin_pct = round((total_margin / total_revenue) * 100, 1) if total_revenue > 0 else 0

    return {
        "year": target_year,
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_expenses": round(total_expenses, 2),
            "total_margin": total_margin,
            "total_margin_pct": total_margin_pct,
        },
        "months": months_data,
    }



def export_finance_dashboard_excel(
    year: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт финансового дашборда в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, numbers
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    # Reuse dashboard logic
    report = get_finance_dashboard(year, db, current_user, company_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Финансы {report['year']}"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    green_font = Font(color="006100", bold=True)
    red_font = Font(color="9C0006", bold=True)

    # Summary section
    ws.cell(row=1, column=1, value=f"Финансовый отчёт за {report['year']} год").font = Font(bold=True, size=14)
    summary = report["summary"]
    ws.cell(row=3, column=1, value="Выручка").font = Font(bold=True)
    ws.cell(row=3, column=2, value=summary["total_revenue"]).number_format = '#,##0'
    ws.cell(row=4, column=1, value="Расходы").font = Font(bold=True)
    ws.cell(row=4, column=2, value=summary["total_expenses"]).number_format = '#,##0'
    ws.cell(row=5, column=1, value="Маржа").font = Font(bold=True)
    ws.cell(row=5, column=2, value=summary["total_margin"]).number_format = '#,##0'
    ws.cell(row=6, column=1, value="Рентабельность").font = Font(bold=True)
    ws.cell(row=6, column=2, value=summary["total_margin_pct"]).number_format = '0.0"%"'

    # Monthly table
    headers = ["Месяц", "Выручка", "Топливо", "Зарплата", "Амортизация", "Всего расходов", "Маржа", "Маржа %"]
    start_row = 8
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, m in enumerate(report["months"], start_row + 1):
        ws.cell(row=row_idx, column=1, value=m["month_name"])
        ws.cell(row=row_idx, column=2, value=m["revenue"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=3, value=m["fuel_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=4, value=m["wage_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=5, value=m["amortization_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=6, value=m["total_expenses"]).number_format = '#,##0'
        margin_cell = ws.cell(row=row_idx, column=7, value=m["margin"])
        margin_cell.number_format = '#,##0'
        margin_cell.font = green_font if m["margin"] >= 0 else red_font
        ws.cell(row=row_idx, column=8, value=m["margin_pct"]).number_format = '0.0"%"'

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 20)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"finance_{report['year']}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# === Bank Integration ===


