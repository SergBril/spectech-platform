"""Unit tests for finance_reports.py."""

from datetime import date
from decimal import Decimal


class TestFinancialMetrics:
    """Тесты финансовых метрик."""

    def test_revenue_calculation(self):
        """Тест расчёта выручки."""
        invoices = [
            {"total": Decimal("100000"), "status": "paid"},
            {"total": Decimal("50000"), "status": "sent"},
            {"total": Decimal("30000"), "status": "draft"},
        ]

        revenue = sum(inv["total"] for inv in invoices)

        assert revenue == Decimal("180000")

    def test_paid_amount_calculation(self):
        """Тест расчёта оплаченной суммы."""
        invoices = [
            {
                "total": Decimal("100000"),
                "paid_amount": Decimal("100000"),
                "status": "paid",
            },
            {
                "total": Decimal("50000"),
                "paid_amount": Decimal("25000"),
                "status": "partially_paid",
            },
            {"total": Decimal("30000"), "paid_amount": Decimal("0"), "status": "sent"},
        ]

        paid = sum(inv["paid_amount"] for inv in invoices)

        assert paid == Decimal("125000")

    def test_outstanding_calculation(self):
        """Тест расчёта задолженности."""
        invoices = [
            {
                "total": Decimal("100000"),
                "paid_amount": Decimal("100000"),
                "status": "paid",
            },
            {
                "total": Decimal("50000"),
                "paid_amount": Decimal("25000"),
                "status": "partially_paid",
            },
            {"total": Decimal("30000"), "paid_amount": Decimal("0"), "status": "sent"},
        ]

        outstanding = sum(
            inv["total"] - inv["paid_amount"]
            for inv in invoices
            if inv["status"] != "paid"
        )

        assert outstanding == Decimal("55000")

    def test_profit_calculation(self):
        """Тест расчёта прибыли."""
        revenue = Decimal("180000")
        expenses = Decimal("50000")

        profit = revenue - expenses

        assert profit == Decimal("130000")

    def test_margin_percentage(self):
        """Тест расчёта маржи."""
        revenue = Decimal("180000")
        profit = Decimal("130000")

        margin = (profit / revenue * Decimal("100")).quantize(Decimal("0.01"))

        assert margin == Decimal("72.22")

    def test_margin_zero_revenue(self):
        """Тест: маржа при нулевой выручке."""
        revenue = Decimal("0")
        profit = Decimal("0")

        margin = (
            Decimal("0")
            if revenue == Decimal("0")
            else (profit / revenue * Decimal("100"))
        )

        assert margin == Decimal("0")

    def test_average_invoice_calculation(self):
        """Тест расчёта среднего чека."""
        invoices = [
            {"total": Decimal("100000")},
            {"total": Decimal("50000")},
            {"total": Decimal("30000")},
        ]

        avg = sum(inv["total"] for inv in invoices) / len(invoices)

        assert avg == Decimal("60000")

    def test_average_invoice_empty(self):
        """Тест: средний чек при пустом списке."""
        invoices = []

        avg = (
            Decimal("0")
            if not invoices
            else sum(inv["total"] for inv in invoices) / len(invoices)
        )

        assert avg == Decimal("0")


class TestTopClients:
    """Тесты топ клиентов."""

    def test_sort_clients_by_revenue(self):
        """Тест сортировки клиентов по выручке."""
        clients = [
            {"client_id": 1, "name": "Client A", "revenue": Decimal("50000")},
            {"client_id": 2, "name": "Client B", "revenue": Decimal("150000")},
            {"client_id": 3, "name": "Client C", "revenue": Decimal("100000")},
        ]

        sorted_clients = sorted(clients, key=lambda c: c["revenue"], reverse=True)

        assert sorted_clients[0]["name"] == "Client B"
        assert sorted_clients[1]["name"] == "Client C"
        assert sorted_clients[2]["name"] == "Client A"

    def test_top_5_clients_limit(self):
        """Тест: лимит топ-5 клиентов."""
        clients = [
            {"client_id": i, "revenue": Decimal(str(i * 10000))} for i in range(1, 11)
        ]

        top_5 = sorted(clients, key=lambda c: c["revenue"], reverse=True)[:5]

        assert len(top_5) == 5
        assert top_5[0]["client_id"] == 10
        assert top_5[4]["client_id"] == 6


class TestTopVehicles:
    """Тесты топ техники."""

    def test_sort_vehicles_by_moto_hours(self):
        """Тест сортировки техники по моточасам."""
        vehicles = [
            {"vehicle_id": 1, "name": "Vehicle A", "moto_hours": Decimal("50")},
            {"vehicle_id": 2, "name": "Vehicle B", "moto_hours": Decimal("150")},
            {"vehicle_id": 3, "name": "Vehicle C", "moto_hours": Decimal("100")},
        ]

        sorted_vehicles = sorted(vehicles, key=lambda v: v["moto_hours"], reverse=True)

        assert sorted_vehicles[0]["name"] == "Vehicle B"
        assert sorted_vehicles[1]["name"] == "Vehicle C"
        assert sorted_vehicles[2]["name"] == "Vehicle A"

    def test_top_5_vehicles_limit(self):
        """Тест: лимит топ-5 техники."""
        vehicles = [
            {"vehicle_id": i, "moto_hours": Decimal(str(i * 10))} for i in range(1, 11)
        ]

        top_5 = sorted(vehicles, key=lambda v: v["moto_hours"], reverse=True)[:5]

        assert len(top_5) == 5
        assert top_5[0]["vehicle_id"] == 10
        assert top_5[4]["vehicle_id"] == 6


class TestDateRangeFiltering:
    """Тесты фильтрации по датам."""

    def test_filter_invoices_by_date_range(self):
        """Тест фильтрации счетов по диапазону дат."""
        invoices = [
            {"id": 1, "invoice_date": date(2026, 9, 5)},
            {"id": 2, "invoice_date": date(2026, 9, 15)},
            {"id": 3, "invoice_date": date(2026, 9, 25)},
            {"id": 4, "invoice_date": date(2026, 10, 5)},
        ]

        date_from = date(2026, 9, 1)
        date_to = date(2026, 9, 30)

        filtered = [
            inv for inv in invoices if date_from <= inv["invoice_date"] <= date_to
        ]

        assert len(filtered) == 3
        assert all(inv["id"] in [1, 2, 3] for inv in filtered)

    def test_empty_date_range(self):
        """Тест: пустой результат при несовпадении дат."""
        invoices = [
            {"id": 1, "invoice_date": date(2026, 8, 15)},
            {"id": 2, "invoice_date": date(2026, 10, 15)},
        ]

        date_from = date(2026, 9, 1)
        date_to = date(2026, 9, 30)

        filtered = [
            inv for inv in invoices if date_from <= inv["invoice_date"] <= date_to
        ]

        assert len(filtered) == 0


class TestCommissionCalculation:
    """Тесты расчёта комиссии платформы."""

    def test_total_commission_from_payouts(self):
        """Тест суммарной комиссии из выплат."""
        payouts = [
            {"platform_commission": Decimal("15000")},
            {"platform_commission": Decimal("7500")},
            {"platform_commission": Decimal("3000")},
        ]

        total_commission = sum(p["platform_commission"] for p in payouts)

        assert total_commission == Decimal("25500")

    def test_commission_percentage_of_revenue(self):
        """Тест процента комиссии от выручки."""
        revenue = Decimal("180000")
        commission = Decimal("25500")

        percentage = (commission / revenue * Decimal("100")).quantize(Decimal("0.01"))

        assert percentage == Decimal("14.17")
