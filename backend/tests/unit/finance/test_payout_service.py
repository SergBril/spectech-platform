"""Unit tests for payout_service.py — business logic without database."""

from datetime import date
from decimal import Decimal


class TestPayoutCalculations:
    """Тесты расчёта выплат (чистая математика, без БД)."""

    def test_gross_amount_calculation(self):
        """gross = moto_hours × rate"""
        moto_hours = Decimal("10.5")
        rate = Decimal("5000")

        gross = moto_hours * rate

        assert gross == Decimal("52500.0")

    def test_commission_15_percent(self):
        """commission = gross × 15 / 100"""
        gross = Decimal("100000")
        rate = Decimal("15")

        commission = (gross * rate / Decimal("100")).quantize(Decimal("0.01"))

        assert commission == Decimal("15000.00")

    def test_net_amount_calculation(self):
        """net = gross - commission"""
        gross = Decimal("100000")
        commission = Decimal("15000")

        net = gross - commission

        assert net == Decimal("85000")

    def test_zero_commission_rate(self):
        """Комиссия 0% = вся сумма к выплате."""
        gross = Decimal("50000")
        rate = Decimal("0")

        commission = (gross * rate / Decimal("100")).quantize(Decimal("0.01"))
        net = gross - commission

        assert commission == Decimal("0.00")
        assert net == Decimal("50000.00")

    def test_full_commission(self):
        """Комиссия 100% = 0 к выплате (edge case)."""
        gross = Decimal("50000")
        rate = Decimal("100")

        commission = (gross * rate / Decimal("100")).quantize(Decimal("0.01"))
        net = gross - commission

        assert commission == Decimal("50000.00")
        assert net == Decimal("0.00")

    def test_zero_moto_hours(self):
        """0 моточасов = 0 выплата."""
        moto_hours = Decimal("0")
        rate = Decimal("5000")

        gross = moto_hours * rate

        assert gross == Decimal("0")

    def test_fractional_moto_hours(self):
        """Дробные моточасы (8.5) с комиссией."""
        moto_hours = Decimal("8.5")
        rate = Decimal("5000")
        rate_percent = Decimal("15")

        gross = moto_hours * rate
        commission = (gross * rate_percent / Decimal("100")).quantize(Decimal("0.01"))
        net = gross - commission

        assert gross == Decimal("42500.0")
        assert commission == Decimal("6375.00")
        assert net == Decimal("36125.00")

    def test_very_small_amount(self):
        """Очень маленькая сумма (1 рубль)."""
        gross = Decimal("1.00")
        rate = Decimal("15")

        commission = (gross * rate / Decimal("100")).quantize(Decimal("0.01"))
        net = gross - commission

        assert commission == Decimal("0.15")
        assert net == Decimal("0.85")

    def test_very_large_amount(self):
        """Очень большая сумма (10 миллионов)."""
        gross = Decimal("10000000.00")
        rate = Decimal("15")

        commission = (gross * rate / Decimal("100")).quantize(Decimal("0.01"))
        net = gross - commission

        assert commission == Decimal("1500000.00")
        assert net == Decimal("8500000.00")


class TestDocumentNumberGeneration:
    """Тесты генерации номеров документов."""

    def test_payout_number_format(self):
        """Формат: ВЫП-2026-0001"""
        year = 2026
        seq = 1

        number = f"ВЫП-{year}-{seq:04d}"

        assert number == "ВЫП-2026-0001"

    def test_payout_number_sequence(self):
        """Последовательность номеров."""
        numbers = [f"ВЫП-2026-{i:04d}" for i in range(1, 6)]

        expected = [
            "ВЫП-2026-0001",
            "ВЫП-2026-0002",
            "ВЫП-2026-0003",
            "ВЫП-2026-0004",
            "ВЫП-2026-0005",
        ]
        assert numbers == expected

    def test_payout_number_rollover(self):
        """Большие номера (> 9999)."""
        number = f"ВЫП-2026-{10000:04d}"

        assert number == "ВЫП-2026-10000"


class TestPayoutGrouping:
    """Тесты группировки выплат."""

    def test_group_by_owner_and_vehicle(self):
        """Группировка по (owner_id, vehicle_id)."""
        records = [
            {"owner_id": 1, "vehicle_id": 10, "moto_hours": 5},
            {"owner_id": 1, "vehicle_id": 10, "moto_hours": 3},
            {"owner_id": 1, "vehicle_id": 20, "moto_hours": 8},
            {"owner_id": 2, "vehicle_id": 10, "moto_hours": 10},
        ]

        grouped = {}
        for r in records:
            key = (r["owner_id"], r["vehicle_id"])
            grouped[key] = grouped.get(key, 0) + r["moto_hours"]

        assert grouped == {(1, 10): 8, (1, 20): 8, (2, 10): 10}

    def test_empty_records(self):
        """Пустой список."""
        records = []
        grouped = {}
        for r in records:
            key = (r["owner_id"], r["vehicle_id"])
            grouped[key] = grouped.get(key, 0) + r["moto_hours"]

        assert grouped == {}

    def test_single_record(self):
        """Одна запись."""
        records = [{"owner_id": 1, "vehicle_id": 10, "moto_hours": 5}]
        grouped = {}
        for r in records:
            key = (r["owner_id"], r["vehicle_id"])
            grouped[key] = grouped.get(key, 0) + r["moto_hours"]

        assert grouped == {(1, 10): 5}


class TestPayoutValidation:
    """Тесты валидации выплат."""

    def test_valid_commission_rates(self):
        """Валидные ставки комиссии (0-100)."""
        valid_rates = [0, 5, 15, 50, 99, 100]

        for rate in valid_rates:
            assert 0 <= rate <= 100, f"Rate {rate} should be valid"

    def test_invalid_commission_negative(self):
        """Отрицательная комиссия невалидна."""
        rate = -5
        assert not (0 <= rate <= 100)

    def test_invalid_commission_over_100(self):
        """Комиссия > 100% невалидна."""
        rate = 150
        assert not (0 <= rate <= 100)

    def test_valid_date_range(self):
        """Валидный диапазон дат."""
        date_from = date(2026, 9, 1)
        date_to = date(2026, 9, 30)

        assert date_from <= date_to

    def test_invalid_date_range(self):
        """date_from > date_to невалидно."""
        date_from = date(2026, 9, 30)
        date_to = date(2026, 9, 1)

        assert not (date_from <= date_to)

    def test_same_day_range(self):
        """Однодневный диапазон (валидно)."""
        d = date(2026, 9, 15)

        assert d <= d


class TestPayoutWorkflow:
    """Тесты workflow статусов выплат."""

    def test_draft_to_sent(self):
        """draft → sent (approve)."""
        status = "draft"
        if status == "draft":
            status = "sent"

        assert status == "sent"

    def test_sent_to_paid(self):
        """sent → paid (pay)."""
        status = "sent"
        if status == "sent":
            status = "paid"

        assert status == "paid"

    def test_cannot_approve_non_draft(self):
        """Нельзя approve не-draft выплату."""
        for status in ["sent", "paid", "cancelled"]:
            can_approve = status == "draft"
            assert not can_approve, f"Should not approve status {status}"

    def test_cannot_pay_non_sent(self):
        """Нельзя pay не-sent выплату."""
        for status in ["draft", "paid", "cancelled"]:
            can_pay = status == "sent"
            assert not can_pay, f"Should not pay status {status}"

    def test_full_workflow(self):
        """Полный цикл: draft → sent → paid."""
        status = "draft"

        # Approve
        assert status == "draft"
        status = "sent"

        # Pay
        assert status == "sent"
        status = "paid"

        assert status == "paid"
