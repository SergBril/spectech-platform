from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.auth import User
from app.models.catalog import Category, Vehicle
from app.models.company import Company
from app.models.contractor import Contractor
from app.models.dispatch import Request
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


def create_test_entities(db):
    """Создаёт базовые сущности для финансовых тестов."""
    init_system_data(db)

    company = Company(
        name="Тест Компания",
        legal_name='ООО "Тест"',
        inn="7799999999",
    )
    db.add(company)
    db.flush()

    client = Contractor(
        type="client",
        name="Тест Клиент",
        inn="7788888888",
        company_id=company.id,
    )
    db.add(client)

    owner = Contractor(
        type="owner",
        name="Тест Собственник",
        company_id=company.id,
    )
    db.add(owner)
    db.flush()

    category = Category(
        name="Тест категория",
        code="test",
        level=1,
        company_id=company.id,
    )
    db.add(category)
    db.flush()

    vehicle = Vehicle(
        id_type="vin",
        id_value="TEST12345678901234",
        category_id=category.id,
        name="Тест техника",
        status="free",
        company_id=company.id,
    )
    db.add(vehicle)
    db.flush()

    now = datetime.now(timezone.utc)
    request = Request(
        client_id=client.id,
        status="completed",
        request_type="one_time",
        vehicle_category_id=category.id,
        work_type="Тест работа",
        object_address="Москва",
        planned_start=now,
        planned_end=now + timedelta(hours=8),
        shift_duration_hours=8,
        client_rate=Decimal("15000"),
        rate_type="per_shift",
        estimated_amount=Decimal("15000"),
        source_channel="phone",
        priority="normal",
        company_id=company.id,
    )
    db.add(request)
    db.flush()

    return {
        "company": company,
        "client": client,
        "owner": owner,
        "vehicle": vehicle,
        "request": request,
    }


# === Тесты generate_document_number ===


def test_generate_document_number_first(db):
    """Первый документ года получает номер 0001."""
    create_test_entities(db)
    number = generate_document_number(db, "INV")
    assert number.startswith("INV-")
    assert number.endswith("-0001")


def test_generate_document_number_sequence(db):
    """Номера увеличиваются последовательно."""
    create_test_entities(db)
    num1 = generate_document_number(db, "INV")

    invoice = Invoice(
        document_number=num1,
        request_id=1,
        client_id=1,
        company_id=1,
        invoice_date=date(2026, 9, 1),
        status=DocumentStatus.draft,
    )
    db.add(invoice)
    db.commit()

    num2 = generate_document_number(db, "INV")
    assert num1 != num2
    assert num1.endswith("-0001")
    assert num2.endswith("-0002")


def test_generate_document_number_different_prefixes(db):
    """Разные префиксы имеют независимые последовательности."""
    create_test_entities(db)
    inv = generate_document_number(db, "INV")
    act = generate_document_number(db, "ACT")
    pay = generate_document_number(db, "PAY")

    assert inv.startswith("INV-")
    assert act.startswith("ACT-")
    assert pay.startswith("PAY-")


# === Тесты calculate_invoice_totals ===


def test_calculate_invoice_totals_no_vat(db):
    """Итоги счёта без НДС."""
    entities = create_test_entities(db)

    invoice = Invoice(
        document_number="INV-2026-TEST",
        request_id=entities["request"].id,
        client_id=entities["client"].id,
        company_id=entities["company"].id,
        invoice_date=date(2026, 9, 1),
        status=DocumentStatus.draft,
    )
    db.add(invoice)
    db.flush()

    item1 = InvoiceItem(
        invoice_id=invoice.id,
        description="Услуга 1",
        quantity=Decimal("8"),
        unit="час",
        unit_price=Decimal("2000"),
    )
    item2 = InvoiceItem(
        invoice_id=invoice.id,
        description="Услуга 2",
        quantity=Decimal("1"),
        unit="шт",
        unit_price=Decimal("3000"),
    )
    db.add_all([item1, item2])
    invoice.items = [item1, item2]

    calculate_invoice_totals(invoice)

    assert invoice.subtotal == Decimal("19000")
    assert invoice.vat_amount == Decimal("0")
    assert invoice.total == Decimal("19000")
    assert item1.amount == Decimal("16000")
    assert item2.amount == Decimal("3000")


def test_calculate_invoice_totals_with_vat(db):
    """Итоги счёта с НДС 20%."""
    entities = create_test_entities(db)

    invoice = Invoice(
        document_number="INV-2026-TEST2",
        request_id=entities["request"].id,
        client_id=entities["client"].id,
        company_id=entities["company"].id,
        invoice_date=date(2026, 9, 1),
        vat_rate=Decimal("20"),
        status=DocumentStatus.draft,
    )
    db.add(invoice)
    db.flush()

    item = InvoiceItem(
        invoice_id=invoice.id,
        description="Услуга",
        quantity=Decimal("1"),
        unit="шт",
        unit_price=Decimal("10000"),
    )
    db.add(item)
    invoice.items = [item]

    calculate_invoice_totals(invoice)

    assert invoice.subtotal == Decimal("10000")
    assert invoice.vat_amount == Decimal("2000")
    assert invoice.total == Decimal("12000")


# === Тесты calculate_payout ===


def test_calculate_payout_basic():
    """Базовый расчёт выплаты с комиссией 15%."""
    result = calculate_payout(Decimal("10000"), Decimal("15"))

    assert result["gross_amount"] == Decimal("10000")
    assert result["platform_commission"] == Decimal("1500")
    assert result["net_amount"] == Decimal("8500")
    assert result["commission_rate"] == Decimal("15")


