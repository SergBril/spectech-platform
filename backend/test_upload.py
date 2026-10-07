"""Тест загрузки банковской выписки."""
import httpx
from pathlib import Path

BASE = "http://localhost:8000"

# 1. Авторизация
login_resp = httpx.post(f"{BASE}/api/v1/auth/login", json={
    "email": "admin@spectech.dev",
    "password": "admin123"  # замените на ваш пароль
})
print("Login:", login_resp.status_code)

if login_resp.status_code != 200:
    print("Login failed:", login_resp.text)
    exit(1)

token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Загрузка выписки
file_path = Path("tests/fixtures/bank_statement_sample.txt")
with open(file_path, "rb") as f:
    files = {"file": (file_path.name, f, "text/plain")}
    resp = httpx.post(
        f"{BASE}/api/v1/finance/bank-statements",
        headers=headers,
        files=files,
        timeout=30.0,
    )

print(f"\nUpload: {resp.status_code}")
print(resp.json() if resp.status_code == 201 else resp.text)

# 3. Получение списка выписок
if resp.status_code == 201:
    list_resp = httpx.get(
        f"{BASE}/api/v1/finance/bank-statements",
        headers=headers,
    )
    print(f"\nList: {list_resp.status_code}")
    import json
    print(json.dumps(list_resp.json(), indent=2, ensure_ascii=False)[:2000])
    
    # 4. Список непривязанных платежей
    unmatched_resp = httpx.get(
        f"{BASE}/api/v1/finance/payments/unmatched",
        headers=headers,
    )
    print(f"\nUnmatched: {unmatched_resp.status_code}")
    print(json.dumps(unmatched_resp.json(), indent=2, ensure_ascii=False)[:2000])