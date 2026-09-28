"""
Seed скрипт для тестирования Wialon адаптера.

Генерирует mock webhook payload и отправляет в endpoint.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://127.0.0.1:8000/api/v1/telematics"


def generate_mock_webhook(
    unit_id: int,
    lat: float,
    lon: float,
    speed: float,
    fuel_level: float,
    engine_on: bool,
    engine_hours: float,
    timestamp: int,
) -> dict:
    """Генерирует mock webhook payload в формате Wialon."""
    return {
        "unit_id": unit_id,
        "type": "message",
        "time": timestamp,
        "pos": {
            "x": lon,
            "y": lat,
            "z": 0,
            "s": speed,
            "c": 180,
            "t": timestamp,
            "sc": 10,
        },
        "param": {
            "avl_fuel_level": fuel_level,
            "avl_engine_hours": engine_hours,
            "avl_driver_id": 1 if engine_on else 0,
            "signal": 85,
        },
        "device_id": f"device_{unit_id}",
        "raw_data": {"source": "mock_script"},
    }


def send_webhook(payload: dict) -> tuple[bool, dict]:
    """Отправляет webhook в endpoint. Возвращает (success, response)."""
    response = httpx.post(f"{API_BASE}/wialon/webhook", json=payload, timeout=10)
    data = response.json()

    # Проверяем HTTP статус код
    if response.status_code != 200:
        return False, data

    # Проверяем статус в теле ответа
    if data.get("status") != "success":
        return False, data

    return True, data


def main():
    print("🚀 Запуск seed скрипта для Wialon адаптера...")
    print(f"API Base: {API_BASE}")

    # Генерируем тестовые данные для vehicle_id=1 (unit_id=1001)
    # Симулируем 3 часа работы экскаватора
    base_time = datetime.now(UTC) - timedelta(hours=3)

    test_data = [
        # Час 1: начало работы
        {
            "unit_id": 1001,
            "lat": 55.7558,
            "lon": 37.6176,
            "speed": 0,
            "fuel": 200,
            "engine": False,
            "hours": 750,
            "offset_min": 0,
        },
        {
            "unit_id": 1001,
            "lat": 55.7560,
            "lon": 37.6180,
            "speed": 25,
            "fuel": 198,
            "engine": True,
            "hours": 750.5,
            "offset_min": 15,
        },
        {
            "unit_id": 1001,
            "lat": 55.7565,
            "lon": 37.6185,
            "speed": 35,
            "fuel": 195,
            "engine": True,
            "hours": 751,
            "offset_min": 30,
        },
        {
            "unit_id": 1001,
            "lat": 55.7570,
            "lon": 37.6190,
            "speed": 40,
            "fuel": 192,
            "engine": True,
            "hours": 751.5,
            "offset_min": 45,
        },
        # Час 2: активная работа
        {
            "unit_id": 1001,
            "lat": 55.7575,
            "lon": 37.6195,
            "speed": 45,
            "fuel": 188,
            "engine": True,
            "hours": 752,
            "offset_min": 60,
        },
        {
            "unit_id": 1001,
            "lat": 55.7580,
            "lon": 37.6200,
            "speed": 50,
            "fuel": 185,
            "engine": True,
            "hours": 752.5,
            "offset_min": 75,
        },
        {
            "unit_id": 1001,
            "lat": 55.7585,
            "lon": 37.6205,
            "speed": 30,
            "fuel": 182,
            "engine": True,
            "hours": 753,
            "offset_min": 90,
        },
        {
            "unit_id": 1001,
            "lat": 55.7590,
            "lon": 37.6210,
            "speed": 20,
            "fuel": 180,
            "engine": True,
            "hours": 753.5,
            "offset_min": 105,
        },
        # Час 3: завершение работы
        {
            "unit_id": 1001,
            "lat": 55.7595,
            "lon": 37.6215,
            "speed": 15,
            "fuel": 178,
            "engine": True,
            "hours": 754,
            "offset_min": 120,
        },
        {
            "unit_id": 1001,
            "lat": 55.7600,
            "lon": 37.6220,
            "speed": 10,
            "fuel": 176,
            "engine": True,
            "hours": 754.5,
            "offset_min": 135,
        },
        {
            "unit_id": 1001,
            "lat": 55.7605,
            "lon": 37.6225,
            "speed": 5,
            "fuel": 175,
            "engine": True,
            "hours": 755,
            "offset_min": 150,
        },
        {
            "unit_id": 1001,
            "lat": 55.7610,
            "lon": 37.6230,
            "speed": 0,
            "fuel": 175,
            "engine": False,
            "hours": 755,
            "offset_min": 165,
        },
    ]

    success_count = 0
    error_count = 0

    for i, data in enumerate(test_data):
        timestamp = int((base_time + timedelta(minutes=data["offset_min"])).timestamp())

        payload = generate_mock_webhook(
            unit_id=data["unit_id"],
            lat=data["lat"],
            lon=data["lon"],
            speed=data["speed"],
            fuel_level=data["fuel"],
            engine_on=data["engine"],
            engine_hours=data["hours"],
            timestamp=timestamp,
        )

        print(f"\n[{i+1}/{len(test_data)}] Отправка webhook...")
        print(
            f"  unit_id={data['unit_id']}, lat={data['lat']}, speed={data['speed']}, fuel={data['fuel']}"
        )

        try:
            success, response = send_webhook(payload)
            if success:
                print(f"  ✅ SUCCESS: {response}")
                success_count += 1
            else:
                print(f"  ❌ FAILED: {response}")
                error_count += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            error_count += 1

    print(f"\n📊 Итого: {success_count} успешно, {error_count} ошибок")

    # Проверяем агрегацию
    print("\n📊 Проверка continuous aggregate...")
    try:
        response = httpx.get(f"{API_BASE}/gps/1/stats", timeout=10)
        print(f"Stats: {response.json()}")
    except Exception as e:
        print(f"Error fetching stats: {e}")


if __name__ == "__main__":
    main()
