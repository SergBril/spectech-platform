"""
Seed скрипт для тестирования сервиса выплат собственникам.

Сценарий:
1. Рассчитывает выплаты за сентябрь 2026
2. Показывает список созданных выплат
3. Одобряет первую выплату
4. Отмечает её как выплаченную
5. Показывает сводку по выплатам
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://127.0.0.1:8000/api/v1"


def login() -> str:
    """Получает JWT токен."""
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


def calculate_payouts(token: str, date_from: str, date_to: str) -> dict:
    """Рассчитывает выплаты за период."""
    response = httpx.post(
        f"{API_BASE}/finance/payouts/calculate?date_from={date_from}&date_to={date_to}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return response.json()


def approve_payout(payout_id: int, token: str) -> dict:
    """Одобряет выплату."""
    response = httpx.post(
        f"{API_BASE}/finance/payouts/{payout_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def pay_payout(payout_id: int, token: str) -> dict:
    """Отмечает выплату как выплаченную."""
    response = httpx.post(
        f"{API_BASE}/finance/payouts/{payout_id}/pay",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def get_summary(token: str, date_from: str, date_to: str) -> dict:
    """Получает сводку по выплатам."""
    response = httpx.get(
        f"{API_BASE}/finance/payouts/summary?date_from={date_from}&date_to={date_to}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def main():
    print("🚀 Запуск seed скрипта для сервиса выплат...")
    print(f"API Base: {API_BASE}")

    # Получаем токен
    print("\n🔑 Получение JWT токена...")
    try:
        token = login()
        print("  ✅ Токен получен")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Период: сентябрь 2026
    date_from = "2026-09-01"
    date_to = "2026-09-30"

    # Рассчитываем выплаты
    print(f"\n💰 Расчёт выплат за период {date_from} - {date_to}...")
    try:
        result = calculate_payouts(token, date_from, date_to)

        if "total_payouts" in result:
            print(f"  ✅ Создано выплат: {result['total_payouts']}")
            print(f"     Общая сумма (gross): {result['total_gross']:,.2f} руб.")
            print(f"     Комиссия платформы: {result['total_commission']:,.2f} руб.")
            print(f"     К выплате (net): {result['total_net']:,.2f} руб.")
            print(f"     Ставка комиссии: {result.get('commission_rate', 15)}%")

            if result.get("payouts"):
                print("\n  📋 Список выплат:")
                for p in result["payouts"]:
                    print(f"\n     Выплата #{p['payout_id']} ({p['document_number']})")
                    print(f"       Техника: {p['vehicle_name']}")
                    print(f"       Моточасы: {p['moto_hours']:.2f}")
                    print(f"       Смен: {p['shifts_count']}")
                    print(f"       Gross: {p['gross_amount']:,.2f} руб.")
                    print(f"       Комиссия: {p['commission']:,.2f} руб.")
                    print(f"       Net: {p['net_amount']:,.2f} руб.")
        else:
            print(f"  ❌ Ошибка: {result}")
            return

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Одобряем и выплачиваем первую выплату
    if result.get("payouts"):
        first_payout = result["payouts"][0]
        payout_id = first_payout["payout_id"]

        print(f"\n✅ Одобрение выплаты #{payout_id}...")
        try:
            approve_result = approve_payout(payout_id, token)
            print(f"  ✅ {approve_result.get('message')}")
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")

        print(f"\n💸 Отметка выплаты #{payout_id} как выплаченной...")
        try:
            pay_result = pay_payout(payout_id, token)
            print(f"  ✅ {pay_result.get('message')}")
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")

    # Показываем сводку
    print(f"\n📊 Сводка по выплатам за {date_from} - {date_to}...")
    try:
        summary = get_summary(token, date_from, date_to)

        if "total_payouts" in summary:
            print(f"  Всего выплат: {summary['total_payouts']}")
            print(f"  Gross сумма: {summary['total_gross']:,.2f} руб.")
            print(f"  Комиссия: {summary['total_commission']:,.2f} руб.")
            print(f"  Net сумма: {summary['total_net']:,.2f} руб.")
            print(f"  Ожидают выплаты: {summary['pending_payouts']}")
        else:
            print(f"  ❌ Ошибка: {summary}")

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")

    print("\n✅ Seed завершён успешно!")


if __name__ == "__main__":
    main()
