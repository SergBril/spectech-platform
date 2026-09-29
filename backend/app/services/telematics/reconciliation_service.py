"""
Сервис для сверки данных оператор vs телематика vs заявка.

Сравнивает данные из shift_reports с gps_points за период смены.
"""

import logging

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.shift import ShiftReport, ShiftTask
from app.models.telematics import GpsPoint, ShiftDataReconciliation

logger = logging.getLogger("spectech.reconciliation_service")


class ReconciliationService:
    """Сервис для сверки данных оператор vs телематика."""

    # Пороги для автоматического подтверждения
    AUTO_APPROVE_THRESHOLD_PERCENT = 5.0  # Расхождение < 5%
    MANUAL_REVIEW_THRESHOLD_PERCENT = 15.0  # Расхождение > 15% требует ручной проверки

    def reconcile_shift_task(
        self, db: Session, shift_task_id: int
    ) -> ShiftDataReconciliation | None:
        """
        Выполняет сверку данных для указанного сменного задания.

        Returns:
            ShiftDataReconciliation с результатами сверки
        """
        # 1. Получаем ShiftTask
        shift_task = db.get(ShiftTask, shift_task_id)
        if not shift_task:
            logger.error(f"ShiftTask {shift_task_id} not found")
            return None

        # 2. Получаем ShiftReport для этого задания
        shift_report = (
            db.query(ShiftReport)
            .filter(ShiftReport.shift_task_id == shift_task_id)
            .order_by(ShiftReport.created_at.desc())
            .first()
        )

        if not shift_report:
            logger.warning(f"No ShiftReport found for ShiftTask {shift_task_id}")
            return None

        # 3. Определяем период смены
        # Используем явные значения или defaults
        if shift_report.operator_work_start:
            work_start = shift_report.operator_work_start
        else:
            # Если нет явного времени начала — берём начало дня смены
            work_start = datetime.combine(
                shift_task.shift_date, datetime.min.time()
            ).replace(tzinfo=UTC)

        if shift_report.operator_work_end:
            work_end = shift_report.operator_work_end
        else:
            # Если нет явного времени окончания — берём конец дня смены
            work_end = datetime.combine(
                shift_task.shift_date, datetime.max.time()
            ).replace(tzinfo=UTC)

        # 4. Получаем телеметрию за период смены
        telemetry_points = (
            db.query(GpsPoint)
            .filter(
                and_(
                    GpsPoint.vehicle_id == shift_task.vehicle_id,
                    GpsPoint.recorded_at >= work_start,
                    GpsPoint.recorded_at <= work_end,
                )
            )
            .order_by(GpsPoint.recorded_at.asc())
            .all()
        )

        # 5. Вычисляем данные из телеметрии
        telematics_moto_hours = self._calculate_moto_hours(telemetry_points)
        telematics_odometer = self._calculate_odometer(telemetry_points)
        telematics_fuel_used = self._calculate_fuel_used(telemetry_points)

        # 6. Получаем данные оператора
        operator_moto_hours = float(shift_report.operator_moto_hours or 0)
        operator_odometer = shift_report.operator_odometer or 0
        operator_fuel_used = float(shift_report.operator_fuel_used or 0)

        # 7. Вычисляем расхождения
        moto_hours_diff_percent = self._calculate_diff_percent(
            operator_moto_hours, telematics_moto_hours
        )
        odometer_diff_percent = self._calculate_diff_percent(
            operator_odometer, telematics_odometer
        )
        fuel_diff_percent = self._calculate_diff_percent(
            operator_fuel_used, telematics_fuel_used
        )

        # 8. Определяем статус сверки
        max_diff = max(
            abs(moto_hours_diff_percent or 0),
            abs(odometer_diff_percent or 0),
            abs(fuel_diff_percent or 0),
        )

        if max_diff <= self.AUTO_APPROVE_THRESHOLD_PERCENT:
            reconciliation_status = "auto_approved"
            decision_source = "telematics"
            final_moto_hours = telematics_moto_hours
            final_odometer = telematics_odometer
            final_fuel_used = telematics_fuel_used
        elif max_diff > self.MANUAL_REVIEW_THRESHOLD_PERCENT:
            reconciliation_status = "manual_review"
            decision_source = None
            final_moto_hours = None
            final_odometer = None
            final_fuel_used = None
        else:
            reconciliation_status = "discrepancy_detected"
            decision_source = None
            final_moto_hours = None
            final_odometer = None
            final_fuel_used = None

        # 9. Создаём или обновляем запись сверки
        reconciliation = (
            db.query(ShiftDataReconciliation)
            .filter(ShiftDataReconciliation.shift_task_id == shift_task_id)
            .first()
        )

        if not reconciliation:
            reconciliation = ShiftDataReconciliation(shift_task_id=shift_task_id)
            db.add(reconciliation)

        reconciliation.operator_moto_hours = operator_moto_hours
        reconciliation.operator_odometer = operator_odometer
        reconciliation.operator_fuel_used = operator_fuel_used

        reconciliation.telematics_moto_hours = telematics_moto_hours
        reconciliation.telematics_odometer = telematics_odometer
        reconciliation.telematics_fuel_used = telematics_fuel_used
        reconciliation.telematics_data_points_count = len(telemetry_points)

        reconciliation.planned_moto_hours = None  # Можно добавить из заявки
        reconciliation.planned_odometer = None

        reconciliation.moto_hours_diff_percent = moto_hours_diff_percent
        reconciliation.odometer_diff_percent = odometer_diff_percent
        reconciliation.fuel_diff_percent = fuel_diff_percent

        reconciliation.reconciliation_status = reconciliation_status
        reconciliation.decision_source = decision_source
        reconciliation.final_moto_hours = final_moto_hours
        reconciliation.final_odometer = final_odometer
        reconciliation.final_fuel_used = final_fuel_used

        reconciliation.company_id = shift_task.company_id

        db.commit()
        db.refresh(reconciliation)

        logger.info(
            f"Reconciliation completed for ShiftTask {shift_task_id}: "
            f"status={reconciliation_status}, max_diff={max_diff:.2f}%"
        )

        return reconciliation

    def _calculate_moto_hours(self, telemetry_points: list[GpsPoint]) -> float:
        """Вычисляет моточасы из телеметрии (двигатель включён)."""
        if not telemetry_points:
            return 0.0

        engine_on_count = sum(1 for p in telemetry_points if p.engine_on is True)
        # Предполагаем что точки приходят каждые 5 минут (300 секунд)
        moto_hours = engine_on_count * 300 / 3600  # секунды → часы
        return round(moto_hours, 2)

    def _calculate_odometer(self, telemetry_points: list[GpsPoint]) -> int:
        """Вычисляет пробег из телеметрии (Haversine formula)."""
        if len(telemetry_points) < 2:
            return 0

        total_distance_km = 0.0

        for i in range(1, len(telemetry_points)):
            p1 = telemetry_points[i - 1]
            p2 = telemetry_points[i]

            distance_km = self._haversine_distance(
                p1.latitude, p1.longitude, p2.latitude, p2.longitude
            )
            total_distance_km += distance_km

        return int(total_distance_km)

    def _calculate_fuel_used(self, telemetry_points: list[GpsPoint]) -> float:
        """Вычисляет расход топлива из телеметрии."""
        if len(telemetry_points) < 2:
            return 0.0

        first_point = telemetry_points[0]
        last_point = telemetry_points[-1]

        if first_point.fuel_level is None or last_point.fuel_level is None:
            logger.warning("fuel_level is None in first or last point")
            return 0.0

        fuel_used = first_point.fuel_level - last_point.fuel_level
        return round(max(0.0, fuel_used), 2)  # Не может быть отрицательным

    def _calculate_diff_percent(self, value1: float, value2: float) -> float:
        """Вычисляет процент расхождения между двумя значениями."""
        if value1 == 0 and value2 == 0:
            return 0.0
        if value2 == 0:
            return 100.0

        diff_percent = abs(value1 - value2) / value2 * 100
        return round(diff_percent, 2)

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Вычисляет расстояние между двумя точками в км (Haversine formula)."""
        import math

        R = 6371.0  # Радиус Земли в км

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


# Singleton instance
reconciliation_service = ReconciliationService()
