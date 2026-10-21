"""Seed script for GPS points."""
import random
from datetime import datetime, timedelta, timezone
from app.core.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
vehicles = db.execute(text("SELECT id, name FROM vehicles")).fetchall()
base_coords = [(55.7558, 37.6173), (55.7420, 37.6230), (55.7610, 37.6050), (55.7350, 37.6400), (55.7700, 37.5900), (55.7200, 37.6500)]
created = 0
now = datetime.now(timezone.utc)
for idx, (vid, vname) in enumerate(vehicles):
    base_lat, base_lon = base_coords[idx % len(base_coords)]
    for i in range(50):
        recorded_at = now - timedelta(hours=random.uniform(0, 24))
        lat = base_lat + random.uniform(-0.045, 0.045)
        lon = base_lon + random.uniform(-0.045, 0.045)
        speed = round(random.uniform(0, 80), 1) if random.random() > 0.2 else 0
        db.execute(text("INSERT INTO gps_points (vehicle_id, latitude, longitude, altitude, speed, heading, engine_on, fuel_level, engine_hours, signal_quality, device_id, recorded_at, received_at) VALUES (:vid, :lat, :lon, :alt, :speed, :heading, :engine_on, :fuel, :eng_hours, :signal, :device_id, :recorded_at, :received_at)"), {"vid": vid, "lat": lat, "lon": lon, "alt": round(random.uniform(120, 180), 1), "speed": speed, "heading": round(random.uniform(0, 360), 1), "engine_on": speed > 0, "fuel": round(random.uniform(15, 95), 1), "eng_hours": round(random.uniform(100, 5000), 2), "signal": random.randint(60, 100), "device_id": f"WIALON-{vid}-{idx}", "recorded_at": recorded_at, "received_at": recorded_at + timedelta(seconds=random.randint(1, 30))})
        created += 1
    if created % 100 == 0:
        db.commit()
db.commit()
print(f"Created {created} GPS points for {len(vehicles)} vehicles")
db.close()
