"""Скрипт создаёт правильные версии тестовых файлов."""

from pathlib import Path

TESTS_DIR = Path(__file__).parent.parent / "tests"

# === conftest.py ===
CONFTEST = '''from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models import *  # noqa: F401, F403
from app.models.dispatch import Request

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_test_request(db, client_id, category_id, company_id, **overrides):
    """Фабрика тестовых заявок с заполненными обязательными полями."""
    now = datetime.now(timezone.utc)
    defaults = {
        "client_id": client_id,
        "status": "completed",
        "request_type": "one_time",
        "vehicle_category_id": category_id,
        "work_type": "Тестовая работа",
        "object_address": "Москва",
        "planned_start": now,
        "planned_end": now + timedelta(hours=8),
        "shift_duration_hours": 8,
        "client_rate": Decimal("15000"),
        "rate_type": "per_shift",
        "estimated_amount": Decimal("15000"),
        "source_channel": "phone",
        "priority": "normal",
        "company_id": company_id,
    }
    defaults.update(overrides)
    return Request(**defaults)
'''

# === test_finance_service.py ===
FINANCE_SERVICE = """from datetime import date
from decimal import Decimal

from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import (
    Invoice, InvoiceItem, Act, Payout, Payment, DocumentStatus,
)
from app.services.finance_service import (
    generate_document_number,
    calculate_invoice_totals,
    register_payment,
    calculate_payout,
    get_finance_dashboard,
)
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request


def create_test_entities(db):
    init_system_data(db)

    company = Company(name="Тест", legal_name='ООО "Тест"', inn="7799999999")
    db.add(company); db.flush()

    client = Contractor(type="client", name="Клиент", inn="7788888888", company_id=company.id)
    owner = Contractor(type="owner", name="Собственник", company_id=company.id)
    db.add(client); db.add(owner); db.flush()

    category = Category(name="Кат", code="test", level=1, company_id=company.id)
    db.add(category); db.flush()

    vehicle = Vehicle(
        id_type="vin", id_value="TEST12345678901234",
        category_id=category.id, name="Техника", status="free", company_id=company.id,
    )
    db.add(vehicle); db.flush()

    request = make_test_request(db, client.id, category.id, company.id)
    db.add(request); db.flush()

    return {"company": company, "client": client, "owner": owner, "vehicle": vehicle, "request": request}


def test_generate_document_number_first(db):
    create_test_entities(db)
    num = generate_document_number(db, "INV")
    assert num.startswith("INV-") and num.endswith("-0001")


def test_generate_document_number_sequence(db):
    create_test_entities(db)
    num1 = generate_document_number(db, "INV")
    inv = Invoice(document_number=num1, request_id=1, client_id=1, company_id=1,
                  invoice_date=date(2026, 9, 1), status=DocumentStatus.draft)
    db.add(inv); db.commit()
    num2 = generate_document_number(db, "INV")
    assert num1 != num2 and num2.endswith("-0002")


def test_generate_document_number_different_prefixes(db):
    create_test_entities(db)
    assert generate_document_number(db, "INV").startswith("INV-")
    assert generate_document_number(db, "ACT").startswith("ACT-")
    assert generate_document_number(db, "PAY").startswith("PAY-")


def test_calculate_invoice_totals_no_vat(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="INV-1", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    i1 = InvoiceItem(invoice_id=inv.id, description="U1", quantity=Decimal("8"), unit="ч", unit_price=Decimal("2000"))
    i2 = InvoiceItem(invoice_id=inv.id, description="U2", quantity=Decimal("1"), unit="шт", unit_price=Decimal("3000"))
    db.add_all([i1, i2]); inv.items = [i1, i2]
    calculate_invoice_totals(inv)
    assert inv.subtotal == Decimal("19000")
    assert inv.vat_amount == Decimal("0")
    assert inv.total == Decimal("19000")


def test_calculate_invoice_totals_with_vat(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="INV-2", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                  vat_rate=Decimal("20"), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    item = InvoiceItem(invoice_id=inv.id, description="U", quantity=Decimal("1"), unit="шт", unit_price=Decimal("10000"))
    db.add(item); inv.items = [item]
    calculate_invoice_totals(inv)
    assert inv.subtotal == Decimal("10000")
    assert inv.vat_amount == Decimal("2000")
    assert inv.total == Decimal("12000")


def test_calculate_payout_basic():
    r = calculate_payout(Decimal("10000"), Decimal("15"))
    assert r["gross_amount"] == Decimal("10000")
    assert r["platform_commission"] == Decimal("1500")
    assert r["net_amount"] == Decimal("8500")


def test_calculate_payout_zero_commission():
    r = calculate_payout(Decimal("5000"), Decimal("0"))
    assert r["platform_commission"] == Decimal("0")
    assert r["net_amount"] == Decimal("5000")


def test_calculate_payout_fractional():
    r = calculate_payout(Decimal("1000"), Decimal("15"))
    assert r["platform_commission"] == Decimal("150.00")


def test_register_payment_updates_invoice(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="INV-P", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                  total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    pay = Payment(invoice_id=inv.id, amount=Decimal("5000"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(pay); db.flush()
    register_payment(db, pay)
    db.refresh(inv)
    assert inv.paid_amount == Decimal("5000")
    assert inv.status == DocumentStatus.partially_paid


def test_register_payment_full_paid(db):
    e = create_test_entities(db)
    inv = Invoice(document_number="INV-F", request_id=e["request"].id, client_id=e["client"].id,
                  company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                  total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    pay = Payment(invoice_id=inv.id, amount=Decimal("10000"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(pay); db.flush()
    register_payment(db, pay)
    db.refresh(inv)
    assert inv.paid_amount == Decimal("10000")
    assert inv.status == DocumentStatus.paid


def test_register_payment_updates_payout(db):
    e = create_test_entities(db)
    po = Payout(document_number="PAY-T", owner_id=e["owner"].id, vehicle_id=e["vehicle"].id,
                company_id=e["company"].id, gross_amount=Decimal("10000"),
                platform_commission=Decimal("1500"), net_amount=Decimal("8500"),
                commission_rate=Decimal("15"), payout_date=date(2026, 9, 1), status=DocumentStatus.sent)
    db.add(po); db.flush()
    pay = Payment(payout_id=po.id, amount=Decimal("8500"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(pay); db.flush()
    register_payment(db, pay)
    db.refresh(po)
    assert po.status == DocumentStatus.paid


def test_get_finance_dashboard_empty(db):
    e = create_test_entities(db)
    r = get_finance_dashboard(db, e["company"].id)
    assert r["total_revenue"] == Decimal("0")
    assert r["invoices_count"] == 0


def test_get_finance_dashboard_with_data(db):
    e = create_test_entities(db)
    db.add(Invoice(document_number="INV-D", request_id=e["request"].id, client_id=e["client"].id,
                   company_id=e["company"].id, invoice_date=date(2026, 9, 1),
                   total=Decimal("12000"), paid_amount=Decimal("5000"), status=DocumentStatus.partially_paid))
    db.add(Payout(document_number="PAY-D", owner_id=e["owner"].id, vehicle_id=e["vehicle"].id,
                  company_id=e["company"].id, gross_amount=Decimal("10000"),
                  platform_commission=Decimal("1500"), net_amount=Decimal("8500"),
                  commission_rate=Decimal("15"), payout_date=date(2026, 9, 1), status=DocumentStatus.draft))
    db.add(Act(document_number="ACT-D", request_id=e["request"].id, client_id=e["client"].id,
               company_id=e["company"].id, act_date=date(2026, 9, 1),
               total_amount=Decimal("12000"), status=DocumentStatus.draft))
    db.commit()
    r = get_finance_dashboard(db, e["company"].id)
    assert r["total_revenue"] == Decimal("12000")
    assert r["total_paid"] == Decimal("5000")
    assert r["total_commission_earned"] == Decimal("1500")
    assert r["invoices_count"] == 1
    assert r["acts_count"] == 1
    assert r["payouts_count"] == 1
"""

