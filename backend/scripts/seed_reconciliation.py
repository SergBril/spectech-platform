"""
Seed скрипт для тестирования сверки данных оператор vs телематика.

Сценарий:
1. Создаёт ShiftTask для vehicle_id=1
2. Создаёт ShiftReport с данными оператора
3. Добавляет GPS точки для симуляции телеметрии
4. Запускает сверку и показывает результат
"""

import sys
from datetime import UTC, datetime, timedelta
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


def create_shift_task(token: str) -> int:
    """Создаёт ShiftTask."""
    response = httpx.post(
        f"{API_BASE}/shifts/tasks",
        json={
            "request_id": 11,
            "operator_id": 4,
            "vehicle_id": 1,
            "shift_date": "2026-09-28",
            "shift_number": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if response.status_code in (200, 201):
        return response.json()["id"]
    raise Exception(f"Failed to create ShiftTask: {response.text}")


def create_shift_report(shift_task_id: int, token: str) -> int:
    """Создаёт ShiftReport с данными оператора."""
    now = datetime.now(UTC)
    response = httpx.post(
        f"{API_BASE}/shifts/reports",
        json={
            "shift_task_id": shift_task_id,
            "operator_moto_hours": 8.0,
            "operator_odometer": 50,
            "operator_fuel_used": 120.0,
            "operator_work_start": (now - timedelta(hours=8)).isoformat(),
            "operator_work_end": now.isoformat(),
            "operator_comment": "Работы выполнены",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if response.status_code in (200, 201):
        return response.json()["id"]
    raise Exception(f"Failed to create ShiftReport: {response.text}")


def add_gps_telemetry(token: str):
    """Добавляет GPS точки для симуляции телеметрии."""
    now = datetime.now(UTC)
    base_lat = 55.7558
    base_lon = 37.6176

    # Симулируем 8 часов работы с небольшими расхождениями
    # Моточасы: ~7.8 часов (расхождение ~2.5%)
    # Пробег: ~48 км (расхождение ~4%)
    # Топливо: ~118л (расхождение ~1.7%)

    points = []
    for i in range(96):  # 96 точек по 5 минут = 8 часов
        time_offset = timedelta(minutes=i * 5)
        recorded_at = now - timedelta(hours=8) + time_offset

        # Двигатель включён 93.6 из 96 точек (97.5% = 7.8 часов)
        engine_on = i < 94

        # Постепенное уменьшение топлива
        fuel_level = 200.0 - (i * 0.85)  # ~82л за 8 часов = 118л расход

        # Движение с переменной скоростью
        speed = 35.0 if engine_on else 0

        points.append(
            {
                "vehicle_id": 1,
                "latitude": base_lat + (i * 0.0005),
                "longitude": base_lon + (i * 0.0005),
                "speed": speed,
                "fuel_level": fuel_level,
                "engine_on": engine_on,
                "recorded_at": recorded_at.isoformat(),
            }
        )

    # Отправляем точки батчами по 20
    for i in range(0, len(points), 20):
        batch = points[i : i + 20]
        response = httpx.post(
            f"{API_BASE}/telematics/gps",
            json=batch,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code in (200, 201):
            print(f"  ✅ Batch {i//20 + 1}/5: {len(batch)} точек сохранено")
        else:
            print(f"  ❌ Batch {i//20 + 1}/5 failed: {response.text}")


def reconcile_shift(shift_task_id: int, token: str) -> dict:
    """Запускает сверку данных."""
    print(f"\n  DEBUG: POST {API_BASE}/telematics/shifts/{shift_task_id}/reconcile")
    response = httpx.post(
        f"{API_BASE}/telematics/shifts/{shift_task_id}/reconcile",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )

    print(f"  DEBUG: HTTP Status: {response.status_code}")
    print(f"  DEBUG: Response: {response.text}")

    if response.status_code != 200:
        print(f"  ❌ Ошибка HTTP {response.status_code}: {response.text}")
        return {}

    return response.json()


def main():
    print("🚀 Запуск seed скрипта для сверки данных...")
    print(f"API Base: {API_BASE}")

    # Получаем токен
    print("\n🔑 Получение JWT токена...")
    try:
        token = login()
        print("  ✅ Токен получен")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Создаём ShiftTask
    print("\n📋 Создание ShiftTask...")
    try:
        shift_task_id = create_shift_task(token)
        print(f"  ✅ ShiftTask создан: id={shift_task_id}")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Создаём ShiftReport
    print("\n📝 Создание ShiftReport (данные оператора)...")
    try:
        report_id = create_shift_report(shift_task_id, token)
        print(f"  ✅ ShiftReport создан: id={report_id}")
        print("  Оператор внёс: 8.0 моточасов, 50 км, 120л топлива")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Добавляем GPS точки
    print("\n📡 Добавление GPS телеметрии (96 точек за 8 часов)...")
    try:
        add_gps_telemetry(token)
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return

    # Запускаем сверку
    print("\n🔍 Запуск сверки данных...")
    try:
        result = reconcile_shift(shift_task_id, token)

        print("\n📊 РЕЗУЛЬТАТ СВЕРКИ:")
        print(f"  ShiftTask ID: {result.get('shift_task_id')}")
        print(f"  Статус: {result.get('status')}")

        print("\n  Данные оператора:")
        op_data = result.get("operator_data", {})
        print(f"    Моточасы: {op_data.get('moto_hours')}")
        print(f"    Пробег: {op_data.get('odometer')} км")
        print(f"    Топливо: {op_data.get('fuel_used')}л")

        print("\n  Данные телеметрии:")
        tel_data = result.get("telematics_data", {})
        print(f"    Моточасы: {tel_data.get('moto_hours')}")
        print(f"    Пробег: {tel_data.get('odometer')} км")
        print(f"    Топливо: {tel_data.get('fuel_used')}л")
        print(f"    Точек данных: {tel_data.get('data_points_count')}")

        print("\n  Расхождения:")
        diffs = result.get("differences", {})
        print(f"    Моточасы: {diffs.get('moto_hours_diff_percent')}%")
        print(f"    Пробег: {diffs.get('odometer_diff_percent')}%")
        print(f"    Топливо: {diffs.get('fuel_diff_percent')}%")

        print("\n  Решение:")
        print(f"    Источник: {result.get('decision_source')}")
        final = result.get("final_values", {})
        print(f"    Финальные моточасы: {final.get('moto_hours')}")
        print(f"    Финальный пробег: {final.get('odometer')}")
        print(f"    Финальное топливо: {final.get('fuel_used')}")

        if result.get("status") == "auto_approved":
            print(
                "\n✅ СВЕРКА ЗАВЕРШЕНА: автоматически подтверждено (расхождение < 5%)"
            )
        elif result.get("status") == "discrepancy_detected":
            print("\n⚠️  ОБНАРУЖЕНО РАСХОЖДЕНИЕ: требуется ручная проверка")
        else:
            print(f"\n📋 Статус: {result.get('status')}")

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return


if __name__ == "__main__":
    main()
