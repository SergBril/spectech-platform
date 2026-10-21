
import requests, random, time
from datetime import date, timedelta

BASE = "http://127.0.0.1:8000/api/v1"
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@spectech.dev", "password": "admin123"})
h = {"Authorization": f"Bearer {r.json()['access_token']}", "Content-Type": "application/json"}

dr = requests.get(f"{BASE}/drivers?limit=200", headers=h).json()
items = dr.get("items", [])
print(f"Updating {len(items)} drivers with documents...")

updated = errors = 0
today = date.today()

for d in items:
    cid = d.get("contractor_id") or d.get("id")
    if not cid:
        continue
    is_expired = random.random() < 0.2
    payload = {
        "passport_series": f"{random.randint(1000,9999)}",
        "passport_number": f"{random.randint(100000,999999)}",
        "passport_issued_by": f"ОВД района {random.choice(['Центральный','Ленинский','Советский','Кировский'])}",
        "passport_issue_date": (today - timedelta(days=random.randint(3650,18000))).isoformat(),
        "date_of_birth": (today - timedelta(days=random.randint(9000,22000))).isoformat(),
        "hire_date": (today - timedelta(days=random.randint(30,3000))).isoformat(),
        "license_number": f"{random.randint(10,99)} {random.randint(10,99)} {random.randint(100000,999999)}",
        "license_category": random.choice(["B","C","D","CE","DE"]),
        "license_issue_date": (today - timedelta(days=random.randint(365,7300))).isoformat(),
        "license_expiry_date": (today + timedelta(days=random.randint(-60,730) if not is_expired else random.randint(-180,-1))).isoformat(),
        "machinist_certificate": f"М-{random.randint(100000,999999)}",
        "machinist_certificate_type": random.choice(["тракторист-машинист","водитель погрузчика","оператор крана"]),
        "machinist_certificate_expiry": (today + timedelta(days=random.randint(-90,1095))).isoformat(),
        "medical_cert_expiry": (today + timedelta(days=random.randint(-30,365))).isoformat(),
        "safety_training_expiry": (today + timedelta(days=random.randint(-45,545))).isoformat(),
    }
    try:
        resp = requests.put(f"{BASE}/drivers/{cid}/profile", json=payload, headers=h)
        if resp.status_code in (200, 201):
            updated += 1
        else:
            errors += 1
    except Exception:
        errors += 1
    if updated % 20 == 0 and updated > 0:
        time.sleep(0.5)

print(f"Updated: {updated}, Errors: {errors}")
