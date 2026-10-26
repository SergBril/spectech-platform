"""Модуль stats для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.catalog import Vehicle
from app.models.shift import ShiftTask, ShiftFuelEntry, CompanyCostRates, DocumentArchive
from app.models.finance import Act
from app.models.bank_statement import BankTransaction
from app.models.contractor import DriverProfile, Employee
from app.models.auth import User
from app.api.deps import get_current_company_id, get_current_user

router = APIRouter()

def get_utilization_stats(
    date_from: str = Query(..., description="Начало периода YYYY-MM-DD"),
    date_to: str = Query(..., description="Конец периода YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика использования техники: % дней со сменами, часы работы, простои."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    # Get all company vehicles
    vehicles = db.execute(
        select(Vehicle).where(Vehicle.company_id == company_id)
    ).scalars().all()

    # Get shifts in period
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    # Per-vehicle stats
    vehicle_stats = []
    for v in vehicles:
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        active_days = len(set(t.shift_date for t in v_tasks))
        utilization_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0

        total_hours = 0
        for t in v_tasks:
            if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None):
                delta = (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600
                total_hours += max(0, delta)

        vehicle_stats.append({
            "vehicle_id": v.id,
            "vehicle_name": v.name,
            "active_days": active_days,
            "total_days": total_days,
            "utilization_pct": utilization_pct,
            "total_hours": round(total_hours, 1),
            "shift_count": len(v_tasks),
        })

    # Summary
    total_vehicles = len(vehicles)
    avg_utilization = round(sum(s["utilization_pct"] for s in vehicle_stats) / total_vehicles, 1) if total_vehicles > 0 else 0

    return {
        "period": {"from": str(d_from), "to": str(d_to), "days": total_days},
        "summary": {
            "total_vehicles": total_vehicles,
            "avg_utilization_pct": avg_utilization,
            "total_shifts": len(tasks),
            "total_hours": round(sum(s["total_hours"] for s in vehicle_stats), 1),
        },
        "vehicles": sorted(vehicle_stats, key=lambda x: x["utilization_pct"], reverse=True),
    }



def export_utilization_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт статистики утилизации техники в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Утилизация"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Техника", "Активные дни", "Всего дней", "Утилизация %", "Смен", "Часов"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    row_idx = 2
    total_shifts = 0
    total_hours = 0
    util_sum = 0

    for v in sorted(vehicles, key=lambda x: x.name):
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        active_days = len(set(t.shift_date for t in v_tasks))
        util_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0
        hours = sum(max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) for t in v_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None))

        ws.cell(row=row_idx, column=1, value=v.name)
        ws.cell(row=row_idx, column=2, value=active_days)
        ws.cell(row=row_idx, column=3, value=total_days)
        ws.cell(row=row_idx, column=4, value=util_pct)
        ws.cell(row=row_idx, column=5, value=len(v_tasks))
        ws.cell(row=row_idx, column=6, value=round(hours, 1))

        # Color code utilization
        if util_pct >= 80:
            ws.cell(row=row_idx, column=4).fill = PatternFill(start_color="C6EFCE", fill_type="solid")
        elif util_pct >= 50:
            ws.cell(row=row_idx, column=4).fill = PatternFill(start_color="FFEB9C", fill_type="solid")
        else:
            ws.cell(row=row_idx, column=4).fill = PatternFill(start_color="FFC7CE", fill_type="solid")

        total_shifts += len(v_tasks)
        total_hours += hours
        util_sum += util_pct
        row_idx += 1

    # Totals
    avg_util = round(util_sum / len(vehicles), 1) if vehicles else 0
    ws.cell(row=row_idx, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=row_idx, column=4, value=avg_util).font = Font(bold=True)
    ws.cell(row=row_idx, column=5, value=total_shifts).font = Font(bold=True)
    ws.cell(row=row_idx, column=6, value=round(total_hours, 1)).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"utilization_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})



def get_driver_kpi(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """KPI водителей: часы работы, количество смен, утилизация, рейтинг."""
    from datetime import date as date_type, timedelta
    from app.models.contractor import DriverProfile, Employee

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(getattr(Employee, 'company_id', None) == company_id)
    ).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
        
    ).scalars().all()

    kpi_list = []
    for profile in drivers:
        emp = db.get(Employee, profile.employee_contractor_id)
        driver_name = f"{emp.first_name} {emp.last_name}" if emp else f"Driver#{profile.employee_contractor_id}"

        d_tasks = [t for t in tasks if t.operator_id == profile.employee_contractor_id]
        active_days = len(set(t.shift_date for t in d_tasks))
        utilization_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0

        total_hours = sum(
            max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)
            for t in d_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None)
        )

        completed = len([t for t in d_tasks if t.status == "completed"])
        completion_rate = round((completed / len(d_tasks)) * 100, 1) if d_tasks else 0

        # Simple rating: weighted score
        rating = round(utilization_pct * 0.4 + completion_rate * 0.3 + min(total_hours / max(total_days, 1), 10) * 3, 1)

        kpi_list.append({
            "driver_id": profile.employee_contractor_id,
            "driver_name": driver_name,
            "shift_count": len(d_tasks),
            "active_days": active_days,
            "total_days": total_days,
            "utilization_pct": utilization_pct,
            "total_hours": round(total_hours, 1),
            "completion_rate": completion_rate,
            "rating": rating,
        })

    kpi_list.sort(key=lambda x: x["rating"], reverse=True)

    return {
        "period": {"from": str(d_from), "to": str(d_to), "days": total_days},
        "drivers": kpi_list,
    }



def export_driver_kpi_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт KPI водителей в Excel с рейтингом."""
    import io
    from datetime import date as date_type, timedelta
    from fastapi.responses import StreamingResponse
    from app.models.contractor import DriverProfile, Employee

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    total_days = (d_to - d_from).days + 1

    drivers = db.execute(
        select(DriverProfile)
        .join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(getattr(Employee, 'company_id', None) == company_id)
    ).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
        
    ).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "KPI Водителей"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["#", "Водитель", "Рейтинг", "Смен", "Активные дни", "Утилизация %", "Часов", "Завершение %"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    kpi_rows = []
    for profile in drivers:
        emp = db.get(Employee, profile.employee_contractor_id)
        name = f"{emp.first_name} {emp.last_name}" if emp else f"Driver#{profile.employee_contractor_id}"
        d_tasks = [t for t in tasks if t.operator_id == profile.employee_contractor_id]
        active_days = len(set(t.shift_date for t in d_tasks))
        util_pct = round((active_days / total_days) * 100, 1) if total_days > 0 else 0
        hours = sum(max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) for t in d_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None))
        completed = len([t for t in d_tasks if t.status == "completed"])
        comp_rate = round((completed / len(d_tasks)) * 100, 1) if d_tasks else 0
        rating = round(util_pct * 0.4 + comp_rate * 0.3 + min(hours / max(total_days, 1), 10) * 3, 1)
        kpi_rows.append((name, rating, len(d_tasks), active_days, util_pct, round(hours, 1), comp_rate))

    kpi_rows.sort(key=lambda x: x[1], reverse=True)

    green_fill = PatternFill(start_color="C6EFCE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", fill_type="solid")

    for row_idx, (name, rating, shifts, adays, util, hrs, comp) in enumerate(kpi_rows, 2):
        ws.cell(row=row_idx, column=1, value=row_idx - 1)
        ws.cell(row=row_idx, column=2, value=name)
        ws.cell(row=row_idx, column=3, value=rating)
        ws.cell(row=row_idx, column=4, value=shifts)
        ws.cell(row=row_idx, column=5, value=adays)
        ws.cell(row=row_idx, column=6, value=util)
        ws.cell(row=row_idx, column=7, value=hrs)
        ws.cell(row=row_idx, column=8, value=comp)

        fill = green_fill if rating >= 70 else yellow_fill if rating >= 40 else red_fill
        ws.cell(row=row_idx, column=3).fill = fill

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"driver_kpi_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})



