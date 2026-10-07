"""Тест применения платежа к Invoice — исправленная версия."""
import httpx
from decimal import Decimal
import json

BASE = "http://127.0.0.1:8000"
timeout = httpx.Timeout(30.0, connect=10.0)

# 1. Авторизация
login_resp = httpx.post(f"{BASE}/api/v1/auth/login", json={
    "email": "admin@spectech.dev",
    "password": "admin123"
}, timeout=timeout)
print(f"Login: {login_resp.status_code}")

if login_resp.status_code != 200:
    print(f"❌ Login failed: {login_resp.text}")
    exit(1)

token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Получаем список Invoice напрямую из БД (надёжнее, чем через API)
from app.core.db import SessionLocal
from app.models.finance import Invoice, DocumentStatus

db = SessionLocal()
invoices = db.query(Invoice).filter(
    Invoice.status != DocumentStatus.paid
).limit(5).all()

print(f"\n📋 Найдено {len(invoices)} неоплаченных Invoice:")
for inv in invoices:
    print(f"   ID={inv.id}, {inv.document_number}, "
          f"Total={inv.total}, Paid={inv.paid_amount}, Status={inv.status.value}")

if not invoices:
    print("❌ Нет неоплаченных Invoice в базе")
    db.close()
    exit(1)

invoice = invoices[0]
print(f"\n🎯 Будем применять к Invoice: {invoice.document_number} (ID={invoice.id})")

db.close()

# 3. Получаем список непривязанных платежей
resp = httpx.get(f"{BASE}/api/v1/banking/payments/unmatched", headers=headers, timeout=timeout)
unmatched = resp.json()

if unmatched["total"] == 0:
    print("\n⚠️ Нет непривязанных платежей (все уже применены или нет выписки)")
    print("Загрузите выписку через test_bank_api.py и попробуйте снова")
    exit(0)

tx = unmatched["items"][0]
print(f"\n📥 Транзакция: {tx['bank_transaction_id']}")
print(f"   Сумма: {tx['amount']} ₽")
print(f"   Плательщик: {tx['counterparty_name']}")
print(f"   Назначение: {tx['purpose'][:100]}...")

# 4. Применяем платёж
print(f"\n⚡ Применяем платёж к Invoice...")
apply_resp = httpx.post(
    f"{BASE}/api/v1/banking/payments/apply",
    headers=headers,
    params={
        "transaction_id": tx["id"],
        "invoice_id": invoice.id,
    },
    timeout=timeout,
)

print(f"Apply status: {apply_resp.status_code}")
if apply_resp.status_code == 200:
    print("✅ Платёж применён успешно!")
    print(json.dumps(apply_resp.json(), indent=2, ensure_ascii=False))
    
    # Проверяем, что Invoice обновился
    db = SessionLocal()
    updated_invoice = db.get(Invoice, invoice.id)
    print(f"\n📊 Invoice после применения:")
    print(f"   Status: {updated_invoice.status.value}")
    print(f"   Paid: {updated_invoice.paid_amount} ₽")
    print(f"   Total: {updated_invoice.total} ₽")
    print(f"   Remaining: {updated_invoice.total - updated_invoice.paid_amount} ₽")
    db.close()
else:
    print(f"❌ Ошибка: {apply_resp.text}")