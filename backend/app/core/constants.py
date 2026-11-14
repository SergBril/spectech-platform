"""Константы и перечисления для бизнес-логики."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

# НДС на ОСНО: 22% с 2026-01-01, 20% для документов за 2025 и ранее.
VAT_RATE_CHANGE_DATE = date(2026, 1, 1)
VAT_RATE_CURRENT = Decimal("22.00")
VAT_RATE_LEGACY = Decimal("20.00")


class TaxSystem(str, Enum):
    """Системы налогообложения."""

    OSNO = "osno"  # ОСНО — с НДС (22% с 2026, 20% ранее)
    USN_INCOME = "usn_6"  # УСН Доходы (6%, без НДС)
    USN_FULL = "usn_15"  # УСН Доходы-Расходы (15%, без НДС)
    PATENT = "patent"  # Патент (без НДС)
    NPD = "npd"  # НПД / Самозанятые (без НДС)

    @property
    def label(self) -> str:
        """Человекочитаемое название."""
        labels = {
            "osno": "ОСНО (с НДС)",
            "usn_6": "УСН Доходы (6%)",
            "usn_15": "УСН Доходы-Расходы (15%)",
            "patent": "Патент",
            "npd": "НПД / Самозанятый",
        }
        return labels.get(self.value, self.value)

    @property
    def has_vat(self) -> bool:
        """Есть ли НДС в этой системе."""
        return self == TaxSystem.OSNO

    @property
    def default_vat_rate(self) -> Decimal:
        """Текущая ставка НДС по умолчанию (без учёта даты документа).

        Для расчётов по документу используй vat_rate_for_date().
        """
        if self == TaxSystem.OSNO:
            return VAT_RATE_CURRENT
        return Decimal("0")


class VatRate(str, Enum):
    """Ставки НДС."""

    NONE = "0"  # Без НДС
    FIVE = "5"  # 5% (льготные товары)
    SEVEN = "7"  # 7% (льготные товары)
    TEN = "10"  # 10% (продукты, детские товары)
    TWENTY = "20"  # 20% (для документов за 2025 и ранее)
    TWENTY_TWO = "22"  # 22% (стандартная с 2026-01-01)

    @property
    def label(self) -> str:
        if self == VatRate.NONE:
            return "Без НДС"
        return f"{self.value}%"

    @property
    def decimal(self) -> Decimal:
        return Decimal(self.value)


# Стандартные ставки для UI
VAT_RATE_CHOICES = [
    {"value": VatRate.NONE.value, "label": VatRate.NONE.label},
    {"value": VatRate.FIVE.value, "label": VatRate.FIVE.label},
    {"value": VatRate.SEVEN.value, "label": VatRate.SEVEN.label},
    {"value": VatRate.TEN.value, "label": VatRate.TEN.label},
    {"value": VatRate.TWENTY.value, "label": VatRate.TWENTY.label},
    {"value": VatRate.TWENTY_TWO.value, "label": VatRate.TWENTY_TWO.label},
]

TAX_SYSTEM_CHOICES = [
    {"value": ts.value, "label": ts.label, "has_vat": ts.has_vat} for ts in TaxSystem
]


def vat_rate_for_date(doc_date=None, tax_system=None) -> Decimal:
    """Ставка НДС по дате ДОКУМЕНТА, а не по сегодняшней дате.

    ОСНО: 22% с 2026-01-01, 20% для документов за 2025 и ранее.
    УСН/Патент/НПД — без НДС. doc_date=None означает текущую ставку.

    Явно заданная ставка в документе имеет приоритет над этой функцией:
    она нужна для ручного переопределения (например, 20% в документе 2026 года).
    """
    if tax_system is None:
        ts = TaxSystem.OSNO
    elif isinstance(tax_system, TaxSystem):
        ts = tax_system
    else:
        try:
            ts = TaxSystem(str(tax_system))
        except ValueError:
            ts = TaxSystem.OSNO
    if not ts.has_vat:
        return Decimal("0")
    if doc_date is None:
        return VAT_RATE_CURRENT
    # Дата может прийти строкой (шаблоны, SimpleNamespace, payload) - приводим.
    if isinstance(doc_date, str):
        try:
            doc_date = date.fromisoformat(doc_date[:10])
        except ValueError:
            return VAT_RATE_CURRENT
    if isinstance(doc_date, datetime):
        doc_date = doc_date.date()
    if not isinstance(doc_date, date):
        return VAT_RATE_CURRENT
    return VAT_RATE_CURRENT if doc_date >= VAT_RATE_CHANGE_DATE else VAT_RATE_LEGACY