def get_fuel_consumption_stats(
    date_from: str = Query(...),
    date_to: str = Query(...),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Статистика расхода топлива по технике за период."""
    from datetime import date as date_type
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    stmt = (
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    )
    if vehicle_id:
        stmt = stmt.where(ShiftFuelEntry.vehicle_id == vehicle_id)

    entries = db.execute(stmt).scalars().all()

    # Group by vehicle
    vehicle_stats = {}
    for e in entries:
        vid = e.vehicle_id
        if vid not in vehicle_stats:
            v = db.get(Vehicle, vid)
            vehicle_stats[vid] = {"vehicle_name": v.name if v else "", "total_liters": 0, "entries": 0}
        vehicle_stats[vid]["total_liters"] += e.quantity_liters
        vehicle_stats[vid]["entries"] += 1

    result = []
    for vid, stats in vehicle_stats.items():
        result.append({
            "vehicle_id": vid,
            "vehicle_name": stats["vehicle_name"],
            "total_liters": round(stats["total_liters"], 2),
            "entries_count": stats["entries"],
            "avg_per_entry": round(stats["total_liters"] / stats["entries"], 2) if stats["entries"] > 0 else 0,
        })

    result.sort(key=lambda x: x["total_liters"], reverse=True)

    total_liters = sum(s["total_liters"] for s in result)
    return {
        "period": {"from": str(d_from), "to": str(d_to)},
        "total_liters": round(total_liters, 2),
        "vehicles": result,
    }



def export_fuel_consumption_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт записей расхода топлива в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse
    from app.models.shift import ShiftFuelEntry

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    stmt = (
        select(ShiftFuelEntry, ShiftTask.shift_date, Vehicle.name.label("vehicle_name"))
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    )
    if vehicle_id:
        stmt = stmt.where(ShiftFuelEntry.vehicle_id == vehicle_id)
    stmt = stmt.order_by(ShiftTask.shift_date.desc())

    rows = db.execute(stmt).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Расход топлива"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Дата", "Техника", "Тип топлива", "Литры", "Пробег (км)", "Моточасы", "Заметки"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    total_liters = 0
    for row_idx, (entry, shift_date, vname) in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=str(shift_date))
        ws.cell(row=row_idx, column=2, value=vname or "")
        ws.cell(row=row_idx, column=3, value=entry.fuel_type or "diesel")
        ws.cell(row=row_idx, column=4, value=entry.quantity_liters)
        ws.cell(row=row_idx, column=5, value=entry.odometer_reading or "")
        ws.cell(row=row_idx, column=6, value=entry.engine_hours or "")
        ws.cell(row=row_idx, column=7, value=entry.notes or "")
        total_liters += entry.quantity_liters

    # Totals row
    last_row = len(rows) + 2
    ws.cell(row=last_row, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=last_row, column=4, value=round(total_liters, 2)).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 30)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"fuel_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# === Checklist Configs ===


def get_fuel_dashboard(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Дашборд расхода топлива: тренды, аномалии, топ потребителей."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func, extract
    from app.models.shift import ShiftFuelEntry

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    entries = db.execute(
        select(ShiftFuelEntry, ShiftTask.shift_date, Vehicle.name.label("vehicle_name"), Vehicle.id.label("vid"))
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .order_by(ShiftTask.shift_date)
    ).all()

    if not entries:
        return {"period": {"from": str(d_from), "to": str(d_to)}, "daily_trend": [], "anomalies": [], "top_consumers": [], "summary": {}}

    # Daily trend
    daily = {}
    for entry, sdate, vname, vid in entries:
        key = str(sdate)
        if key not in daily:
            daily[key] = {"date": key, "liters": 0, "entries": 0}
        daily[key]["liters"] += entry.quantity_liters
        daily[key]["entries"] += 1

    daily_trend = sorted(daily.values(), key=lambda x: x["date"])

    # Per-vehicle totals
    vehicle_totals = {}
    for entry, sdate, vname, vid in entries:
        if vid not in vehicle_totals:
            vehicle_totals[vid] = {"vehicle_name": vname, "total_liters": 0, "entries": 0, "values": []}
        vehicle_totals[vid]["total_liters"] += entry.quantity_liters
        vehicle_totals[vid]["entries"] += 1
        vehicle_totals[vid]["values"].append(entry.quantity_liters)

    # Anomaly detection: values > mean + 2*stddev per vehicle
    anomalies = []
    for vid, stats in vehicle_totals.items():
        vals = stats["values"]
        if len(vals) < 3:
            continue
        mean_val = sum(vals) / len(vals)
        variance = sum((v - mean_val) ** 2 for v in vals) / len(vals)
        stddev = variance ** 0.5
        threshold = mean_val + 2 * stddev

        for entry, sdate, vname, evid in entries:
            if evid == vid and entry.quantity_liters > threshold and stddev > 0:
                anomalies.append({
                    "vehicle_name": vname,
                    "date": str(sdate),
                    "liters": entry.quantity_liters,
                    "mean": round(mean_val, 2),
                    "threshold": round(threshold, 2),
                    "deviation_pct": round(((entry.quantity_liters - mean_val) / mean_val) * 100, 1),
                })

    anomalies.sort(key=lambda x: x["deviation_pct"], reverse=True)

    # Top consumers
    top_consumers = sorted(
        [{"vehicle_id": vid, "vehicle_name": s["vehicle_name"], "total_liters": round(s["total_liters"], 2), "entries": s["entries"]}
         for vid, s in vehicle_totals.items()],
        key=lambda x: x["total_liters"], reverse=True
    )[:10]

    total_liters = sum(s["total_liters"] for s in vehicle_totals.values())
    avg_daily = round(total_liters / max(len(daily_trend), 1), 2)

    return {
        "period": {"from": str(d_from), "to": str(d_to)},
        "summary": {
            "total_liters": round(total_liters, 2),
            "avg_daily_liters": avg_daily,
            "total_entries": len(entries),
            "vehicles_count": len(vehicle_totals),
            "anomalies_count": len(anomalies),
        },
        "daily_trend": daily_trend,
        "anomalies": anomalies[:20],
        "top_consumers": top_consumers,
    }



def get_cost_per_hour_report(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отчёт себестоимости моточаса: топливо + зарплата водителя + амортизация."""
    from datetime import date as date_type
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry
    from app.models.contractor import DriverProfile, Employee

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    ).scalars().all()

    # Default rates (can be configured per vehicle/driver later)
    DEFAULT_FUEL_PRICE = 65.0  # ₽/литр дизеля
    DEFAULT_HOURLY_WAGE = 500.0  # ₽/час водитель
    DEFAULT_AMORTIZATION = 300.0  # ₽/час амортизация

    result = []
    total_cost = 0
    total_hours = 0

    for v in vehicles:
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        v_fuel = [f for f in fuel_entries if f.vehicle_id == v.id]

        hours = sum(
            max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)
            for t in v_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None)
        )
        fuel_liters = sum(f.quantity_liters for f in v_fuel)

        fuel_cost = fuel_liters * DEFAULT_FUEL_PRICE
        wage_cost = hours * DEFAULT_HOURLY_WAGE
        amort_cost = hours * DEFAULT_AMORTIZATION
        total = fuel_cost + wage_cost + amort_cost
        cost_per_hour = round(total / hours, 2) if hours > 0 else 0

        driver_name = ""
        if v_tasks:
            first_driver = next((t.operator_id for t in v_tasks if t.operator_id), None)
            if first_driver:
                emp = db.get(Employee, first_driver)
                driver_name = f"{emp.first_name} {emp.last_name}" if emp else ""

        result.append({
            "vehicle_id": v.id,
            "vehicle_name": v.name,
            "driver_name": driver_name,
            "hours": round(hours, 1),
            "fuel_liters": round(fuel_liters, 2),
            "fuel_cost": round(fuel_cost, 2),
            "wage_cost": round(wage_cost, 2),
            "amortization_cost": round(amort_cost, 2),
            "total_cost": round(total, 2),
            "cost_per_hour": cost_per_hour,
        })

        total_cost += total
        total_hours += hours

    result.sort(key=lambda x: x["cost_per_hour"], reverse=True)

    avg_cost_per_hour = round(total_cost / total_hours, 2) if total_hours > 0 else 0

    return {
        "period": {"from": str(d_from), "to": str(d_to)},
        "rates": {"fuel_price": DEFAULT_FUEL_PRICE, "hourly_wage": DEFAULT_HOURLY_WAGE, "amortization": DEFAULT_AMORTIZATION},
        "summary": {
            "total_cost": round(total_cost, 2),
            "total_hours": round(total_hours, 1),
            "avg_cost_per_hour": avg_cost_per_hour,
            "vehicles_count": len([r for r in result if r["hours"] > 0]),
        },
        "vehicles": result,
    }



