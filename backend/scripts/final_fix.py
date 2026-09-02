"""Финальное исправление тестов: Request обязательные поля."""
from pathlib import Path

TESTS = Path(__file__).parent.parent / "tests"

CONFTEST = '''from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.db import Base, get_db
from app.main import app
from app.models import *
from app.models.dispatch import Request

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override():
        try: yield db
        finally: pass
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def make_test_request(db, client_id, category_id, company_id, **kw):
    now = datetime.now(timezone.utc)
    d = dict(
        client_id=client_id, status="completed", request_type="one_time",
        vehicle_category_id=category_id, work_type="T", object_address="M",
        planned_start=now, planned_end=now + timedelta(hours=8),
        shift_duration_hours=8, client_rate=Decimal("15000"),
        rate_type="per_shift", estimated_amount=Decimal("15000"),
        source_channel="phone", priority="normal", company_id=company_id,
    )
    d.update(kw)
    return Request(**d)
'''

(TESTS / "conftest.py").write_text(CONFTEST, encoding="utf-8")
print("OK conftest.py")

FIN_SVC = '''from datetime import date
from decimal import Decimal
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Invoice, InvoiceItem, Act, Payout, Payment, DocumentStatus
from app.services.finance_service import (
    generate_document_number, calculate_invoice_totals, register_payment,
    calculate_payout, get_finance_dashboard,
)
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request

def e(db):
    init_system_data(db)
    co = Company(name="T", legal_name='OOO "T"', inn="7799999999")
    db.add(co); db.flush()
    cl = Contractor(type="client", name="C", inn="7788888888", company_id=co.id)
    ow = Contractor(type="owner", name="O", company_id=co.id)
    db.add(cl); db.add(ow); db.flush()
    cat = Category(name="K", code="t", level=1, company_id=co.id)
    db.add(cat); db.flush()
    v = Vehicle(id_type="vin", id_value="X" * 17, category_id=cat.id, name="V", status="free", company_id=co.id)
    db.add(v); db.flush()
    r = make_test_request(db, cl.id, cat.id, co.id)
    db.add(r); db.flush()
    return {"co": co, "cl": cl, "ow": ow, "v": v, "r": r}

def test_generate_document_number_first(db):
    e(db)
    n = generate_document_number(db, "INV")
    assert n.startswith("INV-") and n.endswith("-0001")

def test_generate_document_number_sequence(db):
    e(db)
    n1 = generate_document_number(db, "INV")
    db.add(Invoice(document_number=n1, request_id=1, client_id=1, company_id=1,
                   invoice_date=date(2026, 9, 1), status=DocumentStatus.draft))
    db.commit()
    n2 = generate_document_number(db, "INV")
    assert n2.endswith("-0002")

def test_generate_document_number_different_prefixes(db):
    e(db)
    assert generate_document_number(db, "INV").startswith("INV-")
    assert generate_document_number(db, "ACT").startswith("ACT-")
    assert generate_document_number(db, "PAY").startswith("PAY-")

def test_calculate_invoice_totals_no_vat(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id,
                  company_id=d["co"].id, invoice_date=date(2026, 9, 1), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    i1 = InvoiceItem(invoice_id=inv.id, description="U1", quantity=Decimal("8"), unit="h", unit_price=Decimal("2000"))
    i2 = InvoiceItem(invoice_id=inv.id, description="U2", quantity=Decimal("1"), unit="p", unit_price=Decimal("3000"))
    db.add_all([i1, i2]); inv.items = [i1, i2]
    calculate_invoice_totals(inv)
    assert inv.subtotal == Decimal("19000") and inv.total == Decimal("19000")

def test_calculate_invoice_totals_with_vat(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id,
                  company_id=d["co"].id, invoice_date=date(2026, 9, 1),
                  vat_rate=Decimal("20"), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    it = InvoiceItem(invoice_id=inv.id, description="U", quantity=Decimal("1"), unit="p", unit_price=Decimal("10000"))
    db.add(it); inv.items = [it]
    calculate_invoice_totals(inv)
    assert inv.vat_amount == Decimal("2000") and inv.total == Decimal("12000")

def test_calculate_payout_basic():
    r = calculate_payout(Decimal("10000"), Decimal("15"))
    assert r["platform_commission"] == Decimal("1500") and r["net_amount"] == Decimal("8500")

def test_calculate_payout_zero_commission():
    r = calculate_payout(Decimal("5000"), Decimal("0"))
    assert r["platform_commission"] == Decimal("0")

def test_calculate_payout_fractional():
    r = calculate_payout(Decimal("1000"), Decimal("15"))
    assert r["platform_commission"] == Decimal("150.00")

def test_register_payment_updates_invoice(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id,
                  company_id=d["co"].id, invoice_date=date(2026, 9, 1),
                  total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    p = Payment(invoice_id=inv.id, amount=Decimal("5000"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(p); db.flush()
    register_payment(db, p)
    db.refresh(inv)
    assert inv.paid_amount == Decimal("5000") and inv.status == DocumentStatus.partially_paid

def test_register_payment_full_paid(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id,
                  company_id=d["co"].id, invoice_date=date(2026, 9, 1),
                  total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    p = Payment(invoice_id=inv.id, amount=Decimal("10000"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(p); db.flush()
    register_payment(db, p); db.refresh(inv)
    assert inv.status == DocumentStatus.paid

def test_register_payment_updates_payout(db):
    d = e(db)
    po = Payout(document_number="X", owner_id=d["ow"].id, vehicle_id=d["v"].id,
                company_id=d["co"].id, gross_amount=Decimal("10000"),
                platform_commission=Decimal("1500"), net_amount=Decimal("8500"),
                commission_rate=Decimal("15"), payout_date=date(2026, 9, 1), status=DocumentStatus.sent)
    db.add(po); db.flush()
    p = Payment(payout_id=po.id, amount=Decimal("8500"), method="bank_transfer", payment_date=date(2026, 9, 5))
    db.add(p); db.flush()
    register_payment(db, p); db.refresh(po)
    assert po.status == DocumentStatus.paid

def test_get_finance_dashboard_empty(db):
    d = e(db)
    r = get_finance_dashboard(db, d["co"].id)
    assert r["total_revenue"] == Decimal("0")

def test_get_finance_dashboard_with_data(db):
    d = e(db)
    db.add(Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id,
                   company_id=d["co"].id, invoice_date=date(2026, 9, 1),
                   total=Decimal("12000"), paid_amount=Decimal("5000"), status=DocumentStatus.partially_paid))
    db.add(Payout(document_number="Y", owner_id=d["ow"].id, vehicle_id=d["v"].id,
                  company_id=d["co"].id, gross_amount=Decimal("10000"),
                  platform_commission=Decimal("1500"), net_amount=Decimal("8500"),
                  commission_rate=Decimal("15"), payout_date=date(2026, 9, 1), status=DocumentStatus.draft))
    db.add(Act(document_number="Z", request_id=d["r"].id, client_id=d["cl"].id,
               company_id=d["co"].id, act_date=date(2026, 9, 1),
               total_amount=Decimal("12000"), status=DocumentStatus.draft))
    db.commit()
    r = get_finance_dashboard(db, d["co"].id)
    assert r["total_revenue"] == Decimal("12000")
    assert r["total_paid"] == Decimal("5000")
    assert r["total_commission_earned"] == Decimal("1500")
'''

