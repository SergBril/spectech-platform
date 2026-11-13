"""НДС на ОСНО: 22% с 2026-01-01, 20% для документов за 2025 и ранее.

Ставка берётся из даты ДОКУМЕНТА, а не из сегодняшней даты, и явно
заданная ставка имеет приоритет (ручное переопределение).
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.constants import (
    VAT_RATE_CHANGE_DATE,
    TaxSystem,
    vat_rate_for_date,
)


class TestVatRateForDate:
    @pytest.mark.parametrize(
        "doc_date,expected",
        [
            (date(2025, 12, 31), Decimal("20.00")),
            (date(2025, 1, 1), Decimal("20.00")),
            (date(2026, 1, 1), Decimal("22.00")),
            (date(2026, 11, 14), Decimal("22.00")),
            (date(2027, 3, 5), Decimal("22.00")),
        ],
    )
    def test_osno_boundary(self, doc_date, expected):
        assert vat_rate_for_date(doc_date) == expected

    def test_change_date_is_2026_01_01(self):
        assert VAT_RATE_CHANGE_DATE == date(2026, 1, 1)

    def test_none_means_current(self):
        assert vat_rate_for_date(None) == Decimal("22.00")

    def test_datetime_is_normalised(self):
        assert vat_rate_for_date(datetime(2025, 12, 31, 23, 59)) == Decimal("20.00")
        assert vat_rate_for_date(datetime(2026, 1, 1, 0, 0)) == Decimal("22.00")

    @pytest.mark.parametrize("ts", ["usn_6", "usn_15", "patent", "npd"])
    def test_no_vat_systems(self, ts):
        assert vat_rate_for_date(date(2026, 6, 1), ts) == Decimal("0")
        assert vat_rate_for_date(date(2025, 6, 1), ts) == Decimal("0")

    def test_enum_and_string_agree(self):
        assert vat_rate_for_date(date(2026, 6, 1), TaxSystem.OSNO) == Decimal("22.00")
        assert vat_rate_for_date(date(2026, 6, 1), "osno") == Decimal("22.00")

    def test_unknown_system_falls_back_to_osno(self):
        assert vat_rate_for_date(date(2026, 6, 1), "nonsense") == Decimal("22.00")

    def test_property_is_current_rate(self):
        assert TaxSystem.OSNO.default_vat_rate == Decimal("22.00")
        assert TaxSystem.USN_INCOME.default_vat_rate == Decimal("0")


class TestCompanyDefault:
    def test_new_company_defaults_to_22(self, db_session):
        from app.models.company import Company

        c = Company(name="VAT Default Co", inn="9999999966", is_active=True)
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        assert Decimal(str(c.default_vat_rate)) == Decimal("22.00")
