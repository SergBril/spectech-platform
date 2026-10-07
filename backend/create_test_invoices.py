"""Создание тестовых Invoice для проверки авто-матчинга."""
from datetime import date, timedelta
from decimal import Decimal
from app.core.db import SessionLocal
from app.models.finance import Invoice, DocumentStatus
from app.services.finance_service import generate_document_number

db = SessionLocal()

# Создаём Invoice с номерами из выписки
test_invoices = [
    {"number": "347", "total": Decimal("218738.40"), "client_id": 1},
    {"number": "376", "total": Decimal("70700.00"), "client_id": 1},
    {"number": "372", "total": Decimal("71500.00"), "client_id": 1},
    {"number": "387", "total": Decimal("37820.00"), "client_id": 1},
    {"number": "384", "total": Decimal("76860.00"), "client_id": 1},
    {"number": "386", "total": Decimal("30500.00"), "client_id": 1},
    {"number": "388", "total": Decimal("6405.00"), "client_id": 1},
    {"number": "385", "total": Decimal("4880.00"), "client_id": 1},
    {"number": "389", "total": Decimal("34160.00"), "client_id": 1},
    {"number": "391", "total": Decimal("16000.00"), "client_id": 1},
    {"number": "390", "total": Decimal("65880.00"), "client_id": 1},
    {"number": "399", "total": Decimal("143960.00"), "client_id": 1},
    {"number": "397", "total": Decimal("26840.00"), "client_id": 1},
    {"number": "401", "total": Decimal("48800.00"), "client_id": 1},
    {"number": "402", "total": Decimal("36600.00"), "client_id": 1},
    {"number": "404", "total": Decimal("25925.00"), "client_id": 1},
]

for inv_data in test_invoices:
    invoice = Invoice(
        document_number=f"INV-2026-{inv_data['number']}",
        client_id=inv_data["client_id"],
        company_id=1,
        subtotal=inv_data["total"] / Decimal("1.22"),
        vat_amount=inv_data["total"] - inv_data["total"] / Decimal("1.22"),
        vat_rate=Decimal("22.00"),
        total=inv_data["total"],
        paid_amount=Decimal("0.00"),
        invoice_date=date.today() - timedelta(days=30),
        due_date=date.today() + timedelta(days=30),
        status=DocumentStatus.sent,
    )
    db.add(invoice)

db.commit()
print(f"✅ Создано {len(test_invoices)} тестовых Invoice")

# Проверяем
invoices = db.query(Invoice).all()
print(f"\nВсего Invoice в базе: {len(invoices)}")
for inv in invoices[:5]:
    print(f"  {inv.document_number} — {inv.total} ₽")

db.close()