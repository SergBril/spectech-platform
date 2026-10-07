"""Проверка Invoice в базе."""
from app.core.db import SessionLocal
from app.models.finance import Invoice

db = SessionLocal()
invoices = db.query(Invoice).all()

print(f"Всего Invoice в базе: {len(invoices)}\n")

for inv in invoices:
    print(f"ID={inv.id}, Number={inv.document_number}, "
          f"Status={inv.status}, Total={inv.total}, Paid={inv.paid_amount}")

db.close()