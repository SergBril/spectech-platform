"""
Seed скрипт для тестирования финансовой системы.

Сценарий:
1. Использует существующую сверку (reconciliation_id=1)
2. Генерирует счёт автоматически
3. Показывает финансовую сводку
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://127.0.0.1:8000/api/v1"


def login() -> str:
    """Получает JWT токен."""
    response = httpx.post(
        f"{API_BASE}/auth/login",
        json={"email": "admin@spectech.dev", "password": "admin123"},
        timeout=10,
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    raise Exception(f"Login failed: {response.text}")


def generate_invoice(reconciliation_id: int, token: str) -> dict:
    """Генерирует счёт из сверки."""
    response = httpx.post(
        f"{API_BASE}/finance/invoices/generate-from-reconciliation",
        json={
            "reconciliation_id": reconciliation_id,
            "invoice_date": date.today().isoformat(),
            "include_fuel_compensation": True,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return response.json()


def get_finance_summary(token: str) -> dict:
    """Получает финансовую сводку."""
    date_from = (date.today() - timedelta(days=30)).isoformat()
    date_to = date.today().isoformat()

    response = httpx.get(
        f"{API_BASE}/finance/finance/summary?date_from={date_from}&date_to={date_to}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def main():
    print("🚀 Запуск seed скрипта для финансовой системы...")
    print(f"API Base: {API_BASE}")

    # Получаем токен
    print("\n🔑 Получение JWT токена...")
    try:
        token = login()
        print("  ✅ Токен получен")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Генерируем счёт из сверки #1
    print("\n📄 Генерация счёта из сверки #1...")
    try:
        result = generate_invoice(1, token)

        if "document_number" in result:
            print(f"  ✅ Счёт создан: {result['document_number']}")
            print(f"     Итого: {result['total']} руб.")
            print(f"     НДС: {result['vat_amount']} руб.")
            print(f"     Позиций: {len(result.get('items', []))}")

            for item in result.get("items", []):
                print(f"       - {item['description']}: {item['amount']} руб.")
        else:
            print(f"  ❌ Ошибка: {result}")

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Получаем финансовую сводку
    print("\n📊 Финансовая сводка за последние 30 дней...")
    try:
        summary = get_finance_summary(token)

        if "revenue" in summary:
            print(f"  Выручка: {summary['revenue']} руб.")
            print(f"  Расходы: {summary['expenses']} руб.")
            print(f"  Прибыль: {summary['profit']} руб.")
            print(f"  Неоплаченных счетов: {summary['outstanding_invoices']}")
            print(f"  Дебиторка: {summary['outstanding_amount']} руб.")
        else:
            print(f"  ❌ Ошибка: {summary}")

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return


if __name__ == "__main__":
    main()
