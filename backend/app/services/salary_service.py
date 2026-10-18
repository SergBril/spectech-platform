"""Сервис расчёта зарплат сотрудников."""

import logging
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.contractor import Contractor, Employee
from app.models.salary import SalaryRecord, SalaryStatus

logger = logging.getLogger("spectech.salary")


class SalaryService:
    """Сервис для расчёта зарплат по 5 типам ставок."""

    @staticmethod
    def calculate_for_employee(
        db: Session,
        employee: Employee,
        period_start: date,
        period_end: date,
        company_id: int,
        created_by: int | None = None,
    ) -> SalaryRecord:
        """Рассчитывает зарплату сотрудника за период."""
        if not employee.salary_type:
            raise ValueError(
                f"У сотрудника {employee.contractor_id} не задан тип зарплаты (salary_type)"
            )

        # Проверяем существующую запись за этот период (по сотруднику + пересечение дат)
        existing = (
            db.query(SalaryRecord)
            .filter(
                SalaryRecord.employee_contractor_id == employee.contractor_id,
                SalaryRecord.company_id == company_id,
                SalaryRecord.period_start <= period_end,
                SalaryRecord.period_end >= period_start,
            )
            .order_by(SalaryRecord.created_at.desc())
            .first()
        )

        if existing:
            logger.info(
                f"Salary record #{existing.id} already exists for employee #{employee.contractor_id}, updating..."
            )
            shifts_data = SalaryService._get_shifts_data(
                db, employee.contractor_id, period_start, period_end, company_id
            )
            gross, details = SalaryService._calculate_gross(employee, shifts_data)
            existing.period_start = period_start
            existing.period_end = period_end
            existing.shifts_count = shifts_data["shifts_count"]
            existing.total_hours = Decimal(str(shifts_data["total_hours"]))
            existing.total_km = Decimal(str(shifts_data["total_km"]))
            existing.gross_amount = gross
            existing.net_amount = gross
            existing.calculation_details = details
            db.commit()
            db.refresh(existing)
            return existing

        # Собираем данные за период из смен
        shifts_data = SalaryService._get_shifts_data(
            db, employee.contractor_id, period_start, period_end, company_id
        )

        # Рассчитываем по типу ставки
        gross, details = SalaryService._calculate_gross(employee, shifts_data)

        record = SalaryRecord(
            company_id=company_id,
            employee_contractor_id=employee.contractor_id,
            period_start=period_start,
            period_end=period_end,
            shifts_count=shifts_data["shifts_count"],
            total_hours=Decimal(str(shifts_data["total_hours"])),
            total_km=Decimal(str(shifts_data["total_km"])),
            salary_type=employee.salary_type,
            gross_amount=gross,
            deductions=Decimal("0"),
            net_amount=gross,
            calculation_details=details,
            status=SalaryStatus.draft.value,
            created_by=created_by,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(
            f"✅ Salary calculated for employee #{employee.contractor_id}: "
            f"{gross} RUB ({employee.salary_type}), {shifts_data['shifts_count']} shifts"
        )
        return record

    @staticmethod
    def _get_shifts_data(
        db: Session,
        contractor_id: int,
        period_start: date,
        period_end: date,
        company_id: int,
    ) -> dict:
        """Собирает данные о сменах сотрудника за период."""
        from app.models.shift import ShiftReport, ShiftTask

        # Сначала проверяем без фильтра по датам
        all_reports = (
            db.query(ShiftReport).filter(ShiftReport.operator_id == contractor_id).all()
        )

        logger.info(
            f"🔍 Total reports for operator #{contractor_id}: {len(all_reports)}"
        )
        for r in all_reports:
            task = db.get(ShiftTask, r.shift_task_id)
            logger.info(
                f"   Report #{r.id}: task_date={task.shift_date if task else 'N/A'}, hours={r.operator_moto_hours}"
            )

        # Теперь с фильтром
        reports = (
            db.query(ShiftReport)
            .join(ShiftTask, ShiftReport.shift_task_id == ShiftTask.id)
            .filter(
                ShiftReport.operator_id == contractor_id,
                ShiftTask.shift_date >= period_start,
                ShiftTask.shift_date <= period_end,
            )
            .all()
        )

        total_hours = Decimal("0")
        total_km = Decimal("0")

        for report in reports:
            hours = Decimal(str(report.operator_moto_hours or 0))
            total_hours += hours
            if report.operator_odometer:
                total_km += Decimal(str(report.operator_odometer))

        logger.info(
            f"📊 Shifts data for employee #{contractor_id} "
            f"({period_start} to {period_end}): "
            f"{len(reports)} shifts, {total_hours} hours, {total_km} km"
        )

        return {
            "shifts_count": len(reports),
            "total_hours": float(total_hours),
            "total_km": float(total_km),
            "total_shift_cost": 0,
        }

    @staticmethod
    def _calculate_gross(employee: Employee, shifts_data: dict) -> tuple[Decimal, dict]:
        """Рассчитывает gross по типу ставки."""
        rate = Decimal(str(employee.salary_rate or 0))
        Decimal(str(employee.salary_rate_secondary or 0))
        commission_pct = Decimal(str(employee.salary_commission_percent or 0))

        shifts = shifts_data["shifts_count"]
        hours = Decimal(str(shifts_data["total_hours"]))
        km = Decimal(str(shifts_data["total_km"]))

        details = {
            "salary_type": employee.salary_type,
            "rate": float(rate),
            "shifts_count": shifts,
            "total_hours": float(hours),
            "total_km": float(km),
        }

        if employee.salary_type == "fixed_shift":
            gross = rate * shifts
            details["formula"] = f"{rate} × {shifts} смен"

        elif employee.salary_type == "hourly":
            gross = rate * hours
            details["formula"] = f"{rate}/час × {hours} ч"

        elif employee.salary_type == "per_km":
            gross = rate * km
            details["formula"] = f"{rate}/км × {km} км"

        elif employee.salary_type == "shift_percent":
            # % от стоимости смены (стоимость смены пока = 0, нужна доработка)
            shift_cost = Decimal(str(shifts_data.get("total_shift_cost", 0)))
            gross = shift_cost * commission_pct / Decimal("100")
            details["formula"] = f"{commission_pct}% от {shift_cost}"
            details["shift_cost"] = float(shift_cost)

        elif employee.salary_type == "combo":
            # Комбинация: почасовая + % от смены
            hourly_part = rate * hours
            shift_cost = Decimal(str(shifts_data.get("total_shift_cost", 0)))
            percent_part = shift_cost * commission_pct / Decimal("100")
            gross = hourly_part + percent_part
            details["formula"] = (
                f"({rate}/ч × {hours}ч) + ({commission_pct}% от {shift_cost})"
            )
            details["hourly_part"] = float(hourly_part)
            details["percent_part"] = float(percent_part)

        else:
            raise ValueError(f"Unknown salary type: {employee.salary_type}")

        gross = gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        details["gross"] = float(gross)
        return gross, details

    @staticmethod
    def calculate_batch(
        db: Session,
        company_id: int,
        period_start: date,
        period_end: date,
        created_by: int | None = None,
    ) -> list[SalaryRecord]:
        """Рассчитывает зарплату всем сотрудникам компании за период."""
        employees = (
            db.query(Employee)
            .join(Contractor, Employee.contractor_id == Contractor.id)
            .filter(
                Contractor.company_id == company_id,
                Contractor.is_active == True,
                Employee.salary_type.isnot(None),
            )
            .all()
        )

        records = []
        errors = []

        for emp in employees:
            try:
                record = SalaryService.calculate_for_employee(
                    db, emp, period_start, period_end, company_id, created_by
                )
                records.append(record)
            except Exception as e:
                errors.append({"employee_id": emp.contractor_id, "error": str(e)})
                logger.error(
                    f"❌ Failed to calculate salary for employee #{emp.contractor_id}: {e}"
                )

        if errors:
            logger.warning(f"⚠️ Batch salary: {len(records)} OK, {len(errors)} errors")

        return records

    @staticmethod
    def approve_record(db: Session, record_id: int, approved_by: int) -> SalaryRecord:
        """Утверждает запись о зарплате."""
        record = db.get(SalaryRecord, record_id)
        if not record:
            raise ValueError(f"Salary record #{record_id} not found")
        if record.status != SalaryStatus.draft.value:
            raise ValueError(f"Cannot approve record with status '{record.status}'")

        record.status = SalaryStatus.approved.value
        record.approved_at = datetime.now(UTC)
        record.approved_by = approved_by
        db.commit()
        db.refresh(record)
        return record


salary_service = SalaryService()
