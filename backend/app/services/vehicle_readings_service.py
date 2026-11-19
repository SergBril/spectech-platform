"""Показания счётчиков смены: один источник правды для двух маршрутов.

Мобильный сервис писал в operator_odometer НАКОПЛЕННОЕ показание, а driver.py -
ВЫРАБОТКУ за смену. Одна колонка, два смысла: расчёты стоимости и сверки не могли
ей доверять. Здесь семантика зафиксирована:

  *_start / *_end        - накопленные показания счётчика
  operator_* / distance  - выработка за смену, ВЫЧИСЛЯЕТСЯ как разность

Показания идемпотентны: повторный ввод того же числа ничего не меняет, а откат
отвергается. Выработку нельзя подделать, не сломав монотонность.
"""

import logging
from decimal import Decimal

logger = logging.getLogger("spectech.readings")


class ReadingsError(Exception):
    """Показания противоречивы: откат счётчика или конец меньше начала."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def apply_shift_readings(
    db,
    task,
    vehicle,
    *,
    odometer_start=None,
    odometer_end=None,
    hours_start=None,
    hours_end=None,
    report=None,
) -> dict:
    """Применить показания к смене и наработке машины. Без commit.

    Возвращает выработку и предупреждения. Откат счётчика - ошибка, а не
    молчаливая перезапись: иначе одна опечатка обнулит регламент ТО.
    """
    warnings: list[str] = []

    def _num(v):
        return None if v is None else float(v)

    o_start, o_end = _num(odometer_start), _num(odometer_end)
    h_start, h_end = _num(hours_start), _num(hours_end)

    if o_start is not None and o_end is not None and o_end < o_start:
        raise ReadingsError(422, "Одометр на конец смены меньше, чем на начало")
    if h_start is not None and h_end is not None and h_end < h_start:
        raise ReadingsError(422, "Моточасы на конец смены меньше, чем на начало")

    # Откат относительно уже известной наработки машины
    if vehicle is not None:
        cur_o = _num(vehicle.odometer_km)
        cur_h = _num(vehicle.engine_hours)
        if o_end is not None and cur_o is not None and o_end < cur_o:
            raise ReadingsError(
                422,
                f"Одометр {o_end:.0f} км меньше известного {cur_o:.0f} км: "
                "показания не убывают, проверьте ввод",
            )
        if h_end is not None and cur_h is not None and h_end < cur_h:
            raise ReadingsError(
                422,
                f"Моточасы {h_end:.1f} меньше известных {cur_h:.1f}: "
                "показания не убывают, проверьте ввод",
            )

    distance = None
    if o_start is not None and o_end is not None:
        distance = round(o_end - o_start, 1)
    worked_hours = None
    if h_start is not None and h_end is not None:
        worked_hours = round(h_end - h_start, 2)

    # Правдоподобие: смена не может наработать больше астрономического времени
    if worked_hours is not None and task is not None:
        start_at = getattr(task, "actual_start_at", None) or getattr(
            task, "created_at", None
        )
        end_at = getattr(task, "actual_end_at", None)
        if start_at is not None and end_at is not None:
            elapsed = (end_at - start_at).total_seconds() / 3600.0
            if elapsed > 0 and worked_hours > elapsed + 0.5:
                warnings.append(
                    f"выработка {worked_hours:.1f} ч превышает длительность смены {elapsed:.1f} ч"
                )

    if task is not None:
        if o_start is not None:
            task.odometer_start = int(o_start)
        if h_start is not None:
            task.moto_hours_start = Decimal(str(h_start))
        if distance is not None:
            task.odometer_distance = Decimal(str(distance))

    if report is not None:
        if o_end is not None:
            report.odometer_end = int(o_end)
        if h_end is not None:
            report.moto_hours_end = Decimal(str(h_end))
        # operator_* - выработка за смену, единая семантика для обоих маршрутов
        if distance is not None:
            report.operator_odometer = int(round(distance))
        if worked_hours is not None:
            report.operator_moto_hours = Decimal(str(worked_hours))

    if vehicle is not None:
        if o_end is not None:
            vehicle.odometer_km = Decimal(str(o_end))
        if h_end is not None:
            vehicle.engine_hours = Decimal(str(h_end))

    if warnings:
        logger.warning(
            "Shift %s readings: %s", getattr(task, "id", "?"), "; ".join(warnings)
        )

    return {
        "odometer_distance": distance,
        "moto_hours_worked": worked_hours,
        "warnings": warnings,
    }