# === test_finance_api.py ===
FINANCE_API = """from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.services.auth_service import hash_password
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request


def setup_finance_test_data(db):
    init_system_data(db)
    company = Company(name="API Co", legal_name='ООО "API"', inn="7712345678")
    db.add(company); db.flush()

    user = User(email="fin@test.com", full_name="T", password_hash=hash_password("x"),
                company_id=company.id, is_superuser=True)
    db.add(user); db.flush()

    client = Contractor(type="client", name="C", inn="7798765432", company_id=company.id)
    owner = Contractor(type="owner", name="O", company_id=company.id)
    db.add(client); db.add(owner); db.flush()

    category = Category(name="Cat", code="api", level=1, company_id=company.id)
    db.add(category); db.flush()

    vehicle = Vehicle(id_type="vin", id_value="APITEST12345678901", category_id=category.id,
                      name="V", status="free", company_id=company.id)
    db.add(vehicle); db.flush()

    request = make_test_request(db, client.id, category.id, company.id)
    db.add(request); db.commit()

    return {"user": user, "company": company, "client": client, "owner": owner, "vehicle": vehicle, "request": request}


def _setup(client, db):
    from app.api.deps import get_current_user
    from app.main import app
    data = setup_finance_test_data(db)
    app.dependency_overrides[get_current_user] = lambda: data["user"]
    return data


def _clear():
    from app.main import app
    app.dependency_overrides.clear()


def test_create_invoice(client, db):
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "invoice_date": "2026-09-01", "due_date": "2026-09-15", "vat_rate": 20.0,
            "items": [{"description": "E", "quantity": 8, "unit": "ч", "unit_price": 2000}],
        })
        assert r.status_code == 201
        b = r.json()
        assert b["document_number"].startswith("INV-")
        assert b["subtotal"] == "16000.00"
        assert b["total"] == "19200.00"
    finally:
        _clear()


def test_list_invoices(client, db):
    d = _setup(client, db)
    try:
        client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "шт", "unit_price": 1000}],
        })
        r = client.get("/api/v1/invoices")
        assert r.status_code == 200
        assert len(r.json()) >= 1
    finally:
        _clear()


def test_send_invoice(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "шт", "unit_price": 1000}],
        })
        iid = cr.json()["id"]
        sr = client.post(f"/api/v1/invoices/{iid}/send")
        assert sr.status_code == 200 and sr.json()["status"] == "sent"
        assert client.post(f"/api/v1/invoices/{iid}/send").status_code == 409
    finally:
        _clear()


def test_download_invoice_pdf(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "invoice_date": "2026-09-01",
            "items": [{"description": "P", "quantity": 1, "unit": "шт", "unit_price": 500}],
        })
        r = client.get(f"/api/v1/invoices/{cr.json()['id']}/pdf")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"
    finally:
        _clear()


def test_create_act(client, db):
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/acts", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "act_date": "2026-09-01", "total_amount": 15000,
        })
        assert r.status_code == 201
        assert r.json()["document_number"].startswith("ACT-")
    finally:
        _clear()


def test_sign_act_both_parties(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/acts", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "act_date": "2026-09-01", "total_amount": 10000,
        })
        aid = cr.json()["id"]
        s1 = client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "client"})
        assert s1.status_code == 200
        assert s1.json()["signed_by_client_at"] is not None
        s2 = client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "executor"})
        assert s2.status_code == 200
        assert s2.json()["status"] == "paid"
        assert client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "client"}).status_code == 409
    finally:
        _clear()


def test_create_payout_auto_commission(client, db):
    d = _setup(client, db)
    try:
        r = client.post("/api/v1/payouts", json={
            "owner_id": d["owner"].id, "vehicle_id": d["vehicle"].id,
            "request_id": d["request"].id,
            "gross_amount": 20000, "commission_rate": 15, "payout_date": "2026-09-01",
        })
        assert r.status_code == 201
        b = r.json()
        assert b["gross_amount"] == "20000.00"
        assert b["platform_commission"] == "3000.00"
        assert b["net_amount"] == "17000.00"
        assert b["commission_rate"] == "15.00"
    finally:
        _clear()


def test_approve_payout(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/payouts", json={
            "owner_id": d["owner"].id, "vehicle_id": d["vehicle"].id,
            "gross_amount": 10000, "commission_rate": 10, "payout_date": "2026-09-01",
        })
        r = client.post(f"/api/v1/payouts/{cr.json()['id']}/approve")
        assert r.status_code == 200
        assert r.json()["status"] == "sent"
    finally:
        _clear()


def test_payment_updates_invoice(client, db):
    d = _setup(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "шт", "unit_price": 10000}],
        })
        iid = cr.json()["id"]
        pr = client.post("/api/v1/payments", json={
            "invoice_id": iid, "amount": 5000, "method": "bank_transfer", "payment_date": "2026-09-05",
        })
        assert pr.status_code == 201
        gr = client.get(f"/api/v1/invoices/{iid}")
        assert gr.json()["paid_amount"] == "5000.00"
        assert gr.json()["status"] == "partially_paid"
    finally:
        _clear()


def test_finance_dashboard(client, db):
    d = _setup(client, db)
    try:
        r = client.get("/api/v1/payments/dashboard")
        assert r.status_code == 200
        b = r.json()
        for k in ("total_revenue", "total_paid", "total_outstanding", "total_commission_earned", "invoices_count"):
            assert k in b
    finally:
        _clear()


def test_full_finance_workflow(client, db):
    d = _setup(client, db)
    try:
        inv = client.post("/api/v1/invoices", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "invoice_date": "2026-09-01", "vat_rate": 20,
            "items": [{"description": "W", "quantity": 8, "unit": "ч", "unit_price": 1000}],
        }).json()
        client.post(f"/api/v1/invoices/{inv['id']}/send")
        client.post("/api/v1/payments", json={
            "invoice_id": inv["id"], "amount": 9600, "method": "bank_transfer", "payment_date": "2026-09-10",
        })
        act = client.post("/api/v1/acts", json={
            "request_id": d["request"].id, "client_id": d["client"].id,
            "act_date": "2026-09-10", "total_amount": 9600,
        }).json()
        client.post(f"/api/v1/acts/{act['id']}/sign", json={"signed_by": "client"})
        client.post(f"/api/v1/acts/{act['id']}/sign", json={"signed_by": "executor"})
        po = client.post("/api/v1/payouts", json={
            "owner_id": d["owner"].id, "vehicle_id": d["vehicle"].id, "request_id": d["request"].id,
            "gross_amount": 8000, "commission_rate": 15, "payout_date": "2026-09-10",
        }).json()
        assert po["net_amount"] == "6800.00"
        assert po["platform_commission"] == "1200.00"
        pdf = client.get(f"/api/v1/invoices/{inv['id']}/pdf")
        assert pdf.status_code == 200
        dash = client.get("/api/v1/payments/dashboard").json()
        assert float(dash["total_revenue"]) >= 9600
    finally:
        _clear()
"""

if __name__ == "__main__":
    (TESTS_DIR / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    (TESTS_DIR / "test_finance_service.py").write_text(
        FINANCE_SERVICE, encoding="utf-8"
    )
    (TESTS_DIR / "test_finance_api.py").write_text(FINANCE_API, encoding="utf-8")
    print("✅ Все 3 файла обновлены")
