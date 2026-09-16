"""Модуль перевода единиц измерения и других констант."""

# Словарь перевода единиц измерения
UNIT_TRANSLATIONS = {
    "hourly": "час",
    "hour": "час",
    "hr": "час",
    "shift": "смена",
    "smena": "смена",
    "km": "км",
    "fixed": "услуга",
    "service": "услуга",
    "usluga": "услуга",
    "piece": "шт",
    "pcs": "шт",
    "шт": "шт",
    "m": "м",
    "m2": "м²",
    "m3": "м³",
    "kg": "кг",
    "ton": "т",
    "liter": "л",
    "l": "л",
    "day": "день",
    "month": "мес",
}


def translate_unit(unit: str) -> str:
    """Перевод единицы измерения с английского на русский."""
    if not unit:
        return "шт"
    unit_lower = str(unit).strip().lower()
    return UNIT_TRANSLATIONS.get(unit_lower, str(unit).strip())
