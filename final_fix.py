import subprocess
import sys
import os

print("=" * 60)
print("FINAL FIX - SOLVING ALL ISSUES")
print("=" * 60)

# ===== 1. INSTALL PASSLIB =====
print("\n[1/3] Installing passlib...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "passlib[bcrypt]", "--quiet"])
print("✅ passlib installed")

# ===== 2. FIX ADMIN PASSWORD =====
print("\n[2/3] Fixing admin password...")
sys.path.insert(0, 'backend')
from backend.app.core.db import SessionLocal
from backend.app.models.auth import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db = SessionLocal()
admin = db.query(User).filter(User.email == "admin@spectech.dev").first()

if admin:
    print(f"  Found admin: ID={admin.id}")
    # Проверяем все поля
    cols = [c.name for c in admin.__table__.columns]
    print(f"  Columns: {cols}")
    
    # Сбрасываем пароль
    admin.hashed_password = pwd_context.hash("admin")
    
    # Если есть is_active - включаем
    if hasattr(admin, 'is_active'):
        admin.is_active = True
        print("  Set is_active=True")
    
    db.commit()
    print("✅ Password reset using passlib.CryptContext")
    print("   Password: 'admin'")
    
    # Проверяем что хеш работает
    test = pwd_context.verify("admin", admin.hashed_password)
    print(f"  Verification test: {test}")
else:
    print("❌ Admin not found!")

db.close()

# ===== 3. FIX PAGE.TSX =====
print("\n[3/3] Fixing page.tsx WebSocket block...")
page_path = 'frontend/src/app/telematics/page.tsx'

with open(page_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Удаляем дублированный импорт toast
lines = content.split('\n')
new_lines = []
toast_seen = False
for line in lines:
    if 'import toast, { Toaster } from "react-hot-toast";' in line:
        if not toast_seen:
            new_lines.append(line)
            toast_seen = True
    else:
        new_lines.append(line)
content = '\n'.join(new_lines)

# Находим и заменяем сломанный блок WebSocket
old_block_start = 'console.log("🔌 Connecting to WebSocket...");'
old_block_end_pattern = 'return () => {\n   console.log("🔌 Disconnecting WebSocket");\n   ws.disconnect();\n };'

start_idx = content.find(old_block_start)
end_idx = content.find(old_block_end_pattern)

if start_idx >= 0 and end_idx >= 0:
    end_idx += len(old_block_end_pattern)
    
    new_block = '''console.log("🔌 Connecting to WebSocket...");
 const ws = new SpectechWebSocket(token, {
   onConnected: () => {
     console.log("✅ WebSocket connected, subscribing to GPS and Alerts");
     setWsConnected(true);
     ws.subscribe("gps");
     ws.subscribe("alerts");
   },
   onGpsPoint: (data: any) => {
     console.log("📍 New GPS point:", data);
     setGpsMessagesCount((prev) => prev + 1);
     const gpsData = data.data;
     setVehicles((prev) => {
       const exists = prev.some((v) => v.id === gpsData.vehicle_id);
       if (exists) {
         return prev.map((v) =>
           v.id === gpsData.vehicle_id
             ? {
                 ...v,
                 last_lat: gpsData.lat,
                 last_lon: gpsData.lon,
                 last_speed: gpsData.speed,
                 last_updated: gpsData.recorded_at,
               }
             : v
         );
       } else {
         return [
           ...prev,
           {
             id: gpsData.vehicle_id,
             name: "Машина #" + gpsData.vehicle_id,
             status: "online",
             last_lat: gpsData.lat,
             last_lon: gpsData.lon,
             last_speed: gpsData.speed,
             last_updated: gpsData.recorded_at,
           },
         ];
       }
     });
   },
   onAlert: (data: any) => {
     console.log("🚨 New alert:", data);
     const alertData = data.data;
     setAlerts((prev) => {
       const exists = prev.some((a) => a.id === alertData.id);
       if (exists) return prev;
       return [alertData, ...prev];
     });
     const severity = alertData.severity;
     toast.error(alertData.title, {
       duration: 5000,
       style: {
         background: severity === "critical" ? "#fee2e2" : severity === "warning" ? "#fef3c7" : "#dbeafe",
         color: severity === "critical" ? "#991b1b" : severity === "warning" ? "#92400e" : "#1e40af",
         border: "2px solid " + (severity === "critical" ? "#ef4444" : severity === "warning" ? "#f59e0b" : "#3b82f6"),
       },
     });
   },
   onDisconnected: () => {
     console.log("❌ WebSocket disconnected");
     setWsConnected(false);
   },
   onError: (error: any) => console.error("WS error:", error),
 });
 ws.connect();
 wsRef.current = ws;
 return () => {
   console.log("🔌 Disconnecting WebSocket");
   ws.disconnect();
 };'''
    
    content = content[:start_idx] + new_block + content[end_idx:]
    
    with open(page_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ page.tsx fixed:")
    print("   - Removed duplicate toast import")
    print("   - Added ws.subscribe('alerts')")
    print("   - Added onAlert handler with toast.error")
    print("   - Added ws.connect() and wsRef.current = ws")
    print("   - Added onDisconnected and onError")
else:
    print(f"⚠️  Could not find exact WebSocket block (start={start_idx}, end={end_idx})")

print()
print("=" * 60)
print("ALL FIXES APPLIED!")
print("=" * 60)
print()
print("NEXT STEPS:")
print("1. Restart uvicorn (Ctrl+C in uvicorn window, then:")
print("   cd backend")
print("   uvicorn app.main:app --reload --port 8000)")
print("2. Refresh browser (Ctrl+F5) on http://localhost:3000/telematics")
print("3. Run simulator:")
print("   cd backend")
print("   .venv\\Scripts\\python.exe scripts\\gps_simulator.py")