def test_calculate_payout_zero_commission():
    """Выплата без комиссии."""
    result = calculate_payout(Decimal("5000"), Decimal("0"))

    assert result["gross_amount"] == Decimal("5000")
    assert result["platform_commission"] == Decimal("0")
    assert result["net_amount"] == Decimal("5000")


def test_calculate_payout_fractional():
    """Расчёт с дробными суммами (округление до копеек)."""
    result = calculate_payout(Decimal("1000"), Decimal("15"))

    assert result["platform_commission"] == Decimal("150.00")
    assert result["net_amount"] == Decimal("850.00")


# === Тесты register_payment ===


def test_register_payment_updates_invoice(db):
    """Платёж увеличивает paid_amount счёта."""
    entities = create_test_entities(db)

    invoice = Invoice(
        document_number="INV-TEST-PAY",
        request_id=entities["request"].id,
        client_id=entities["client"].id,
        company_id=entities["company"].id,
        invoice_date=date(2026, 9, 1),
        total=Decimal("10000"),
        paid_amount=Decimal("0"),
        status=DocumentStatus.sent,
    )
    db.add(invoice)
    db.flush()

    payment = Payment(
        invoice_id=invoice.id,
        amount=Decimal("5000"),
        method="bank_transfer",
        payment_date=date(2026, 9, 5),
    )
    db.add(payment)
    db.flush()

    register_payment(db, payment)

    db.refresh(invoice)
    assert invoice.paid_amount == Decimal("5000")
    assert invoice.status == DocumentStatus.partially_paid


def test_register_payment_full_paid(db):
    """Полная оплата меняет статус на 'paid'."""
    entities = create_test_entities(db)

    invoice = Invoice(
        document_number="INV-TEST-FULL",
        request_id=entities["request"].id,
        client_id=entities["client"].id,
        company_id=entities["company"].id,
        invoice_date=date(2026, 9, 1),
        total=Decimal("10000"),
        paid_amount=Decimal("0"),
        status=DocumentStatus.sent,
    )
    db.add(invoice)
    db.flush()

    payment = Payment(
        invoice_id=invoice.id,
        amount=Decimal("10000"),
        method="bank_transfer",
        payment_date=date(2026, 9, 5),
    )
    db.add(payment)
    db.flush()

    register_payment(db, payment)

    db.refresh(invoice)
    assert invoice.paid_amount == Decimal("10000")
    assert invoice.status == DocumentStatus.paid


def test_register_payment_updates_payout(db):
    """Платёж по выплате меняет её статус на 'paid'."""
    entities = create_test_entities(db)

    payout = Payout(
        document_number="PAY-TEST",
        owner_id=entities["owner"].id,
        vehicle_id=entities["vehicle"].id,
        company_id=entities["company"].id,
        gross_amount=Decimal("10000"),
        platform_commission=Decimal("1500"),
        net_amount=Decimal("8500"),
        commission_rate=Decimal("15"),
        payout_date=date(2026, 9, 1),
        status=DocumentStatus.sent,
    )
    db.add(payout)
    db.flush()

    payment = Payment(
        payout_id=payout.id,
        amount=Decimal("8500"),
        method="bank_transfer",
        payment_date=date(2026, 9, 5),
    )
    db.add(payment)
    db.flush()

    register_payment(db, payment)

    db.refresh(payout)
    assert payout.status == DocumentStatus.paid


# === Тесты get_finance_dashboard ===


def test_get_finance_dashboard_empty(db):
    """Пустой дашборд возвращает нули."""
    entities = create_test_entities(db)

    result = get_finance_dashboard(db, entities["company"].id)

    assert result["total_revenue"] == Decimal("0")
    assert result["total_paid"] == Decimal("0")
    assert result["invoices_count"] == 0


def test_get_finance_dashboard_with_data(db):
    """Дашборд корректно агрегирует данные."""
    entities = create_test_entities(db)

    invoice = Invoice(
        document_number="INV-DASH-1",
        request_id=entities["request"].id,
        client_id=entities["client"].id,
        company_id=entities["company"].id,
        invoice_date=date(2026, 9, 1),
        total=Decimal("12000"),
        paid_amount=Decimal("5000"),
        status=DocumentStatus.partially_paid,
    )
    db.add(invoice)

    payout = Payout(
        document_number="PAY-DASH-1",
        owner_id=entities["owner"].id,
        vehicle_id=entities["vehicle"].id,
        company_id=entities["company"].id,
        gross_amount=Decimal("10000"),
        platform_commission=Decimal("1500"),
        net_amount=Decimal("8500"),
        commission_rate=Decimal("15"),
        payout_date=date(2026, 9, 1),
        status=DocumentStatus.draft,
    )
    db.add(payout)

    act = Act(
        document_number="ACT-DASH-1",
        request_id=entities["request"].id,
        client_id=entities["client"].id,
        company_id=entities["company"].id,
        act_date=date(2026, 9, 1),
        total_amount=Decimal("12000"),
        status=DocumentStatus.draft,
    )
    db.add(act)
    db.commit()

    result = get_finance_dashboard(db, entities["company"].id)

    assert result["total_revenue"] == Decimal("12000")
    assert result["total_paid"] == Decimal("5000")
    assert result["total_outstanding"] == Decimal("7000")
    assert result["total_commission_earned"] == Decimal("1500")
    assert result["invoices_count"] == 1
    assert result["acts_count"] == 1
    assert result["payouts_count"] == 1