def export_cost_per_hour_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт отчёта себестоимости моточаса в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse
    from app.models.shift import ShiftFuelEntry
    from app.models.contractor import Employee

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    # Reuse same logic as get_cost_per_hour_report
    report_data = get_cost_per_hour_report(date_from, date_to, db, current_user, company_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Себестоимость моточаса"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    headers = ["Техника", "Водитель", "Часов", "Топливо (л)", "Топливо (₽)", "Зарплата (₽)", "Амортизация (₽)", "Итого (₽)", "₽/час"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, v in enumerate(report_data["vehicles"], 2):
        ws.cell(row=row_idx, column=1, value=v["vehicle_name"])
        ws.cell(row=row_idx, column=2, value=v["driver_name"])
        ws.cell(row=row_idx, column=3, value=v["hours"])
        ws.cell(row=row_idx, column=4, value=v["fuel_liters"])
        ws.cell(row=row_idx, column=5, value=v["fuel_cost"])
        ws.cell(row=row_idx, column=6, value=v["wage_cost"])
        ws.cell(row=row_idx, column=7, value=v["amortization_cost"])
        ws.cell(row=row_idx, column=8, value=v["total_cost"])
        ws.cell(row=row_idx, column=9, value=v["cost_per_hour"])

    # Totals
    last_row = len(report_data["vehicles"]) + 2
    ws.cell(row=last_row, column=1, value="ИТОГО").font = Font(bold=True)
    ws.cell(row=last_row, column=3, value=report_data["summary"]["total_hours"]).font = Font(bold=True)
    ws.cell(row=last_row, column=8, value=report_data["summary"]["total_cost"]).font = Font(bold=True)
    ws.cell(row=last_row, column=9, value=report_data["summary"]["avg_cost_per_hour"]).font = Font(bold=True)

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 25)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"cost_per_hour_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# === Cost Rates Configuration ===


