from datetime import date
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
