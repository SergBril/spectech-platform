"""Seed script: creates test data for drivers, invoices, maintenance, fuel."""
import requests
import random
from datetime import datetime, timedelta, date

BASE = "http://127.0.0.1:8000/api/v1"

# Auth
r = requests.post(f"{BASE}/auth/login", json={"email": "admin@spectech.dev", "password": "admin123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Get current user company_id
me = requests.get(f"{BASE}/me", headers=h).json()
user_company_id = me.get("company_id", 4)
print(f"User company_id: {user_company_id}")

# Get existing data
vehicles = requests.get(f"{BASE}/vehicles?limit=20", headers=h).json()
v_all = vehicles if isinstance(vehicles, list) else vehicles.get("items", [])
# Filter vehicles by user's company
v_list = [v for v in v_all if v.get("company_id") == user_company_id]
print(f"Vehicles (all): {len(v_all)}, (own company): {len(v_list)}")

contractors = requests.get(f"{BASE}/contractors?limit=20", headers=h).json()
c_list = contractors if isinstance(contractors, list) else contractors.get("items", [])
c_ids = [c["id"] for c in c_list]

req_data = requests.get(f"{BASE}/requests?limit=50", headers=h).json()
req_list = req_data if isinstance(req_data, list) else req_data.get("items", [])
req_ids = [r["id"] for r in req_list]

print(f"Contractors: {len(c_ids)}, Requests: {len(req_ids)}")

created = {"drivers": 0, "invoices": 0, "maintenance": 0, "fuel": 0}
errors = {"drivers": 0, "invoices": 0, "maintenance": 0, "fuel": 0}


# =============================================
# 1. DRIVERS (20 штук)
# =============================================
print("\n=== Creating Drivers ===")
driver_names = [
    "Алексеев Алексей Петрович", "Борисов Борис Иванович", "Волков Виктор Сергеевич",
    "Григорьев Григорий Андреевич", "Дмитриев Дмитрий Николаевич", "Егоров Егор Владимирович",
    "Жуков Максим Жукович", "Зайцев Захар Павлович", "Козлов Константин Олегович",
    "Лебедев Леонид Артёмович", "Михайлов Михаил Дмитриевич", "Новиков Николай Фёдорович",
    "Орлов Олег Геннадьевич", "Петров Пётр Алексеевич", "Романов Роман Юрьевич",
    "Семёнов Сергей Викторович", "Тихонов Тимур Рустамович", "Ульянов Ульян Борисович",
    "Фёдоров Фёдор Михайлович", "Харитонов Харитон Ильич",
]

phones_used = set()
for name in driver_names:
    phone = f"+79{random.randint(10,99)}{random.randint(1000000,9999999)}"
    while phone in phones_used:
        phone = f"+79{random.randint(10,99)}{random.randint(1000000,9999999)}"
    phones_used.add(phone)

    payload = {"full_name": name, "phone": phone, "contractor_id": random.choice(c_ids)}
    try:
        resp = requests.post(f"{BASE}/drivers", json=payload, headers=h)
        if resp.status_code in (200, 201):
            created["drivers"] += 1
        else:
            errors["drivers"] += 1
    except Exception:
        errors["drivers"] += 1

dr = requests.get(f"{BASE}/drivers?limit=50", headers=h).json()
d_list = dr.get("items", []) if isinstance(dr, dict) else dr
driver_contractor_ids = list({d["contractor_id"] for d in d_list})
print(f"  Created: {created['drivers']}, Errors: {errors['drivers']}")


# =============================================
# 2. INVOICES (15 штук)
# =============================================
print("\n=== Creating Invoices ===")
statuses_inv = ["draft", "sent", "paid", "overdue", "cancelled"]

for i in range(15):
    inv_date = date.today() - timedelta(days=random.randint(0, 60))
    due = inv_date + timedelta(days=30)
    subtotal = round(random.uniform(10000, 500000), 2)
    vat_rate = random.choice([0, 10, 20])
    vat_amount = round(subtotal * vat_rate / 100, 2)
    total = round(subtotal + vat_amount, 2)

    rid = random.choice(req_ids) if req_ids else None
    if not rid:
        break

    payload = {
        "document_number": f"INV-{datetime.now().year}-{i+1:04d}",
        "request_id": rid,
        "client_id": random.choice(c_ids),
        "company_id": user_company_id,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "vat_rate": vat_rate,
        "total": total,
        "paid_amount": total if random.random() > 0.4 else round(random.uniform(0, total), 2),
        "tax_system": random.choice(["usn", "osno"]),
        "is_vat_included": vat_rate > 0,
        "invoice_date": inv_date.isoformat(),
        "due_date": due.isoformat(),
        "status": random.choice(statuses_inv),
        "comment": f"Счёт за услуги спецтехники #{i+1}",
    }

    try:
        resp = requests.post(f"{BASE}/invoices", json=payload, headers=h)
        if resp.status_code in (200, 201):
            created["invoices"] += 1
        else:
            errors["invoices"] += 1
            if errors["invoices"] <= 2:
                print(f"  Invoice error: {resp.status_code} {resp.text[:150]}")
    except Exception:
        errors["invoices"] += 1

print(f"  Created: {created['invoices']}, Errors: {errors['invoices']}")


# =============================================
# 3. MAINTENANCE ORDERS (10 штук) — only own vehicles
# =============================================
print("\n=== Creating Maintenance Orders ===")
order_types = ["scheduled", "repair", "diagnostic", "inspection"]
priorities_m = ["low", "medium", "high", "critical"]
statuses_m = ["planned", "in_progress", "completed", "cancelled"]
titles = [
    "Замена масла и фильтров", "Ремонт гидравлики", "Диагностика двигателя",
    "ТО-2 плановое", "Замена тормозных колодок", "Ремонт ходовой части",
    "Проверка электрооборудования", "Замена ремней привода", "Смазка узлов и агрегатов",
    "Капитальный ремонт КПП",
]

for i in range(10):
    vehicle = random.choice(v_list)
    vid = vehicle["id"]
    eng_hours = float(vehicle.get("engine_hours", 100))
    parts_cost = round(random.uniform(1000, 50000), 2)
    labor_cost = round(random.uniform(2000, 30000), 2)

    payload = {
        "vehicle_id": vid,
        "company_id": user_company_id,
        "order_type": random.choice(order_types),
        "priority": random.choice(priorities_m),
        "title": titles[i % len(titles)],
        "description": f"Наряд-заказ на ТО техники #{i+1}",
        "planned_hours": round(random.uniform(1, 16), 1),
        "parts_cost": parts_cost,
        "labor_cost": labor_cost,
        "total_cost": round(parts_cost + labor_cost, 2),
        "engine_hours_at_start": eng_hours,
        "created_by_id": 1,
    }

    status = random.choice(statuses_m)
    if status == "completed":
        payload["actual_hours"] = round(random.uniform(1, 16), 1)
        payload["engine_hours_at_completion"] = eng_hours + random.uniform(5, 50)

    try:
        resp = requests.post(f"{BASE}/maintenance/orders", json=payload, headers=h)
        if resp.status_code in (200, 201):
            created["maintenance"] += 1
            oid = resp.json().get("id")
            if oid and status != "planned":
                requests.patch(f"{BASE}/maintenance/orders/{oid}", json={"status": status}, headers=h)
        else:
            errors["maintenance"] += 1
            if errors["maintenance"] <= 2:
                print(f"  Maint error: {resp.status_code} {resp.text[:150]}")
    except Exception:
        errors["maintenance"] += 1

print(f"  Created: {created['maintenance']}, Errors: {errors['maintenance']}")


# =============================================
# 4. FUEL TRANSACTIONS (30 штук) — only own vehicles
# =============================================
print("\n=== Creating Fuel Transactions ===")
for i in range(30):
    vehicle = random.choice(v_list)
    vid = vehicle["id"]
    vol = round(random.uniform(10, 200), 1)
    price = round(random.uniform(45, 65), 2)
    occurred = datetime.now() - timedelta(days=random.randint(0, 90), hours=random.randint(0, 23))

    payload = {
        "vehicle_id": vid,
        "transaction_type": random.choice(["refuel", "consumption"]),
        "volume": vol,
        "price_per_liter": price,
        "total_cost": round(vol * price, 2),
        "fuel_level_before": round(random.uniform(10, 80), 1),
        "fuel_level_after": round(random.uniform(20, 95), 1),
        "odometer": round(random.uniform(10000, 200000), 0),
        "detected_automatically": False,
        "company_id": user_company_id,
        "occurred_at": occurred.isoformat(),
        "comment": f"Заправка #{i+1}",
    }
    if driver_contractor_ids and random.random() > 0.3:
        payload["driver_id"] = random.choice(driver_contractor_ids)

    try:
        resp = requests.post(f"{BASE}/telematics/fuel", json=payload, headers=h)
        if resp.status_code in (200, 201):
            created["fuel"] += 1
        else:
            errors["fuel"] += 1
            if errors["fuel"] <= 2:
                print(f"  Fuel error: {resp.status_code} {resp.text[:150]}")
    except Exception:
        errors["fuel"] += 1

print(f"  Created: {created['fuel']}, Errors: {errors['fuel']}")


# =============================================
# SUMMARY
# =============================================
print("\n" + "=" * 50)
print("SEED COMPLETE")
print("=" * 50)
for entity in created:
    icon = "OK" if errors[entity] == 0 else "WARN"
    print(f"  [{icon}] {entity:15s}: {created[entity]:3d} created, {errors[entity]:3d} errors")
print("=" * 50)
