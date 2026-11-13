"""Regression: marketplace commission rate is a PERCENT, not a fraction.

The column was numeric(5,4) with server_default 0.1 holding 0.1000, while
calculate_payout() divides by 100 and the vehicle form sends 10.00. That
combination raised numeric field overflow on every ORM insert without an
explicit rate, and the UI rendered "0.1%" instead of "10%".
"""

from decimal import Decimal

import sqlalchemy as sa

from app.models.catalog import Vehicle
from app.services.finance_service import calculate_payout


class TestCommissionRateSemantics:
    def test_model_default_is_ten_percent(self):
        col = Vehicle.__table__.columns["marketplace_commission_rate"]
        assert col.default.arg == Decimal("10.00")

    def test_column_precision_allows_ten(self):
        col = Vehicle.__table__.columns["marketplace_commission_rate"]
        assert isinstance(col.type, sa.Numeric)
        assert (col.type.precision, col.type.scale) == (
            5,
            2,
        ), "numeric(5,4) caps at 9.9999 and cannot store 10.00 percent"

    def test_payout_treats_rate_as_percent(self):
        r = calculate_payout(Decimal("1000"), Decimal("10.00"))
        assert r["platform_commission"] == Decimal("100.00")
        assert r["net_amount"] == Decimal("900.00")

    def test_fraction_would_undercharge_hundredfold(self):
        """Guards against reintroducing fraction semantics."""
        correct = calculate_payout(Decimal("1000"), Decimal("10.00"))
        wrong = calculate_payout(Decimal("1000"), Decimal("0.1"))
        assert correct["platform_commission"] == Decimal("100.00")
        assert wrong["platform_commission"] == Decimal("1.00")
        assert correct["platform_commission"] / wrong["platform_commission"] == 100
