from app.models.auth import User
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
