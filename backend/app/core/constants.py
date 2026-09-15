"""Константы и перечисления для бизнес-логики."""

from decimal import Decimal
from enum import Enum


class TaxSystem(str, Enum):
    """Системы налогообложения."""

    OSNO = "osno"  # ОСНО — с НДС (обычно 20%)
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
        """Ставка НДС по умолчанию для этой системы."""
        if self == TaxSystem.OSNO:
            return Decimal("20.00")
        return Decimal("0")


class VatRate(str, Enum):
    """Ставки НДС."""

    NONE = "0"  # Без НДС
    FIVE = "5"  # 5% (льготные товары)
    SEVEN = "7"  # 7% (льготные товары)
    TEN = "10"  # 10% (продукты, детские товары)
    TWENTY = "20"  # 20% (стандартная)
    TWENTY_TWO = "22"  # 22% (историческая)

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
