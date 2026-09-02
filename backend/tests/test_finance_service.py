from datetime import date
from decimal import Decimal
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.finance import Invoice, InvoiceItem, Act, Payout, Payment, DocumentStatus
from app.services.finance_service import (generate_document_number, calculate_invoice_totals,
    register_payment, calculate_payout, get_finance_dashboard)
from app.services.rbac_service import init_system_data
from tests.conftest import make_test_request

def e(db):
    init_system_data(db)
    co = Company(name="T", legal_name='OOO "T"', inn="7799999999"); db.add(co); db.flush()
    cl = Contractor(type="client", name="C", inn="7788888888", company_id=co.id)
    ow = Contractor(type="owner", name="O", company_id=co.id)
    db.add(cl); db.add(ow); db.flush()
    cat = Category(name="K", code="t", level=1, company_id=co.id); db.add(cat); db.flush()
    v = Vehicle(id_type="vin", id_value="X"*17, category_id=cat.id, name="V", status="free", company_id=co.id)
    db.add(v); db.flush()
    r = make_test_request(db, cl.id, cat.id, co.id); db.add(r); db.flush()
    return {"co": co, "cl": cl, "ow": ow, "v": v, "r": r}

def test_generate_document_number_first(db):
    e(db); assert generate_document_number(db, "INV").endswith("-0001")
def test_generate_document_number_sequence(db):
    e(db); n1 = generate_document_number(db, "INV")
    db.add(Invoice(document_number=n1, request_id=1, client_id=1, company_id=1, invoice_date=date(2026,9,1), status=DocumentStatus.draft)); db.commit()
    assert generate_document_number(db, "INV").endswith("-0002")
def test_generate_document_number_different_prefixes(db):
    e(db); assert generate_document_number(db, "INV").startswith("INV-")
def test_calculate_invoice_totals_no_vat(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id, company_id=d["co"].id, invoice_date=date(2026,9,1), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    i1 = InvoiceItem(invoice_id=inv.id, description="U1", quantity=Decimal("8"), unit="h", unit_price=Decimal("2000"))
    i2 = InvoiceItem(invoice_id=inv.id, description="U2", quantity=Decimal("1"), unit="p", unit_price=Decimal("3000"))
    db.add_all([i1, i2]); inv.items = [i1, i2]
    calculate_invoice_totals(inv)
    assert inv.subtotal == Decimal("19000") and inv.total == Decimal("19000")
def test_calculate_invoice_totals_with_vat(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id, company_id=d["co"].id, invoice_date=date(2026,9,1), vat_rate=Decimal("20"), status=DocumentStatus.draft)
    db.add(inv); db.flush()
    it = InvoiceItem(invoice_id=inv.id, description="U", quantity=Decimal("1"), unit="p", unit_price=Decimal("10000"))
    db.add(it); inv.items = [it]
    calculate_invoice_totals(inv)
    assert inv.vat_amount == Decimal("2000") and inv.total == Decimal("12000")
def test_calculate_payout_basic():
    r = calculate_payout(Decimal("10000"), Decimal("15"))
    assert r["platform_commission"] == Decimal("1500")
def test_calculate_payout_zero_commission():
    assert calculate_payout(Decimal("5000"), Decimal("0"))["platform_commission"] == Decimal("0")
def test_calculate_payout_fractional():
    assert calculate_payout(Decimal("1000"), Decimal("15"))["platform_commission"] == Decimal("150.00")
def test_register_payment_updates_invoice(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id, company_id=d["co"].id, invoice_date=date(2026,9,1), total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    p = Payment(invoice_id=inv.id, amount=Decimal("5000"), method="bank_transfer", payment_date=date(2026,9,5))
    db.add(p); db.flush(); register_payment(db, p); db.refresh(inv)
    assert inv.paid_amount == Decimal("5000") and inv.status == DocumentStatus.partially_paid
def test_register_payment_full_paid(db):
    d = e(db)
    inv = Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id, company_id=d["co"].id, invoice_date=date(2026,9,1), total=Decimal("10000"), paid_amount=Decimal("0"), status=DocumentStatus.sent)
    db.add(inv); db.flush()
    p = Payment(invoice_id=inv.id, amount=Decimal("10000"), method="bank_transfer", payment_date=date(2026,9,5))
    db.add(p); db.flush(); register_payment(db, p); db.refresh(inv)
    assert inv.status == DocumentStatus.paid
def test_register_payment_updates_payout(db):
    d = e(db)
    po = Payout(document_number="X", owner_id=d["ow"].id, vehicle_id=d["v"].id, company_id=d["co"].id, gross_amount=Decimal("10000"), platform_commission=Decimal("1500"), net_amount=Decimal("8500"), commission_rate=Decimal("15"), payout_date=date(2026,9,1), status=DocumentStatus.sent)
    db.add(po); db.flush()
    p = Payment(payout_id=po.id, amount=Decimal("8500"), method="bank_transfer", payment_date=date(2026,9,5))
    db.add(p); db.flush(); register_payment(db, p); db.refresh(po)
    assert po.status == DocumentStatus.paid
def test_get_finance_dashboard_empty(db):
    d = e(db); assert get_finance_dashboard(db, d["co"].id)["total_revenue"] == Decimal("0")
def test_get_finance_dashboard_with_data(db):
    d = e(db)
    db.add(Invoice(document_number="X", request_id=d["r"].id, client_id=d["cl"].id, company_id=d["co"].id, invoice_date=date(2026,9,1), total=Decimal("12000"), paid_amount=Decimal("5000"), status=DocumentStatus.partially_paid))
    db.add(Payout(document_number="Y", owner_id=d["ow"].id, vehicle_id=d["v"].id, company_id=d["co"].id, gross_amount=Decimal("10000"), platform_commission=Decimal("1500"), net_amount=Decimal("8500"), commission_rate=Decimal("15"), payout_date=date(2026,9,1), status=DocumentStatus.draft))
    db.add(Act(document_number="Z", request_id=d["r"].id, client_id=d["cl"].id, company_id=d["co"].id, act_date=date(2026,9,1), total_amount=Decimal("12000"), status=DocumentStatus.draft))
    db.commit()
    r = get_finance_dashboard(db, d["co"].id)
    assert r["total_revenue"] == Decimal("12000") and r["total_paid"] == Decimal("5000") and r["total_commission_earned"] == Decimal("1500")