(TESTS / "test_finance_service.py").write_text(FIN_SVC, encoding="utf-8")
print("OK test_finance_service.py")

FIN_API = '''from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.services.auth_service import hash_password
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request

def setup(db):
    init_system_data(db)
    co = Company(name="A", legal_name='OOO "A"', inn="7712345678")
    db.add(co); db.flush()
    u = User(email="f@t.com", full_name="T", password_hash=hash_password("x"),
             company_id=co.id, is_superuser=True)
    db.add(u); db.flush()
    cl = Contractor(type="client", name="C", inn="7798765432", company_id=co.id)
    ow = Contractor(type="owner", name="O", company_id=co.id)
    db.add(cl); db.add(ow); db.flush()
    cat = Category(name="K", code="a", level=1, company_id=co.id)
    db.add(cat); db.flush()
    v = Vehicle(id_type="vin", id_value="Y" * 17, category_id=cat.id,
                name="V", status="free", company_id=co.id)
    db.add(v); db.flush()
    r = make_test_request(db, cl.id, cat.id, co.id)
    db.add(r); db.commit()
    return {"u": u, "co": co, "cl": cl, "ow": ow, "v": v, "r": r}

def S(c, db):
    from app.api.deps import get_current_user
    from app.main import app
    d = setup(db)
    app.dependency_overrides[get_current_user] = lambda: d["u"]
    return d

def C():
    from app.main import app
    app.dependency_overrides.clear()

def test_create_invoice(client, db):
    d = S(client, db)
    try:
        r = client.post("/api/v1/invoices", json={
            "request_id": d["r"].id, "client_id": d["cl"].id,
            "invoice_date": "2026-09-01", "vat_rate": 20.0,
            "items": [{"description": "E", "quantity": 8, "unit": "h", "unit_price": 2000}],
        })
        assert r.status_code == 201
        assert r.json()["subtotal"] == "16000.00"
    finally: C()

def test_list_invoices(client, db):
    d = S(client, db)
    try:
        client.post("/api/v1/invoices", json={
            "request_id": d["r"].id, "client_id": d["cl"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "p", "unit_price": 1000}],
        })
        r = client.get("/api/v1/invoices")
        assert r.status_code == 200 and len(r.json()) >= 1
    finally: C()

def test_send_invoice(client, db):
    d = S(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["r"].id, "client_id": d["cl"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "p", "unit_price": 1000}],
        })
        iid = cr.json()["id"]
        sr = client.post(f"/api/v1/invoices/{iid}/send")
        assert sr.status_code == 200 and sr.json()["status"] == "sent"
        assert client.post(f"/api/v1/invoices/{iid}/send").status_code == 409
    finally: C()

def test_download_invoice_pdf(client, db):
    d = S(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["r"].id, "client_id": d["cl"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "P", "quantity": 1, "unit": "p", "unit_price": 500}],
        })
        r = client.get(f"/api/v1/invoices/{cr.json()['id']}/pdf")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
    finally: C()

def test_create_act(client, db):
    d = S(client, db)
    try:
        r = client.post("/api/v1/acts", json={
            "request_id": d["r"].id, "client_id": d["cl"].id,
            "act_date": "2026-09-01", "total_amount": 15000,
        })
        assert r.status_code == 201
    finally: C()

def test_sign_act_both_parties(client, db):
    d = S(client, db)
    try:
        cr = client.post("/api/v1/acts", json={
            "request_id": d["r"].id, "client_id": d["cl"].id,
            "act_date": "2026-09-01", "total_amount": 10000,
        })
        aid = cr.json()["id"]
        s1 = client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "client"})
        assert s1.status_code == 200
        s2 = client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "executor"})
        assert s2.status_code == 200 and s2.json()["status"] == "paid"
        assert client.post(f"/api/v1/acts/{aid}/sign", json={"signed_by": "client"}).status_code == 409
    finally: C()

def test_create_payout_auto_commission(client, db):
    d = S(client, db)
    try:
        r = client.post("/api/v1/payouts", json={
            "owner_id": d["ow"].id, "vehicle_id": d["v"].id, "request_id": d["r"].id,
            "gross_amount": 20000, "commission_rate": 15, "payout_date": "2026-09-01",
        })
        assert r.status_code == 201
        b = r.json()
        assert b["gross_amount"] == "20000.00"
        assert b["platform_commission"] == "3000.00"
        assert b["net_amount"] == "17000.00"
    finally: C()

def test_approve_payout(client, db):
    d = S(client, db)
    try:
        cr = client.post("/api/v1/payouts", json={
            "owner_id": d["ow"].id, "vehicle_id": d["v"].id,
            "gross_amount": 10000, "commission_rate": 10, "payout_date": "2026-09-01",
        })
        r = client.post(f"/api/v1/payouts/{cr.json()['id']}/approve")
        assert r.status_code == 200 and r.json()["status"] == "sent"
    finally: C()

def test_payment_updates_invoice(client, db):
    d = S(client, db)
    try:
        cr = client.post("/api/v1/invoices", json={
            "request_id": d["r"].id, "client_id": d["cl"].id, "invoice_date": "2026-09-01",
            "items": [{"description": "U", "quantity": 1, "unit": "p", "unit_price": 10000}],
        })
        iid = cr.json()["id"]
        pr = client.post("/api/v1/payments", json={
            "invoice_id": iid, "amount": 5000, "method": "bank_transfer", "payment_date": "2026-09-05",
        })
        assert pr.status_code == 201
        gr = client.get(f"/api/v1/invoices/{iid}")
        assert gr.json()["paid_amount"] == "5000.00"
    finally: C()

def test_finance_dashboard(client, db):
    d = S(client, db)
    try:
        r = client.get("/api/v1/payments/dashboard")
        assert r.status_code == 200
        for k in ("total_revenue", "total_paid", "invoices_count"):
            assert k in r.json()
    finally: C()

def test_full_finance_workflow(client, db):
    d = S(client, db)
    try:
        inv = client.post("/api/v1/invoices", json={
            "request_id": d["r"].id, "client_id": d["cl"].id, "invoice_date": "2026-09-01", "vat_rate": 20,
            "items": [{"description": "W", "quantity": 8, "unit": "h", "unit_price": 1000}],
        }).json()
        client.post(f"/api/v1/invoices/{inv['id']}/send")
        client.post("/api/v1/payments", json={
            "invoice_id": inv["id"], "amount": 9600, "method": "bank_transfer", "payment_date": "2026-09-10",
        })
        act = client.post("/api/v1/acts", json={
            "request_id": d["r"].id, "client_id": d["cl"].id,
            "act_date": "2026-09-10", "total_amount": 9600,
        }).json()
        client.post(f"/api/v1/acts/{act['id']}/sign", json={"signed_by": "client"})
        client.post(f"/api/v1/acts/{act['id']}/sign", json={"signed_by": "executor"})
        po = client.post("/api/v1/payouts", json={
            "owner_id": d["ow"].id, "vehicle_id": d["v"].id, "request_id": d["r"].id,
            "gross_amount": 8000, "commission_rate": 15, "payout_date": "2026-09-10",
        }).json()
        assert po["net_amount"] == "6800.00"
        pdf = client.get(f"/api/v1/invoices/{inv['id']}/pdf")
        assert pdf.status_code == 200
    finally: C()
'''

(TESTS / "test_finance_api.py").write_text(FIN_API, encoding="utf-8")
print("OK test_finance_api.py")

print("\nDONE! Now run: pytest tests/ -v")