"""Быстрый тест API банковских выписок."""
import httpx

BASE = "http://127.0.0.1:8000" 

# 1. Авторизация
login_resp = httpx.post(f"{BASE}/api/v1/auth/login", json={
    "email": "admin@spectech.dev",
    "password": "admin123"
})
print("Login:", login_resp.status_code)

if login_resp.status_code != 200:
    print("Login failed:", login_resp.text)
    exit(1)

token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Проверяем маршруты с НОВЫМ префиксом /banking
test_endpoints = [
    ("GET", f"{BASE}/api/v1/banking/bank-statements"),
    ("GET", f"{BASE}/api/v1/banking/payments/unmatched"),
]

for method, url in test_endpoints:
    resp = httpx.request(method, url, headers=headers)
    print(f"\n{method} {url.replace(BASE, '')}")
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 404:
        print(f"  ❌ Not Found — маршрут не зарегистрирован")
    elif resp.status_code == 200:
        print(f"  ✅ Работает!")
        import json
        print(f"  Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)[:500]}")
    else:
        print(f"  ⚠️ Status {resp.status_code}: {resp.text[:200]}")

# 3. Загрузка выписки
from pathlib import Path
file_path = Path("tests/fixtures/bank_statement_sample.txt")

if file_path.exists():
    print(f"\n📤 Uploading {file_path.name}...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "text/plain")}
        resp = httpx.post(
            f"{BASE}/api/v1/banking/bank-statements",  # ← НОВЫЙ ПРЕФИКС
            headers=headers,
            files=files,
            timeout=30.0,
        )
    
    print(f"Upload: {resp.status_code}")
    if resp.status_code == 201:
        import json
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    else:
        print(resp.text[:1000])
else:
    print(f"\n⚠️ File not found: {file_path}")