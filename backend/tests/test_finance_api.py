from app.models.auth import User
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
