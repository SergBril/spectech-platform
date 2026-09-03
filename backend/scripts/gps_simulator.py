"""Симулятор движения техники для тестирования Live GPS."""
import asyncio
import random
import httpx
import time
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


async def login():
    """Получает токен."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API}/auth/login", json={
            "email": "admin@spectech.dev",
            "password": "admin123",
        })
        return resp.json()["access_token"]


async def get_vehicles(token: str):
    """Получает список техники."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/vehicles",
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.json()


async def send_gps(token: str, vehicle_id: int, lat: float, lon: float, speed: float):
    """Отправляет GPS точку."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/telematics/gps/single",
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


async def simulate_vehicle(vehicle_id: int, vehicle_name: str, token: str):
    """Симулирует движение одной техники."""
    # Стартовая позиция (Москва)
    lat = 55.7558 + random.uniform(-0.05, 0.05)
    lon = 37.6173 + random.uniform(-0.05, 0.05)
    
    print(f"🚗 {vehicle_name} (ID={vehicle_id}) starting at ({lat:.4f}, {lon:.4f})")
    
    for i in range(30):  # 30 точек = 60 секунд при интервале 2с
        # Движение
        speed = random.uniform(20, 80)  # км/ч
        distance_km = speed * (2 / 3600)  # за 2 секунды
        distance_deg = distance_km / 111  # примерно
        
        lat += distance_deg * 0.7 * random.uniform(0.5, 1.5)
        lon += distance_deg * random.uniform(0.5, 1.5)
        
        status = await send_gps(token, vehicle_id, lat, lon, speed)
        
        print(f"  [{i+1:2d}/30] {vehicle_name}: ({lat:.4f}, {lon:.4f}) "
              f"speed={speed:.1f} km/h, status={status}")
        
        await asyncio.sleep(2)  # Отправляем каждые 2 секунды


async def main():
    """Запускает симуляцию для нескольких машин."""
    print("🚀 GPS Simulator")
    print("=" * 60)
    
    try:
        token = await login()
        print(f"✅ Logged in, token: {token[:30]}...")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        print("   Убедитесь что backend запущен: uvicorn app.main:app --reload --port 8000")
        return
    
    try:
        vehicles = await get_vehicles(token)
        if not vehicles:
            print("❌ No vehicles found. Create vehicles first at /vehicles")
            return
        
        print(f"📋 Found {len(vehicles)} vehicles:")
        for v in vehicles[:5]:
            print(f"   - {v['name']} (ID={v['id']})")
        
        # Запускаем симуляцию для первых 3 машин
        tasks = []
        for vehicle in vehicles[:3]:
            print(f"\n▶️  Starting simulation for: {vehicle['name']}")
            tasks.append(simulate_vehicle(vehicle["id"], vehicle["name"], token))
        
        await asyncio.gather(*tasks)
        
        print("\n✅ Simulation completed!")
        print("\n📊 Check the map at http://localhost:3000/telematics")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())