def get_cost_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить текущие ставки для расчёта себестоимости."""
    from app.models.shift import CompanyCostRates

    rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()

    if not rates:
        return {"fuel_price_per_liter": 65.0, "hourly_wage": 500.0, "amortization_per_hour": 300.0}

    return {
        "fuel_price_per_liter": rates.fuel_price_per_liter,
        "hourly_wage": rates.hourly_wage,
        "amortization_per_hour": rates.amortization_per_hour,
        "updated_at": rates.updated_at.isoformat() if rates.updated_at else None,
    }



def update_cost_rates(
    fuel_price_per_liter: float = Body(...),
    hourly_wage: float = Body(...),
    amortization_per_hour: float = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить ставки для расчёта себестоимости моточаса."""
    from app.models.shift import CompanyCostRates

    rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()

    if rates:
        rates.fuel_price_per_liter = fuel_price_per_liter
        rates.hourly_wage = hourly_wage
        rates.amortization_per_hour = amortization_per_hour
        rates.updated_by = current_user.id
    else:
        rates = CompanyCostRates(
            company_id=company_id,
            fuel_price_per_liter=fuel_price_per_liter,
            hourly_wage=hourly_wage,
            amortization_per_hour=amortization_per_hour,
            updated_by=current_user.id,
        )
        db.add(rates)

    db.commit()
    return {"message": "Ставки обновлены"}



