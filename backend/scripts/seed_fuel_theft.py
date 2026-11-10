import os
"""
Seed СЃРєСЂРёРїС‚ РґР»СЏ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ РґРµС‚РµРєС‚РѕСЂР° СЃР»РёРІРѕРІ С‚РѕРїР»РёРІР°.

РЎРёРјСѓР»РёСЂСѓРµС‚ СЃС†РµРЅР°СЂРёР№ СЃР»РёРІР°:
1. РўРµС…РЅРёРєР° СЃС‚РѕРёС‚ РЅР° РјРµСЃС‚Рµ (speed=0)
2. Р”РІРёРіР°С‚РµР»СЊ РІС‹РєР»СЋС‡РµРЅ (engine_on=False)
3. РЈСЂРѕРІРµРЅСЊ С‚РѕРїР»РёРІР° РїР°РґР°РµС‚ РЅР° 15 Р»РёС‚СЂРѕРІ Р·Р° 5 РјРёРЅСѓС‚
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://127.0.0.1:8000/api/v1/telematics"


def generate_theft_scenario(vehicle_id: int = 1) -> list[dict]:
    """
    Р“РµРЅРµСЂРёСЂСѓРµС‚ СЃРµСЂРёСЋ GPS С‚РѕС‡РµРє, СЃРёРјСѓР»РёСЂСѓСЋС‰РёС… СЃР»РёРІ С‚РѕРїР»РёРІР°.

    РЎС†РµРЅР°СЂРёР№:
    - РњРёРЅСѓС‚Р° 0: СѓСЂРѕРІРµРЅСЊ 150Р», РґРІРёРіР°С‚РµР»СЊ РІС‹РєР»СЋС‡РµРЅ
    - РњРёРЅСѓС‚Р° 1: СѓСЂРѕРІРµРЅСЊ 148Р» (РїРѕС‚РµСЂСЏ 2Р» вЂ” РЅРѕСЂРјР°Р»СЊРЅРѕ)
    - РњРёРЅСѓС‚Р° 2: СѓСЂРѕРІРµРЅСЊ 145Р» (РїРѕС‚РµСЂСЏ 3Р» вЂ” РїРѕРґРѕР·СЂРёС‚РµР»СЊРЅРѕ)
    - РњРёРЅСѓС‚Р° 3: СѓСЂРѕРІРµРЅСЊ 140Р» (РїРѕС‚РµСЂСЏ 5Р» вЂ” РѕС‡РµРЅСЊ РїРѕРґРѕР·СЂРёС‚РµР»СЊРЅРѕ)
    - РњРёРЅСѓС‚Р° 4: СѓСЂРѕРІРµРЅСЊ 135Р» (РїРѕС‚РµСЂСЏ 5Р» вЂ” СЏРІРЅРѕ СЃР»РёРІ!)
    - РС‚РѕРіРѕ: РїР°РґРµРЅРёРµ 15Р» Р·Р° 5 РјРёРЅСѓС‚
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
    """РћС‚РїСЂР°РІР»СЏРµС‚ GPS С‚РѕС‡РєСѓ РІ endpoint."""
    response = httpx.post(
        f"{API_BASE}/gps/single",
        json=point,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def detect_theft(vehicle_id: int, token: str) -> dict:
    """Р—Р°РїСѓСЃРєР°РµС‚ РґРµС‚РµРєС‚РѕСЂ СЃР»РёРІРѕРІ."""
    response = httpx.post(
        f"{API_BASE}/fuel/detect-theft?vehicle_id={vehicle_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return response.json()


def main():
    print("рџљЂ Р—Р°РїСѓСЃРє seed СЃРєСЂРёРїС‚Р° РґР»СЏ РґРµС‚РµРєС‚РѕСЂР° СЃР»РёРІРѕРІ...")
    print(f"API Base: {API_BASE}")

    # РџРѕР»СѓС‡Р°РµРј С‚РѕРєРµРЅ (РІ production РёСЃРїРѕР»СЊР·СѓР№С‚Рµ РЅР°СЃС‚РѕСЏС‰РёР№ JWT)
    token = os.environ.get("SEED_AUTH_TOKEN", "REPLACE_WITH_REAL_TOKEN")

    vehicle_id = 1

    # Р“РµРЅРµСЂРёСЂСѓРµРј СЃС†РµРЅР°СЂРёР№ СЃР»РёРІР°
    theft_points = generate_theft_scenario(vehicle_id)

    print(f"\nрџ“Ќ РћС‚РїСЂР°РІРєР° {len(theft_points)} GPS С‚РѕС‡РµРє (СЃРёРјСѓР»СЏС†РёСЏ СЃР»РёРІР°)...")
    for i, point in enumerate(theft_points):
        print(
            f"\n[{i+1}/{len(theft_points)}] fuel_level={point['fuel_level']}Р», speed={point['speed']} РєРј/С‡"
        )
        try:
            response = send_gps_point(point, token)
            if response.get("status") == "ok":
                print("  вњ… GPS С‚РѕС‡РєР° СЃРѕС…СЂР°РЅРµРЅР°")
            else:
                print(f"  вќЊ РћС€РёР±РєР°: {response}")
        except Exception as e:
            print(f"  вќЊ Exception: {e}")

    print("\nрџ”Ќ Р—Р°РїСѓСЃРє РґРµС‚РµРєС‚РѕСЂР° СЃР»РёРІРѕРІ...")
    try:
        result = detect_theft(vehicle_id, token)
        print("\nрџ“Љ Р РµР·СѓР»СЊС‚Р°С‚ РґРµС‚РµРєС†РёРё:")
        print(f"  РџСЂРѕРІРµСЂРµРЅРѕ С‚РµС…РЅРёРєРё: {result.get('checked_vehicles')}")
        print(f"  РћР±РЅР°СЂСѓР¶РµРЅРѕ СЃР»РёРІРѕРІ: {result.get('thefts_detected')}")

        if result.get("thefts_detected", 0) > 0:
            print("\nрџљЁ РћР‘РќРђР РЈР–Р•Рќ РЎР›РР’:")
            for theft in result.get("thefts", []):
                print(f"  ID: {theft['id']}")
                print(f"  РћР±СЉС‘Рј: {theft['volume_liters']}Р»")
                print(f"  Р”Рѕ: {theft['fuel_before']}Р» в†’ РџРѕСЃР»Рµ: {theft['fuel_after']}Р»")
                print(f"  Р’СЂРµРјСЏ: {theft['occurred_at']}")
                print(
                    f"  РњРµСЃС‚Рѕ: ({theft['location']['latitude']}, {theft['location']['longitude']})"
                )
        else:
            print(
                "\nвњ… РЎР»РёРІРѕРІ РЅРµ РѕР±РЅР°СЂСѓР¶РµРЅРѕ (РІРѕР·РјРѕР¶РЅРѕ, РїР°РґРµРЅРёРµ < 10Р» РёР»Рё С‚РµС…РЅРёРєР° РґРІРёРіР°Р»Р°СЃСЊ)"
            )

    except Exception as e:
        print(f"вќЊ РћС€РёР±РєР° РґРµС‚РµРєС†РёРё: {e}")


if __name__ == "__main__":
    main()


