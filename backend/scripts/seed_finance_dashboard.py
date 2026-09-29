"""
Seed скрипт для тестирования финансового дашборда.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://127.0.0.1:8000/api/v1"


def login() -> str:
    response = httpx.post(
        f"{API_BASE}/auth/login",
        json={  # pragma: allowlist secret
            "email": "admin@spectech.dev",
            "password": "admin123",  # pragma: allowlist secret
        },
        timeout=10,
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    raise Exception(f"Login failed: {response.text}")


def get_dashboard(token: str, date_from: str, date_to: str) -> dict:
    response = httpx.get(
        f"{API_BASE}/finance/dashboard?date_from={date_from}&date_to={date_to}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return response.json()


def get_revenue_by_client(token: str, date_from: str, date_to: str) -> dict:
    response = httpx.get(
        f"{API_BASE}/finance/revenue-by-client?date_from={date_from}&date_to={date_to}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return response.json()


def get_revenue_by_vehicle(token: str, date_from: str, date_to: str) -> dict:
    response = httpx.get(
        f"{API_BASE}/finance/revenue-by-vehicle?date_from={date_from}&date_to={date_to}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return response.json()


def main():
    print("🚀 Запуск seed скрипта для финансового дашборда...")

    token = login()
    print("✅ Токен получен")

    date_from = "2026-09-01"
    date_to = "2026-09-30"

    print(f"\n📊 Финансовый дашборд за {date_from} - {date_to}...")
    dashboard = get_dashboard(token, date_from, date_to)

    if "revenue" in dashboard:
        print("\n💰 ВЫРУЧКА:")
        print(f"   Всего: {dashboard['revenue']['total']:,.2f} руб.")
        print(f"   Оплачено: {dashboard['revenue']['paid']:,.2f} руб.")
        print(f"   Дебиторка: {dashboard['revenue']['outstanding']:,.2f} руб.")

        print("\n💸 РАСХОДЫ:")
        print(f"   Выплаты: {dashboard['expenses']['payouts']:,.2f} руб.")
        print(f"   Комиссия: {dashboard['expenses']['commission']:,.2f} руб.")

        print("\n📈 ПРИБЫЛЬ:")
        print(f"   Gross: {dashboard['profit']['gross']:,.2f} руб.")
        print(f"   Net: {dashboard['profit']['net']:,.2f} руб.")
        print(f"   Маржа: {dashboard['profit']['margin_percent']:.2f}%")

        print("\n📊 МЕТРИКИ:")
        print(f"   Счетов: {dashboard['metrics']['invoices_count']}")
        print(f"   Средний чек: {dashboard['metrics']['avg_invoice']:,.2f} руб.")
        print(f"   Выплат: {dashboard['metrics']['payouts_count']}")
        print(f"   Моточасов: {dashboard['metrics']['moto_hours_total']:.2f}")
    else:
        print(f"❌ Ошибка: {dashboard}")

    print("\n👥 Топ клиентов по выручке...")
    clients = get_revenue_by_client(token, date_from, date_to)
    if "clients" in clients:
        for c in clients["clients"]:
            print(
                f"   {c['client_name']}: {c['total_revenue']:,.2f} руб. ({c['invoices_count']} счетов)"
            )

    print("\n🚜 Топ техники по моточасам...")
    vehicles = get_revenue_by_vehicle(token, date_from, date_to)
    if "vehicles" in vehicles:
        for v in vehicles["vehicles"]:
            print(
                f"   {v['vehicle_name']}: {v['moto_hours']:.2f} м/ч ({v['shifts_count']} смен)"
            )

    print("\n✅ Seed завершён!")


if __name__ == "__main__":
    main()