def get_cost_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Прогноз расходов на следующий месяц на основе трендов за последние 90 дней."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry, CompanyCostRates

    today = date_type.today()
    lookback = today - timedelta(days=90)
    next_month_start = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    next_month_end = (next_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    forecast_days = (next_month_end - next_month_start).days + 1

    # Get last 90 days data
    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= lookback)
        .where(ShiftTask.shift_date <= today)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= lookback)
        .where(ShiftTask.shift_date <= today)
    ).scalars().all()

    # Load rates
    company_rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()
    fuel_price = company_rates.fuel_price_per_liter if company_rates else 65.0
    hourly_wage = company_rates.hourly_wage if company_rates else 500.0
    amort_rate = company_rates.amortization_per_hour if company_rates else 300.0

    actual_days = max((today - lookback).days, 1)

    total_hours = sum(
        max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)
        for t in tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None)
    )
    total_fuel = sum(f.quantity_liters for f in fuel_entries)

    avg_daily_hours = total_hours / actual_days
    avg_daily_fuel = total_fuel / actual_days

    # Forecast
    forecast_hours = round(avg_daily_hours * forecast_days, 1)
    forecast_fuel = round(avg_daily_fuel * forecast_days, 2)
    forecast_fuel_cost = round(forecast_fuel * fuel_price, 2)
    forecast_wage_cost = round(forecast_hours * hourly_wage, 2)
    forecast_amort_cost = round(forecast_hours * amort_rate, 2)
    forecast_total = round(forecast_fuel_cost + forecast_wage_cost + forecast_amort_cost, 2)

    # Actual totals for comparison
    actual_fuel_cost = round(total_fuel * fuel_price, 2)
    actual_wage_cost = round(total_hours * hourly_wage, 2)
    actual_amort_cost = round(total_hours * amort_rate, 2)
    actual_total = round(actual_fuel_cost + actual_wage_cost + actual_amort_cost, 2)

    # Daily trend for chart (last 30 days)
    daily_data = {}
    for t in tasks:
        key = str(t.shift_date)
        if key not in daily_data:
            daily_data[key] = {"date": key, "hours": 0}
        if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None):
            daily_data[key]["hours"] += max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600)

    for f_entry in fuel_entries:
        task = db.get(ShiftTask, f_entry.shift_task_id)
        if task:
            key = str(task.shift_date)
            if key in daily_data:
                daily_data[key].setdefault("fuel", 0)
                daily_data[key]["fuel"] += f_entry.quantity_liters

    daily_trend = sorted(daily_data.values(), key=lambda x: x["date"])[-30:]

    change_pct = round(((forecast_total / max(actual_total, 1)) * (actual_days / forecast_days) - 1) * 100, 1) if actual_total > 0 else 0

    return {
        "period": {"lookback_days": 90, "forecast_from": str(next_month_start), "forecast_to": str(next_month_end), "forecast_days": forecast_days},
        "actual_90d": {
            "total_cost": actual_total, "total_hours": round(total_hours, 1),
            "fuel_liters": round(total_fuel, 2), "fuel_cost": actual_fuel_cost,
            "wage_cost": actual_wage_cost, "amortization_cost": actual_amort_cost,
        },
        "forecast": {
            "total_cost": forecast_total, "total_hours": forecast_hours,
            "fuel_liters": forecast_fuel, "fuel_cost": forecast_fuel_cost,
            "wage_cost": forecast_wage_cost, "amortization_cost": forecast_amort_cost,
            "change_pct": change_pct,
        },
        "rates": {"fuel_price": fuel_price, "hourly_wage": hourly_wage, "amortization": amort_rate},
        "daily_trend": daily_trend,
    }


