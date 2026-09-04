"""
GPS Simulator - отправляет GPS точки на бэкенд для тестирования WebSocket.
"""
import asyncio
import random
import httpx
from datetime import datetime, timezone

API_BASE = "http://localhost:8000/api/v1"
EMAIL = "admin@spectech.dev"
PASSWORD = "admin"

async def login(client: httpx.AsyncClient) -> str:
    """Получает JWT токен через OAuth2 password flow."""
    # OAuth2 требует form-urlencoded данные
    resp = await client.post(
        f"{API_BASE}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def get_vehicles(client: httpx.AsyncClient, token: str):
    """Получает список машин."""
    resp = await client.get(
        f"{API_BASE}/vehicles",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def send_gps(client: httpx.AsyncClient, token: str, vehicle_id: int, lat: float, lon: float, speed: float) -> int:
    """Отправляет одну GPS точку."""
    resp = await client.post(
        f"{API_BASE}/telematics/gps/single",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "vehicle_id": vehicle_id,
            "latitude": lat,
            "longitude": lon,
            "speed": speed,
            "heading": random.uniform(0, 360),
            "altitude": random.uniform(100, 200),
            "engine_on": True,
            "engine_hours": random.uniform(100, 1000),
            "fuel_level": random.uniform(30, 90),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return resp.status_code


async def simulate_vehicle(client: httpx.AsyncClient, token: str, vehicle_id: int, name: str):
    """Симулирует движение одной машины."""
    lat = 55.7558 + random.uniform(-0.05, 0.05)
    lon = 37.6173 + random.uniform(-0.05, 0.05)
    print(f"🚗 {name} (ID={vehicle_id}) starting at ({lat:.4f}, {lon:.4f})")

    for i in range(30):
        # Скорость 20-120 км/ч (чтобы иногда превышать 90 и вызывать алерты)
        speed = random.uniform(20, 120)

        # Движение
        distance_deg = speed / 111.0 / 3600.0 * 2
        lat += distance_deg * 0.7 * random.uniform(0.5, 1.5)
        lon += distance_deg * random.uniform(0.5, 1.5)

        try:
            status = await send_gps(client, token, vehicle_id, lat, lon, speed)
            print(f"  [{i+1:2d}/30] {name}: ({lat:.4f}, {lon:.4f}) speed={speed:.1f} km/h, status={status}")
        except Exception as e:
            print(f"  [{i+1:2d}/30] {name}: ERROR {type(e).__name__}: {e}")

        await asyncio.sleep(2)

    print(f"✅ {name} finished")


async def main():
    print("🚀 GPS Simulator")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            token = await login(client)
            print(f"✅ Logged in, token: {token[:20]}...")
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return

        try:
            vehicles = await get_vehicles(client, token)
            print(f"📋 Found {len(vehicles)} vehicles:")
            for v in vehicles:
                print(f"   - {v['name']} (ID={v['id']})")
        except Exception as e:
            print(f"❌ Get vehicles failed: {e}")
            return

        if not vehicles:
            print("❌ No vehicles found")
            return

        print()
        print("▶️  Starting simulation...")
        tasks = []
        for v in vehicles:
            tasks.append(simulate_vehicle(client, token, v["id"], v["name"]))

        await asyncio.gather(*tasks)
        print()
        print("🎉 Simulation complete!")


if __name__ == "__main__":
    asyncio.run(main())
