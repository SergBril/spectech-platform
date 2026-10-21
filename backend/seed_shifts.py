"""Seed script for shift tasks and reports."""
import requests, random, time
from datetime import date, datetime, timedelta

BASE = "http://127.0.0.1:8000/api/v1"
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@spectech.dev", "password": "admin123"})
h = {"Authorization": f"Bearer {r.json()['access_token']}", "Content-Type": "application/json"}

vehicles = requests.get(f"{BASE}/vehicles?limit=10", headers=h).json()
v_list = vehicles.get("items", vehicles) if isinstance(vehicles, dict) else vehicles
drivers = requests.get(f"{BASE}/drivers?limit=20", headers=h).json()
d_list = drivers.get("items", []) if isinstance(drivers, dict) else drivers
reqs = requests.get(f"{BASE}/requests?limit=20", headers=h).json()
r_list = reqs if isinstance(reqs, list) else reqs.get("items", [])

today = date.today()
created_tasks = created_reports = errors = 0

for i in range(30):
    shift_date = today - timedelta(days=random.randint(1, 30))
    vehicle = random.choice(v_list)
    driver = random.choice(d_list)
    request = random.choice(r_list)
    vid, did, rid = vehicle.get("id"), driver.get("contractor_id") or driver.get("id"), request.get("id")
    if not all([vid, did, rid]):
        continue
    task_payload = {"request_id": rid, "operator_id": did, "vehicle_id": vid, "shift_date": shift_date.isoformat(), "shift_number": 1, "odometer_start": random.randint(10000, 90000), "moto_hours_start": round(random.uniform(100, 5000), 2), "fuel_level_start": round(random.uniform(20, 80), 2)}
    try:
        resp = requests.post(f"{BASE}/shifts/tasks", json=task_payload, headers=h)
        if resp.status_code == 201:
            task_id = resp.json().get("id")
            created_tasks += 1
            work_start = datetime.combine(shift_date, datetime.min.time().replace(hour=7))
            work_end = datetime.combine(shift_date, datetime.min.time().replace(hour=random.randint(15, 20)))
            report_payload = {"shift_task_id": task_id, "operator_moto_hours": round(random.uniform(4, 10), 2), "operator_odometer": task_payload["odometer_start"] + random.randint(20, 200), "operator_fuel_used": round(random.uniform(10, 60), 2), "operator_work_start": work_start.isoformat(), "operator_work_end": work_end.isoformat(), "operator_idle_hours": round(random.uniform(0.5, 2), 2), "operator_comment": f"Смена {shift_date}"}
            resp2 = requests.post(f"{BASE}/shifts/reports", json=report_payload, headers=h)
            if resp2.status_code in (200, 201):
                created_reports += 1
            else:
                errors += 1
        else:
            errors += 1
    except Exception:
        errors += 1
    if created_tasks % 10 == 0 and created_tasks > 0:
        time.sleep(0.3)

print(f"Created: {created_tasks} tasks, {created_reports} reports, Errors: {errors}")