# === Diadoc / ЭДО Integration ===


def get_pnl_per_vehicle(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отчёт прибыльности по каждой единице техники: выручка - расходы = маржа."""
    from datetime import date as date_type
    from app.models.shift import ShiftFuelEntry, CompanyCostRates

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)

    vehicles = db.execute(select(Vehicle).where(Vehicle.company_id == company_id)).scalars().all()

    # Load rates
    company_rates = db.execute(
        select(CompanyCostRates).where(CompanyCostRates.company_id == company_id)
    ).scalar_one_or_none()
    fuel_price = company_rates.fuel_price_per_liter if company_rates else 65.0
    hourly_wage = company_rates.hourly_wage if company_rates else 500.0
    amort_rate = company_rates.amortization_per_hour if company_rates else 300.0

    tasks = db.execute(
        select(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
        .where(ShiftTask.status.notin_(["cancelled"]))
    ).scalars().all()

    fuel_entries = db.execute(
        select(ShiftFuelEntry)
        .join(ShiftTask, ShiftFuelEntry.shift_task_id == ShiftTask.id)
        .join(Vehicle, ShiftFuelEntry.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date >= d_from)
        .where(ShiftTask.shift_date <= d_to)
    ).scalars().all()

    acts = db.execute(
        select(Act).where(
            Act.company_id == company_id,
            Act.act_date >= d_from,
            Act.act_date <= d_to,
        )
    ).scalars().all()

    result = []
    for v in vehicles:
        v_tasks = [t for t in tasks if t.vehicle_id == v.id]
        v_fuel = [f for f in fuel_entries if f.vehicle_id == v.id]
        v_acts = [a for a in acts if a.vehicle_id == v.id]

        hours = sum(max(0, (getattr(t, 'planned_end', None) - getattr(t, 'planned_start', None)).total_seconds() / 3600) for t in v_tasks if getattr(t, 'planned_start', None) and getattr(t, 'planned_end', None))
        fuel_liters = sum(f.quantity_liters for f in v_fuel)
        revenue = sum(a.total_amount or 0 for a in v_acts)
        fuel_cost = fuel_liters * fuel_price
        wage_cost = hours * hourly_wage
        amort_cost = hours * amort_rate
        total_expenses = fuel_cost + wage_cost + amort_cost
        margin = revenue - total_expenses
        margin_pct = round((margin / revenue) * 100, 1) if revenue > 0 else 0

        result.append({
            "vehicle_id": v.id, "vehicle_name": v.name,
            "hours": round(hours, 1), "fuel_liters": round(fuel_liters, 2),
            "revenue": round(revenue, 2),
            "fuel_cost": round(fuel_cost, 2), "wage_cost": round(wage_cost, 2), "amortization_cost": round(amort_cost, 2),
            "total_expenses": round(total_expenses, 2),
            "margin": round(margin, 2), "margin_pct": margin_pct,
        })

    result.sort(key=lambda x: x["margin"], reverse=True)
    return {"period": {"from": str(d_from), "to": str(d_to)}, "vehicles": result}



def export_pnl_excel(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Экспорт отчёта прибыльности по технике в Excel."""
    import io
    from datetime import date as date_type
    from fastapi.responses import StreamingResponse

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    report = get_pnl_per_vehicle(date_from, date_to, db, current_user, company_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "P&L по технике"

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    green_font = Font(color="006100", bold=True)
    red_font = Font(color="9C0006", bold=True)

    headers = ["Техника", "Часов", "Выручка", "Топливо", "Зарплата", "Амортизация", "Расходы", "Маржа", "Маржа %"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, v in enumerate(report["vehicles"], 2):
        ws.cell(row=row_idx, column=1, value=v["vehicle_name"])
        ws.cell(row=row_idx, column=2, value=v["hours"])
        ws.cell(row=row_idx, column=3, value=v["revenue"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=4, value=v["fuel_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=5, value=v["wage_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=6, value=v["amortization_cost"]).number_format = '#,##0'
        ws.cell(row=row_idx, column=7, value=v["total_expenses"]).number_format = '#,##0'
        margin_cell = ws.cell(row=row_idx, column=8, value=v["margin"])
        margin_cell.number_format = '#,##0'
        margin_cell.font = green_font if v["margin"] >= 0 else red_font
        ws.cell(row=row_idx, column=9, value=v["margin_pct"]).number_format = '0.0"%"'

    for col_cells in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 22)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    filename = f"pnl_{d_from.strftime('%Y%m%d')}_{d_to.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})



def get_platform_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обзор платформы: пользователи, техника, акты, финансы, активность."""
    from datetime import date as date_type, timedelta
    from sqlalchemy import func
    from app.models.shift import ShiftFuelEntry, DocumentArchive
    # from app.models.finance import BankTransaction  # TODO: find correct module
    from app.models.contractor import DriverProfile, Employee

    today = date_type.today()
    month_start = today.replace(day=1)

    # Users & drivers
    users_count = db.execute(select(func.count()).select_from(User)).scalar() or 0
    drivers_count = db.execute(select(func.count()).select_from(DriverProfile)).scalar() or 0

    # Vehicles
    vehicles_count = db.execute(select(func.count()).select_from(Vehicle).where(Vehicle.company_id == company_id)).scalar() or 0

    # Acts this month
    acts_month = db.execute(
        select(func.count(), func.coalesce(func.sum(Act.total_amount), 0))
        .where(Act.company_id == company_id)
        .where(Act.act_date >= month_start)
    ).one()
    acts_count = acts_month[0] or 0
    revenue_month = float(acts_month[1] or 0)

    # Overdue acts
    overdue_count = db.execute(
        select(func.count()).select_from(Act)
        .where(Act.company_id == company_id)
        .where(Act.status.in_(["draft", "sent_to_edo", "signed"]))
        .where(Act.act_date <= today - timedelta(days=30))
    ).scalar() or 0

    # Transactions this month
    txn_month = db.execute(
        select(func.count(), func.coalesce(func.sum(BankTransaction.amount), 0))
        .where(BankTransaction.company_id == company_id)
        .where(BankTransaction.document_date >= month_start)
    ).one()
    txn_count = txn_month[0] or 0
    txn_amount = float(txn_month[1] or 0)

    # Unmatched transactions
    unmatched_count = db.execute(
        select(func.count()).select_from(BankTransaction)
        .where(BankTransaction.company_id == company_id)
        .where(BankTransaction.matched_invoice_id.is_(None))
    ).scalar() or 0

    # Documents in archive
    docs_count = db.execute(
        select(func.count()).select_from(DocumentArchive)
        .where(DocumentArchive.company_id == company_id)
    ).scalar() or 0

    # Shifts today
    shifts_today = db.execute(
        select(func.count()).select_from(ShiftTask)
        .join(Vehicle, ShiftTask.vehicle_id == Vehicle.id)
        .where(Vehicle.company_id == company_id)
        .where(ShiftTask.shift_date == today)
    ).scalar() or 0

    return {
        "users": {"total": users_count, "drivers": drivers_count},
        "vehicles": {"total": vehicles_count},
        "acts_this_month": {"count": acts_count, "revenue": round(revenue_month, 2)},
        "overdue_acts": overdue_count,
        "transactions_this_month": {"count": txn_count, "amount": round(txn_amount, 2)},
        "unmatched_transactions": unmatched_count,
        "documents_in_archive": docs_count,
        "shifts_today": shifts_today,
        "date": str(today),
    }


# === Audit Log ===


def get_recent_actions(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Последние действия из audit log для dashboard виджета."""
    from app.models.auth import AuditLog
    logs = db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).scalars().all()
    return [{"id": l.id, "user_id": l.user_id, "action": l.action, "resource_type": l.resource_type, "details": l.details, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs]


