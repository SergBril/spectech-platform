"""Тест многостраничности: УПД и ТОРГ-12 с 60 позициями."""

import sys
from datetime import date, datetime
from types import SimpleNamespace

sys.path.insert(0, "/app")

from app.services.reportlab_pdf_generator import (
    generate_torg12_reportlab,
    generate_upd_reportlab,
)

BANK = {
    "bank_name": "ПАО Сбербанк",
    "account": "40702810000000012345",
    "bik": "044525225",
    "correspondent_account": "30101810400000000225",
}
company = SimpleNamespace(
    name='ООО "СпецТехника Про"',
    inn="7700000000",
    kpp="770001001",
    legal_address="123456, г. Москва, ул. Примерная, д. 1",
    bank_details=BANK,
    director_position="Генеральный директор",
)
client = SimpleNamespace(
    name="ООО ТестКлиент",
    inn="7707083893",
    kpp="770701001",
    legal_address="119048, г. Москва, ул. Усачёва, д. 35, стр. 1",
    bank_details=BANK,
)
req = SimpleNamespace(work_type=None)

items = [
    {
        "description": f"Аренда экскаватора JCB JS330, смена №{i} (работы по разработке грунта)",
        "unit": "шт",
        "quantity": 1.0,
        "unit_price": 10000.0,
        "subtotal": 10000.0,
        "vat_amount": 2200.0,
        "total": 12200.0,
    }
    for i in range(1, 61)
]

act = SimpleNamespace(
    document_number="TEST-MULTIPAGE",
    act_date=date(2026, 9, 27),
    request_id=999,
    created_at=datetime(2026, 9, 27),
    tax_system="osno",
    vat_rate=22.0,
    is_vat_included=False,
    total_amount=sum(i["total"] for i in items),
    comment=None,
)

for name, gen in [("UPD", generate_upd_reportlab), ("TORG", generate_torg12_reportlab)]:
    pdf = gen(act, company, client, req, items=items)
    path = f"/tmp/{name}-TEST-MULTIPAGE.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    print(f"{name}: {len(pdf)} bytes -> {path}")
print("OK")
