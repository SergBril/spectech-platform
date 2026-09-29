"""
Seed скрипт для тестирования детектора сливов топлива.

Симулирует сценарий слива:
1. Техника стоит на месте (speed=0)
2. Двигатель выключен (engine_on=False)
3. Уровень топлива падает на 15 литров за 5 минут
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://127.0.0.1:8000/api/v1/telematics"


def generate_theft_scenario(vehicle_id: int = 1) -> list[dict]:
    """
    Генерирует серию GPS точек, симулирующих слив топлива.

    Сценарий:
    - Минута 0: уровень 150л, двигатель выключен
    - Минута 1: уровень 148л (потеря 2л — нормально)
    - Минута 2: уровень 145л (потеря 3л — подозрительно)
    - Минута 3: уровень 140л (потеря 5л — очень подозрительно)
    - Минута 4: уровень 135л (потеря 5л — явно слив!)
    - Итого: падение 15л за 5 минут
    """
    base_time = datetime.now(UTC) - timedelta(minutes=5)
    base_lat = 55.7558
    base_lon = 37.6176

    return [
        {
            "vehicle_id": vehicle_id,
            "latitude": base_lat,
            "longitude": base_lon,
            "speed": 0,
            "fuel_level": 150.0,
            "engine_on": False,
            "recorded_at": (base_time + timedelta(minutes=0)).isoformat(),
        },
        {
            "vehicle_id": vehicle_id,
            "latitude": base_lat + 0.00001,
            "longitude": base_lon + 0.00001,
            "speed": 0,
            "fuel_level": 148.0,
            "engine_on": False,
            "recorded_at": (base_time + timedelta(minutes=1)).isoformat(),
        },
        {
            "vehicle_id": vehicle_id,
            "latitude": base_lat + 0.00002,
            "longitude": base_lon + 0.00002,
            "speed": 0,
            "fuel_level": 145.0,
            "engine_on": False,
            "recorded_at": (base_time + timedelta(minutes=2)).isoformat(),
        },
        {
            "vehicle_id": vehicle_id,
            "latitude": base_lat + 0.00003,
            "longitude": base_lon + 0.00003,
            "speed": 0,
            "fuel_level": 140.0,
            "engine_on": False,
            "recorded_at": (base_time + timedelta(minutes=3)).isoformat(),
        },
        {
            "vehicle_id": vehicle_id,
            "latitude": base_lat + 0.00004,
            "longitude": base_lon + 0.00004,
            "speed": 0,
            "fuel_level": 135.0,
            "engine_on": False,
            "recorded_at": (base_time + timedelta(minutes=4)).isoformat(),
        },
    ]


def send_gps_point(point: dict, token: str) -> dict:
    """Отправляет GPS точку в endpoint."""
    response = httpx.post(
        f"{API_BASE}/gps/single",
        json=point,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def detect_theft(vehicle_id: int, token: str) -> dict:
    """Запускает детектор сливов."""
    response = httpx.post(
        f"{API_BASE}/fuel/detect-theft?vehicle_id={vehicle_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def main():
    print("🚀 Запуск seed скрипта для детектора сливов...")
    print(f"API Base: {API_BASE}")

    # Получаем токен (в production используйте настоящий JWT)
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJhZG1pbkBzcGVjdGVjaC5kZXYiLCJleHAiOjE3OTA2Nzk1ODMsImlhdCI6MTc5MDU5MzE4M30.g5FYZUJ0MVF40MPvFK2JS04-M86_It4nFukO9jDMaVY"

    vehicle_id = 1

    # Генерируем сценарий слива
    theft_points = generate_theft_scenario(vehicle_id)

    print(f"\n📍 Отправка {len(theft_points)} GPS точек (симуляция слива)...")
    for i, point in enumerate(theft_points):
        print(
            f"\n[{i+1}/{len(theft_points)}] fuel_level={point['fuel_level']}л, speed={point['speed']} км/ч"
        )
        try:
            response = send_gps_point(point, token)
            if response.get("status") == "ok":
                print("  ✅ GPS точка сохранена")
            else:
                print(f"  ❌ Ошибка: {response}")
        except Exception as e:
            print(f"  ❌ Exception: {e}")

    print("\n🔍 Запуск детектора сливов...")
    try:
        result = detect_theft(vehicle_id, token)
        print("\n📊 Результат детекции:")
        print(f"  Проверено техники: {result.get('checked_vehicles')}")
        print(f"  Обнаружено сливов: {result.get('thefts_detected')}")

        if result.get("thefts_detected", 0) > 0:
            print("\n🚨 ОБНАРУЖЕН СЛИВ:")
            for theft in result.get("thefts", []):
                print(f"  ID: {theft['id']}")
                print(f"  Объём: {theft['volume_liters']}л")
                print(f"  До: {theft['fuel_before']}л → После: {theft['fuel_after']}л")
                print(f"  Время: {theft['occurred_at']}")
                print(
                    f"  Место: ({theft['location']['latitude']}, {theft['location']['longitude']})"
                )
        else:
            print(
                "\n✅ Сливов не обнаружено (возможно, падение < 10л или техника двигалась)"
            )

    except Exception as e:
        print(f"❌ Ошибка детекции: {e}")


if __name__ == "__main__":
    main()
